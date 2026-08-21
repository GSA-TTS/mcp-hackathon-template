# GSA MCP Hackathon — Server Template

A ready-to-run starter for building a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server in Python, plus deployment kits for **IBM Cloud (watsonx Orchestrate)** and **Databricks**.

Built with [FastMCP](https://github.com/jlowin/fastmcp) and [uv](https://docs.astral.sh/uv/). If you have never built an MCP server before, start with **[QUICKSTART.md](QUICKSTART.md)**.

---

## What is an MCP server?

An MCP server exposes **tools** (functions the model can call), **prompts** (reusable conversation starters), and **resources** (data the model can read) to an AI client such as Claude Desktop, Claude Code, or an agent platform like watsonx Orchestrate. You write the tools; the client's model decides when to call them.

This template gives you a working server with one example of each, so you can replace the examples with your own service and deploy.

---

## Repo structure

```
mcp-hackathon-template/
├── README.md                  # This file
├── QUICKSTART.md              # 5-minute clone → run → connect walkthrough
├── main.py                    # Local entry point (uv run python main.py)
├── pyproject.toml             # Package + dependencies (uv)
├── requirements.txt           # Mirror of runtime deps (for buildpack hosts)
├── Dockerfile                 # Container image (streamable-HTTP, port 8080)
├── manifest.yaml              # cloud.gov (Cloud Foundry) deploy
├── server.json                # MCP registry metadata
├── .env.example               # Copy to .env for local dev
├── .github/workflows/ci.yml   # Lint + test on push/PR
├── src/
│   └── example_server/        # ← rename to your service
│       ├── app.py             # Thin entry point: builds FastMCP, picks transport
│       ├── config.py          # Settings from env vars / .env
│       ├── models.py          # Pydantic models & enums for tool params
│       ├── utils.py           # Shared helpers (HTTP client, pagination)
│       ├── routes.py          # HTTP-only routes (/health, /version)
│       ├── tools/             # ONE FILE PER TOOL
│       │   ├── __init__.py    #   register_tools(mcp) aggregator
│       │   └── example_tool.py
│       ├── prompts/
│       │   ├── __init__.py    #   register_prompts(mcp) aggregator
│       │   └── example.py
│       └── resources/
│           ├── __init__.py    #   register_resources(mcp) aggregator
│           └── example.py
├── tests/                     # Import + registration smoke tests
├── eval/                      # Stub → build a Phoenix eval harness (see mcp-eval skill)
└── deploy/
    ├── README.md              # Which deployment kit to use
    ├── ibm/                   # watsonx Orchestrate: 3 kits (see below)
    └── databricks/            # Databricks Apps kit
```

---

## Getting started

### Prerequisites
- [uv](https://docs.astral.sh/uv/) — `pip install uv` or `brew install uv`

### Install and run

```bash
cp .env.example .env
uv sync
uv run python main.py
```

The server starts in **stdio** mode — it talks JSON-RPC over stdin/stdout, which is how local clients (Claude Desktop, Claude Code) launch it. See [QUICKSTART.md](QUICKSTART.md) to connect a client.

### Verify

```bash
uv sync --group dev
uv run pytest tests/ -v      # tests
uv run ruff check .          # lint
```

---

## The one-tool-per-file pattern

Each tool lives in its own file under `src/example_server/tools/` and exposes a `register(mcp)` function. `tools/__init__.py` calls each one from a single `register_tools(mcp)`. This keeps the tool list scannable and lets you add or remove an integration by touching two files.

**Step 1 — create `src/example_server/tools/my_tool.py`:**

```python
from typing import Annotated
from fastmcp import FastMCP

from example_server.utils import fetch_json


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="example_get_thing",
        annotations={
            "title": "Get a thing",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def get_thing(thing_id: Annotated[str, "The ID to fetch."]) -> dict:
        """One-line summary. Document the data source, its update cadence,
        and the return shape here — the model reads this docstring."""
        return await fetch_json(f"https://api.example.gov/things/{thing_id}")
```

**Step 2 — wire it up in `tools/__init__.py`:**

```python
from example_server.tools import example_tool, my_tool

def register_tools(mcp) -> None:
    example_tool.register(mcp)
    my_tool.register(mcp)  # ← add this line
```

**Step 3 — add any API key** as a typed field in `config.py` and document the env var in `.env.example`.

Prompts (`prompts/`) and resources (`resources/`) follow the exact same `register(mcp)` + aggregator pattern.

---

## Rename the package

Before publishing your server, rename `example_server` to your service (e.g. `census_mcp`):

1. Rename the folder `src/example_server/` → `src/<your_name>/`.
2. Update `pyproject.toml`: the `[project].name`, `[project.scripts]`, and `[tool.hatch.build.targets.wheel].packages`.
3. Find-and-replace `example_server` across `src/`, `tests/`, `main.py`, `Dockerfile`, and `manifest.yaml`.

---

## Tool design tips (federal data)

- **Return structured data, not prose.** Return dicts/lists with consistent keys and let the model narrate.
- **Document freshness.** Federal datasets lag; state the update frequency and "as-of" date in the docstring.
- **Expose pagination.** Use `PaginationParams` / `paginate()` from `utils.py`, and return `has_more` / `next_offset`.
- **Use explicit timeouts.** `utils.fetch_json` defaults to 30s.
- **Actionable errors.** Return an error dict with a `hint`, not a raw stack trace.

---

## Deploying

Local development uses stdio. To share your server with an agent platform, deploy it and register it. See **[deploy/README.md](deploy/README.md)** for a chooser, then:

- **IBM watsonx Orchestrate** — [deploy/ibm/](deploy/ibm/) (three kits: local stdio toolkit, Code Engine build-from-Git, and prebuilt image).
- **Databricks Apps** — [deploy/databricks/](deploy/databricks/).

Both read the same server code; `app.py` automatically serves HTTP when the platform injects a port.

---

## Evaluations

Measuring how well an LLM can use your tools is the real test of server quality. This template intentionally does **not** ship an eval harness — see [eval/README.md](eval/README.md) for how to build one with the `mcp-eval` skill.

---

## License

[MIT](LICENSE). See [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy and hackathon security notes.
