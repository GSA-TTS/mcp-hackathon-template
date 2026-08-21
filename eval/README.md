# Evaluations (stub)

This template does **not** include an evaluation harness — but building one is
the single best way to know whether your MCP server actually works well.

## Why evaluate?

The quality of an MCP server is **not** how many tools it has — it's how well an
LLM with no other context can use those tools (their names, schemas, docstrings,
and return shapes) to answer realistic, difficult questions. An eval harness
measures exactly that and shows you *where* to fix things (tool schema, docstring,
or system prompt).

## How to build one

Use the **`mcp-eval` skill** (available to the coding agent in this repo under
`.agents/skills/mcp-eval/`). It walks you through a reusable
[Arize Phoenix](https://docs.arize.com/phoenix) harness that:

1. Launches your MCP server over stdio and connects a LangChain agent to it.
2. Feeds the agent a dataset of natural-language questions with known answers.
3. Scores each answer with LLM-as-judge evaluators and logs traces to Phoenix.

The companion **`mcp-builder` skill** (`.agents/skills/mcp-builder/`) covers
Phase 4 — writing the 10 gold questions (`evaluation.xml`) that become the
harness's dataset.

## Expected layout once built

The `mcp-eval` skill produces an `eval/phoenix/` module roughly like:

```
eval/phoenix/
├── agent.py            # <Server>Agent — launches your server over stdio
├── create_dataset.py   # CLI: upload a CSV dataset to Phoenix
├── run_experiment.py   # CLI: run agent + judges against a dataset
├── datasets.yaml       # Dataset registry
├── judges/             # LLM-as-judge evaluators (correctness, scope)
├── prompts/            # Versioned agent system prompts
└── datasets/<name>/    # evaluation.xml (source) + examples/<name>.csv
```

Add the eval-only dependencies to the `dev` dependency group in
`pyproject.toml` when you scaffold it (the skill lists the exact versions), then
`uv sync --group dev`.
