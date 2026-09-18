# =============================================================================
# OFFLINE MLflow GenAI EVAL for a deployed Databricks Apps MCP server
# =============================================================================
# Evaluate an LLM agent that uses YOUR deployed MCP server, scored by MLflow
# GenAI judges. Paste this into a Databricks notebook opened in THIS folder
# (eval/databricks/) so the `agent_server/` package sits next to it.
#
# !!! FIRST, run this in a SEPARATE notebook cell ABOVE this one, on its own,
# !!! and let it finish (it restarts the Python interpreter):
# !!!
# !!!     %pip install openai-agents databricks-openai
# !!!     %restart_python
# !!!
# !!! The agent (agent_server/agent.py) imports `agents` (openai-agents) and
# !!! `databricks_openai`, which are not on the default Databricks runtime.
# !!! %restart_python must run so the freshly installed packages are importable.
#
# This variant authenticates to the MCP app with a SERVICE PRINCIPAL (OAuth
# M2M). That is the only identity that reliably reaches a deployed Databricks
# App from an offline eval -- OBO needs a forwarded request header (absent in a
# notebook) and a plain notebook identity cannot mint an OAuth token. See
# agent_server/eval_auth.py for the full explanation.
#
# The generated agent.py is used UNMODIFIED. All auth wiring is injected at
# runtime by agent_server/eval_auth.py, and the deployment-specific values
# (model, MCP URL) are set on the module after import -- so you never edit
# agent.py.
#
# ONE-TIME SETUP (see README):
#   - Create a service principal + OAuth secret.
#   - Grant it workspace-access and "Can Use" on your MCP app.
#   - Store its credentials in a Databricks secret scope.
# =============================================================================

import os

# --- CONFIG: the things you edit --------------------------------------------
# 1) Your deployed MCP server's /mcp URL (from the deploy kit output).
MCP_SERVER_URL = "https://<your-app>.aws.databricksapps.com/mcp"

# 2) A Databricks foundation-model serving endpoint you can query. List options:
#    [e.name for e in WorkspaceClient().serving_endpoints.list()]
MODEL = "databricks-claude-haiku-4-5"

# 3) The workspace host that fronts your MCP app + an experiment YOU can write
#    to (get its id from the experiment's URL or the Experiments UI).
DATABRICKS_HOST = "https://<your-workspace>.cloud.databricks.com/"
EXPERIMENT_ID = "<your-experiment-id>"

# 4) The Databricks secret scope + keys holding the service-principal creds
#    (created by setup-eval-sp.sh; defaults match that script's output).
SECRET_SCOPE = "mcp-eval-secrets"
SECRET_KEY_CLIENT_ID = "sp_id"
SECRET_KEY_CLIENT_SECRET = "sp_secret"
# -----------------------------------------------------------------------------

import asyncio
import atexit
import threading

import mlflow
from mlflow.entities.trace_location import MlflowExperimentLocation
from mlflow.genai import evaluate
from mlflow.genai.scorers import (
    Correctness,
    Guidelines,
    RelevanceToQuery,
    Safety,
)
from mlflow.types.responses import ResponsesAgentRequest

# NOTE: do NOT call nest_asyncio.apply(). It globally monkeypatches asyncio and
# conflicts with the shared-loop design below (you'd hit "Event loop is closed"
# during httpx connection teardown).

# --- Service-principal credentials -------------------------------------------
# Read from a Databricks secret scope. dbutils only exists inside a Databricks
# notebook; guard so the module still imports elsewhere.
try:
    _sp_client_id = dbutils.secrets.get(SECRET_SCOPE, SECRET_KEY_CLIENT_ID)  # type: ignore[name-defined]
    _sp_client_secret = dbutils.secrets.get(SECRET_SCOPE, SECRET_KEY_CLIENT_SECRET)  # type: ignore[name-defined]
except NameError:
    # Outside Databricks: fall back to env vars if present.
    _sp_client_id = os.getenv("DATABRICKS_CLIENT_ID", "")
    _sp_client_secret = os.getenv("DATABRICKS_CLIENT_SECRET", "")

# --- Wire auth into the (unmodified) generated agent -------------------------
import agent_server.agent as agent  # noqa: E402
from agent_server.eval_auth import patch_agent_with_service_principal  # noqa: E402

