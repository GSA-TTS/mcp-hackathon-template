---
name: mcp-eval-wxai
description: Guide for building a Phoenix-based evaluation harness for an MCP server, with the agent and LLM-as-judge models served by IBM watsonx.ai. Use when you need to create or extend LLM-as-judge evaluations that measure how well an agent can accomplish realistic tasks using only the MCP server's tools. Covers watsonx.ai account setup (project, API key, URL), the eval/phoenix module layout, dataset creation, the LangChain agent, judges, system prompts, and running experiments.
---

# MCP Server Evaluation Guide (Phoenix + IBM watsonx.ai)

## Overview

The measure of an MCP server's quality is NOT how comprehensively it implements
tools, but how well those tools (schemas, docstrings, return shapes) let an LLM with
NO other context answer realistic, difficult questions. This skill describes a
reusable [Arize Phoenix](https://docs.arize.com/phoenix) evaluation harness that:

1. Spins up a LangChain agent (backed by a watsonx.ai model) connected to the MCP server (over stdio).
2. Feeds it a dataset of natural-language questions with known answers.
3. Scores each answer with LLM-as-judge evaluators (also watsonx.ai models) and logs traces to Phoenix.

> This skill is the watsonx.ai variant of `mcp-eval`. Everything except model
> access (watsonx.ai setup, env vars, dependencies, `ChatWatsonx` in `agent.py`,
> the judge `LLM` wrapper) is identical to the original.

Use this after the server is built (it complements the `mcp-builder` skill, which
produces the `evaluation.xml` question set this harness consumes).

---

# Module Layout

The harness lives in `eval/phoenix/` at the repo root:

```
eval/phoenix/
├── agent.py                   # The <Server>Agent class (launches the MCP server over stdio)
├── create_dataset.py          # CLI: upload a CSV dataset to Phoenix
├── run_experiment.py          # CLI: run an experiment (agent + judges) against a dataset
├── datasets.yaml              # Dataset registry (name -> csv_path, input/output keys, description)
├── README.md                  # Usage docs for this specific server
├── judges/                    # LLM-as-judge evaluators
│   ├── __init__.py            # Re-exports each judge for `from judges import ...`
│   ├── correctness_judge.py   # match_expected_response (compares to ground truth)
│   └── relevance_judge.py     # check_answer_scope (in-scope vs. out-of-scope)
├── prompts/                   # Agent system prompts, one per version
│   ├── system_prompt_v1.txt   # Basic domain analyst
│   └── system_prompt_v2.txt   # + scope boundaries
└── datasets/                  # Test datasets (CSV files)
    └── <name>/examples/<name>.csv
```

**Naming:** Name the agent class after the server (e.g. `HydroAgent`, `NIHReporterAgent`)
and name datasets `<domain>-eval-<n>` (e.g. `hydro-eval-0`).

---

# watsonx.ai Setup (one-time)

You need three values: the **watsonx.ai URL**, an **IBM Cloud API key**, and a
**watsonx.ai project ID**. They populate `WATSONX_URL`, `WATSONX_API_KEY` and
`WATSONX_PROJECT_ID` in the `.env` below.

## 1. Pick or create a project

Inference requires a project (or deployment space) that has a **watsonx.ai Runtime**
service instance associated with it.

- **Sandbox project (quickest):** watsonx.ai creates a sandbox project automatically
  when you sign up, and your watsonx.ai Runtime instance is associated with it
  automatically. If it is missing, click **Create sandbox** in the Projects section
  of the home page.
- **New project:** **Projects > View all projects > New project > Create an empty
  project**, enter a name, then **Create**. Then associate the service: project
  **Manage** tab > **Services & integrations** > **Associate service**, tick your
  **watsonx.ai Runtime** instance, **Associate**. (Needs the project **Admin** role;
  the instance must be in the same region as the project.)

## 2. Get the project ID

Open the project, go to **Manage** > **General**, and copy the **project ID** from the
*Details* section. This is `WATSONX_PROJECT_ID`.

## 3. Get the watsonx.ai URL

The URL is the regional endpoint where your watsonx.ai Runtime instance lives. It is
the `url` shown under **Developer access** on the watsonx.ai home page. This is
`WATSONX_URL`.

| Region | `WATSONX_URL` |
|---|---|
| Dallas | `https://us-south.ml.cloud.ibm.com` |
| Frankfurt | `https://eu-de.ml.cloud.ibm.com` |
| London | `https://eu-gb.ml.cloud.ibm.com` |
| Tokyo | `https://jp-tok.ml.cloud.ibm.com` |
| Sydney | `https://au-syd.ml.cloud.ibm.com` |
| Toronto | `https://ca-tor.ml.cloud.ibm.com` |

The URL must match the project's region. watsonx.ai on AWS uses different hosts; copy
the value from **Developer access** instead of using the table.

## 4. Create an IBM Cloud API key

Log in to [IBM Cloud](https://cloud.ibm.com/), go to **Manage > Access (IAM) > API
keys** (or use **Create API key** under **Developer access** on the watsonx.ai home
page), click **Create**, name it, and **copy it immediately**: it can only be viewed
or downloaded at creation time. This is `WATSONX_API_KEY`. Use a key for an account
that has access to the project. Never commit it.

## 5. Choose models

`AGENT_MODEL` must support **tool calling**; `JUDGE_MODEL` only needs chat. Model
availability differs by region and changes over time, so list what your region
actually serves instead of copying an ID from this document:

```bash
# Tool-calling models (candidates for AGENT_MODEL)
curl -s "$WATSONX_URL/ml/v1/foundation_model_specs?version=2024-10-10&filters=task_function_calling,!lifecycle_withdrawn:and&limit=100" \
  | python3 -c "import json,sys; [print(r['model_id']) for r in json.load(sys.stdin)['resources']]"

# Chat models (candidates for JUDGE_MODEL): use filters=function_text_chat instead
```

This public endpoint needs no key. At the time of writing, `meta-llama/llama-3-3-70b-instruct`
was in the tool-calling list for all six regions above, and it is the default used
here. Some entries in the list are base models (e.g. `ibm/granite-3-1-8b-base`);
prefer an instruct/chat model. Use another model if your list says otherwise. If your project is restricted, the
models your project can actually call may be a subset of this list; the smoke test
below confirms it.

## 6. Smoke test before running the harness

With the three values exported (or in `.env`), run this once. It confirms credentials,
the project association, a plain chat call, and tool calling:

```python
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_ibm import ChatWatsonx

load_dotenv()

@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

model = ChatWatsonx(model_id=os.environ["AGENT_MODEL"], temperature=0)  # fails here on bad key/URL
print(model.invoke("Say OK").content)
msg = model.bind_tools([add]).invoke("What is 2 plus 4? Use the tool.")
print(msg.tool_calls)   # expect [{'name': 'add', 'args': {'a': 2, 'b': 4}, ...}]
```

An empty `tool_calls` list means `AGENT_MODEL` does not do tool calling; pick another.

---

# Environment & Configuration

All credentials come from a **root-level `.env`** (gitignored). Provide a
`.env.example` at the repo root documenting the keys. Every module calls
`load_dotenv()` (bare, so it walks up from CWD to the repo root).

Required variables:

| Variable | Used by | Purpose |
|---|---|---|
| `WATSONX_URL` | agent + judges | watsonx.ai regional endpoint, e.g. `https://us-south.ml.cloud.ibm.com` (also `eu-de`, `eu-gb`, `jp-tok`, `au-syd`, `ca-tor`) |
| `WATSONX_API_KEY` | agent + judges | IBM Cloud API key (the SDK exchanges it for an IAM token and refreshes it) |
| `WATSONX_PROJECT_ID` | agent + judges | watsonx.ai project ID (use `WATSONX_SPACE_ID` instead if you deploy to a space) |
| `AGENT_MODEL` | `agent.py` | watsonx.ai model ID the agent-under-test drives. MUST support tool calling |
| `JUDGE_MODEL` | `judges/*.py` | watsonx.ai model ID the LLM-as-judge uses (separate from the agent, so you can judge with a stronger/different model) |

These `WATSONX_*` names are read automatically by both `langchain-ibm` (`ChatWatsonx`)
and LiteLLM's `watsonx/` provider (used by Phoenix evals), so no credentials need to
be passed in code. Model IDs use the watsonx.ai form, e.g.
`meta-llama/llama-3-3-70b-instruct`, `ibm/granite-4-h-small`; check the model is
available in your region and supports tool calling (agent), per setup step 5.

**Keep `AGENT_MODEL` and `JUDGE_MODEL` distinct env vars.** Judging with a different
(often stronger) model than the agent-under-test reduces self-preference bias and lets
you hold the judge fixed while iterating on the agent. Read `JUDGE_MODEL` with a
sensible default: `os.getenv("JUDGE_MODEL", "meta-llama/llama-3-3-70b-instruct")`.

Example `.env.example`:

```bash
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_API_KEY=            # IBM Cloud API key (never commit)
WATSONX_PROJECT_ID=         # project > Manage > General > Details
AGENT_MODEL=meta-llama/llama-3-3-70b-instruct
JUDGE_MODEL=meta-llama/llama-3-3-70b-instruct
```

The MCP server itself may need no credentials (e.g. a public API); note that in
`.env.example` so users don't think the eval vars are for the server.

## Dependency group

Add eval-only dependencies to a `dev` dependency group in `pyproject.toml` so they
don't ship with the server:

```toml
[dependency-groups]
dev = [
    "arize-phoenix>=18.0.0",
    "arize-phoenix-client>=2.13.0",
    "arize-phoenix-evals>=3.1.1",
    "langchain>=1.3.14",
    "langchain-mcp-adapters>=0.3.0",
    "langchain-ibm>=1.1.2",
    "litellm>=1.0.0",
    "openinference-instrumentation-langchain>=0.1.67",
    "opentelemetry-exporter-otlp>=1.43.0",
    "opentelemetry-sdk>=1.43.0",
    "pandas>=2.0.0",
    "pyyaml>=6.0.0",
]
```

`langchain-ibm` pulls in `ibm-watsonx-ai`. `litellm` is required by Phoenix evals'
LiteLLM adapter, which is how the judges reach watsonx.ai.

Install with `uv sync --group dev`.

---

# Components

## The Agent (`agent.py`)

A single `<Server>Agent` class that owns Phoenix instrumentation, the MCP client, and
the LangChain agent. Key responsibilities:

- **Instrument once:** call `phoenix.otel.register(project_name, endpoint)` then
  `LangChainInstrumentor().instrument(tracer_provider=...)` in `initialize()`.
- **Launch the server over stdio** via `MultiServerMCPClient`. Set `cwd` to the repo
  root so the launch command works regardless of the current directory:

  ```python
  REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
  ...
  self.client = MultiServerMCPClient({
      "<server>_server": {
          "transport": "stdio",
          "command": "uv",
          "args": ["run", "src/<servername>/app.py"],
          "cwd": REPO_ROOT,
      },
      # Alternative: {"transport": "http", "url": "http://localhost:8000/mcp"}
  })
  tools = await self.client.get_tools()
  ```

- **Build the agent** with `create_agent(model=ChatWatsonx(...), tools=tools,
  system_prompt=self._load_system_prompt())`, using `temperature=0` for reproducibility.
  `ChatWatsonx` picks up `WATSONX_URL` / `WATSONX_API_KEY` / `WATSONX_PROJECT_ID`
  from the environment:

  ```python
  from langchain_ibm import ChatWatsonx

  model = ChatWatsonx(
      model_id=os.environ["AGENT_MODEL"],
      temperature=0,
      # url / api_key / project_id are read from WATSONX_URL / WATSONX_API_KEY /
      # WATSONX_PROJECT_ID; pass them explicitly only if you need to override.
  )
  agent = create_agent(model=model, tools=tools, system_prompt=self._load_system_prompt())
  ```
- **Load prompts by version** from `prompts/system_prompt_{version}.txt` so experiments
  can compare prompt variants.
- **Expose a sync task factory** `create_experiment_task()` that returns a
  `task(example)` closure calling `asyncio.run(self.run(example.input["query"]))` —
  Phoenix experiments expect synchronous task functions.
- Provide a `main()` for standalone smoke testing (`python agent.py`).

## Judges (`judges/`)

Each judge is a plain function using `phoenix.evals.ClassificationEvaluator` with an
`LLM` wrapper pointed at the `JUDGE_MODEL`. Reach watsonx.ai through the LiteLLM
provider by prefixing the model ID with `watsonx/`:

```python
from phoenix.evals import LLM

judge_llm = LLM(
    provider="litellm",
    model=f"watsonx/{os.getenv('JUDGE_MODEL', 'meta-llama/llama-3-3-70b-instruct')}",
)
```

Credentials are read from `WATSONX_URL` / `WATSONX_API_KEY` / `WATSONX_PROJECT_ID`
(the `LLM` wrapper does not forward extra client kwargs to LiteLLM completions, so
use env vars rather than constructor arguments). Judges take Phoenix's `input`, `output`,
and (for correctness) `expected` dicts and return a single classification label.

**`match_expected_response(input, output, expected)` — correctness.** Compares the
agent's answer to ground truth (`expected["responses"]`). The prompt template MUST
tolerate reasonable formatting differences (units, surrounding prose, extra context)
so a correct answer isn't marked wrong for cosmetic reasons. Returns
`correct` / `incorrect` (`choices={"correct": 1, "incorrect": 0}`).

**`check_answer_scope(input, output)` — relevance/scope.** No reference needed. Judges
whether the agent answered an in-scope question or appropriately refused an
out-of-scope one. Returns `within_scope` / `out_of_scope`.

Judge template guidelines:
- State the agent's exact domain/scope so the judge knows what "in scope" means.
- Use `{input}`, `{output}`, and (correctness only) `{reference}` placeholders.
- Set `temperature=0.0`.
- Return `result[0]` (Phoenix ClassificationEvaluator returns a list).

`judges/__init__.py` re-exports each judge so `run_experiment.py` can do
`from judges import match_expected_response, check_answer_scope`.

## System Prompts (`prompts/`)

One `system_prompt_v{n}.txt` per version. Version them so you can A/B prompt strategies
in separate experiments:
- **v1 — basic analyst:** the domain role plus critical conventions (coordinate systems,
  ID formats, unit caveats) the agent needs to call tools correctly.
- **v2 — scope boundaries:** adds explicit in-scope vs. out-of-scope guidance ("answer
  factual X; refuse Y/predictions/recommendations") while still being helpful first.

Keep `run_experiment.py`'s `--system-prompt-version choices=[...]` in sync with the
prompt files that actually exist.

## Dataset (`datasets/` + `datasets.yaml`)

Datasets are CSVs with an input column (`query`) and an output/reference column
(`responses`). Convert the `evaluation.xml` produced by `mcp-builder` into a CSV:
each `<question>` -> `query`, each `<answer>` -> `responses`.

Keep the source `evaluation.xml` inside the dataset directory it produces (e.g.
`datasets/<name>/evaluation.xml`) rather than at the repo root, so the questions and
the generated CSV travel together:

```
datasets/<name>/
├── evaluation.xml            # source question set (from mcp-builder Phase 4)
└── examples/<name>.csv       # generated dataset (query,responses)
```

Register each dataset in `datasets.yaml`:

```yaml
datasets:
  <name>:
    csv_path: datasets/<name>/examples/<name>.csv
    input_keys:
      - query
    output_keys:
      - responses
    description: "One-line description and question count"
```

Question quality bar (from the evaluation methodology): independent, read-only,
verifiable single answer, stable over time, and complex enough to require multiple tool
calls. Prefer paraphrased questions that can't be answered by keyword-matching the
tool output.

## CLIs

**`create_dataset.py`** — loads a CSV per `datasets.yaml`, validates the required
columns exist, and uploads via `phoenix.client.Client().datasets.create_dataset(...)`.
Supports `--list`, `--dataset-name`, `--phoenix-name`, `--csv-path`, and `--dry-run`
(validate without uploading — use this in CI/pre-flight).

**`run_experiment.py`** — loads the Phoenix dataset, initializes the agent with a
chosen prompt version, and runs `client.experiments.run_experiment(dataset, task,
evaluators=[check_answer_scope, match_expected_response], ...)`. Supports
`--dataset-name`, `--system-prompt-version`, `--project-name`, `--phoenix-endpoint`,
`--experiment-description`, `--dataset-version-id`, and `--no-validate`.

---

# Workflow

Run all commands from `eval/phoenix/` (after `uv sync --group dev` and populating `.env`).

1. **Start Phoenix** (standalone server, UI at :6006, OTLP at :4317):
   ```bash
   uv run arize-phoenix serve
   ```

2. **Create the dataset in Phoenix** (one-time per dataset):
   ```bash
   uv run create_dataset.py --dataset-name <name>
   # validate only, no upload:
   uv run create_dataset.py --dataset-name <name> --dry-run
   ```

3. **Run an experiment**:
   ```bash
   uv run run_experiment.py --dataset-name <name>
   uv run run_experiment.py --dataset-name <name> --system-prompt-version v2
   ```

4. **Review** results and per-question traces in the Phoenix UI (http://localhost:6006).
   Inspect failing cases to decide whether the fix belongs in the tool schema/docstring,
   the system prompt, or the question itself.

---

# Building a New Eval Harness (checklist)

When adding this harness to a fresh MCP server repo:

- [ ] Copy `eval/phoenix/` and rename the agent class + MCP server key after the server.
- [ ] Point the stdio launch command at the server's `app.py`; set `cwd=REPO_ROOT`.
- [ ] Rewrite both judge prompt templates for the new domain/scope.
- [ ] Wire `AGENT_MODEL` and `JUDGE_MODEL` (distinct watsonx.ai model IDs) and `WATSONX_URL` / `WATSONX_API_KEY` / `WATSONX_PROJECT_ID`; update `.env.example`.
- [ ] Write system prompts (v1 basic, v2 scoped) for the new domain.
- [ ] Convert `evaluation.xml` -> `datasets/<name>/examples/<name>.csv` and register it in `datasets.yaml`.
- [ ] Add the `dev` dependency group; run `uv sync --group dev`.
- [ ] Verify: `create_dataset.py --dry-run` loads the CSV, and `agent.py` / `judges` / `run_experiment.py` import cleanly and the MCP server launches with the agent's exact config.
- [ ] Update `eval/phoenix/README.md` for the new server.

---

# Common Pitfalls

- **Judge marks correct answers wrong** — the correctness template is too strict. Allow
  unit/formatting/context differences explicitly.
- **Agent can't find tools** — the stdio `command`/`args`/`cwd` don't resolve to a
  runnable server. Test the exact `MultiServerMCPClient` config in isolation.
- **Env vars missing at judge time** — judges also call `load_dotenv()` and read
  `JUDGE_MODEL`/`WATSONX_*`; they run in the same process so the root `.env` covers them.
- **Prompt version mismatch** — `--system-prompt-version` choices must match the files
  in `prompts/`.
- **`project_id`/`space_id` not set** — watsonx.ai inference requires one of them
  (`WATSONX_PROJECT_ID` or `WATSONX_SPACE_ID`); the error surfaces from both
  `ChatWatsonx` and LiteLLM.
- **Agent never calls tools** — the chosen `AGENT_MODEL` does not support tool calling
  on watsonx.ai. Re-run the smoke test (setup step 6) and pick a model from the
  `function_text_chat` list (setup step 5).
- **401 / token errors** — `WATSONX_API_KEY` must be an IBM Cloud API key for the
  account that owns the project, and `WATSONX_URL` must match the project's region.
- **Non-reproducible runs** — set `temperature=0` for both the agent and the judges.
