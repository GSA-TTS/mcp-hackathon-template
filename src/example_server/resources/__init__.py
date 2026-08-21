"""Resources submodule — static/semi-static data the client can read directly.

Resources are addressable by URI and don't require a tool call. Good for data
dictionaries, reference tables (FIPS codes, agency acronyms), and schemas.

Each resource module exposes a `register(mcp)` function; this file aggregates
them into `register_resources(mcp)`.
"""

from __future__ import annotations

from example_server.resources import example


def register_resources(mcp) -> None:
    """Register all resources with the MCP server."""
    example.register(mcp)


__all__ = ["register_resources"]