# Override the deployment-specific values in the generated module with YOUR
# config, so you never have to edit agent.py.
agent.MODEL = MODEL
agent.MCP_SERVERS = [("mcp-server", MCP_SERVER_URL)]

# Monkeypatch the agent's get_mcp_user_workspace_client() to return an
# authenticated service-principal client. This is what makes the MCP calls
# actually reach the OAuth-gated app.
_sp = patch_agent_with_service_principal(
    agent,
    host=DATABRICKS_HOST,
    client_id=_sp_client_id,
    client_secret=_sp_client_secret,
)

# Optional sanity check: confirm the SP identity resolves before the full eval.
# _sp.current_user.me()

invoke = agent.invoke

# --- MLflow experiment + trace destination -----------------------------------
# On MLflow 3.x, mlflow.genai.evaluate() logs judge assessments via MLflow
# Tracing. Without an explicit trace destination the harness can get a None
# trace back and fail with "'NoneType' object has no attribute 'info'", which
# cascades into every scorer failing. Setting both fixes that.
mlflow.set_experiment(experiment_id=EXPERIMENT_ID)
mlflow.tracing.set_destination(MlflowExperimentLocation(experiment_id=EXPERIMENT_ID))

# Tuning knobs (uncomment if the eval times out or hammers the app).
# os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
# os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "60"

# --- Evaluation dataset -------------------------------------------------------
# REPLACE this with questions relevant to YOUR MCP server's tools. The row below
# is an example (it targets a CDC PLACES tool) to show the shape.
#
# `inputs` keys must match predict()'s parameter names (here: `request`).
# Expectations for judges like Correctness MUST live under an `expectations`
# dict; `expected_facts` must be a LIST. Add more rows to broaden coverage.
eval_dataset = [
    {
        "inputs": {
            "request": "<a question your agent should answer using its tools>"
        },
        "expectations": {
            "expected_facts": ["<a fact the correct answer must contain>"],
        },
    },
]


# --- Async plumbing -----------------------------------------------------------
# agent.py creates ONE AsyncDatabricksOpenAI client at import and reuses it for
# every invoke(). Its httpx/anyio connection pool binds to the first event loop
# that touches it, so a fresh-loop-per-call approach fails with "bound to a
# different event loop". We run ONE persistent loop on a background thread and
# marshal every coroutine onto it with run_coroutine_threadsafe. The cached
# client never crosses loops; the loop is never closed mid-run; and evaluate()'s
# parallel worker threads can all submit onto it safely.
_LOOP = asyncio.new_event_loop()


def _loop_runner():
    asyncio.set_event_loop(_LOOP)
    _LOOP.run_forever()


_LOOP_THREAD = threading.Thread(target=_loop_runner, daemon=True, name="eval-async-loop")
_LOOP_THREAD.start()
atexit.register(lambda: _LOOP.call_soon_threadsafe(_LOOP.stop))


def _run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _LOOP).result()


def _extract_text(response) -> str:
    """Pull assistant text out of a ResponsesAgentResponse robustly.

    The last output item may be a tool call, and message content may be a list
    of content blocks (e.g. {"type": "output_text", "text": ...}) rather than a
    plain string. Walk items in reverse and return the first real text found.
    """
    for item in reversed(response.output):
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            if content.strip():
                return content
            continue
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text") or block.get("content") or "")
                else:
                    parts.append(getattr(block, "text", "") or "")
            text = "".join(p for p in parts if p)
            if text.strip():
                return text
    return str(response.output)


@mlflow.trace(span_type="AGENT")
def predict(request: str) -> str:
    agent_request = ResponsesAgentRequest(input=[{"role": "user", "content": request}])
    response = _run_async(invoke(agent_request))
    return _extract_text(response)


# --- Run evaluation -----------------------------------------------------------
# Scorers: https://docs.databricks.com/mlflow3/genai/eval-monitor/predefined-judge-scorers
if __name__ == "__main__":
    results = evaluate(
        data=eval_dataset,
        predict_fn=predict,
        scorers=[
            Safety(),
            RelevanceToQuery(),
            Correctness(),  # uses expectations.expected_facts
            Guidelines(name="conciseness", guidelines="Responses must be concise."),
        ],
    )
    print(results)
    # Results also appear in the MLflow experiment UI.
