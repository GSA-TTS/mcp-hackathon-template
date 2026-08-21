"""Example resource — replace or supplement with your own.

Resource URI conventions:
  - Use a consistent scheme per service, e.g. "census://", "example://".
  - Static resources (no parameters):  @mcp.resource("scheme://path")
  - Parameterized resources:           @mcp.resource("scheme://path/{param}")
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the example resource(s) with the MCP server."""

    @mcp.resource("example://info/server")
    def server_info() -> str:
        """Basic information about this MCP server.

        Replace with documentation specific to the API(s) you expose — a data
        dictionary, field reference, or usage notes the model can read directly.
        """
        return (
            "Example MCP Server\n\n"
            "This is a starter server for the GSA MCP hackathon.\n"
            "Replace this resource, the example tool, and the package name with\n"
            "your own service. See the repo README to get started."
        )

    @mcp.resource("example://docs/{topic}")
    def docs(topic: str) -> str:
        """Parameterized docs lookup (example of a templated resource URI)."""
        pages = {
            "getting-started": "Clone, `uv sync`, then `uv run python main.py`.",
            "deploy": "See deploy/ for IBM and Databricks deployment kits.",
        }
        return pages.get(topic, f"No documentation found for topic '{topic}'.")
