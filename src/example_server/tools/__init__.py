"""Tools submodule — one tool per file.

Each tool module (e.g. `example_tool.py`) exposes a `register(mcp)` function
that attaches its `@mcp.tool`-decorated function to the server. This file
aggregates them into a single `register_tools(mcp)` that `app.py` calls.

To add a tool:
  1. Create `tools/<your_tool>.py` with a `register(mcp)` function.
  2. Import it below and call `<your_tool>.register(mcp)` inside register_tools.
"""

from __future__ import annotations

from example_server.tools import example_tool


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    example_tool.register(mcp)


__all__ = ["register_tools"]
