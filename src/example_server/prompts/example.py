"""Example prompt — replace or supplement with your own.

A prompt function returns a string (rendered as a user message) or a list of
messages for a multi-turn starter. Its parameters become input fields in the
client UI. Keep prompts dataset-agnostic where possible so they compose well.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the example prompt with the MCP server."""

    @mcp.prompt()
    def explore_dataset(dataset_name: str, goal: str = "summarize") -> str:
        """Start an exploration session for a named dataset.

        Args:
            dataset_name: Human-readable name of the dataset to explore.
            goal: What to do — e.g. "summarize", "find trends", "compare years".
        """
        return (
            f"I want to {goal} the {dataset_name} dataset. "
            "Please start by describing what data is available, "
            "then help me investigate it step by step."
        )
