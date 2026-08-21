"""Example tool — replace this with a real tool for your service.

This is the canonical one-tool-per-file pattern:
  - the module exposes a single `register(mcp)` function,
  - inside it, one `@mcp.tool`-decorated function is defined,
  - the decorated function is async (so I/O doesn't block the server),
  - annotations describe the tool's behavior to the client.

Tool design tips for federal datasets:
  - Return dicts/lists with consistent keys; let the LLM narrate the data.
  - State the data's update frequency and "as-of" date in the docstring.
  - Expose pagination (see `PaginationParams` / `paginate`) for list results.
  - Give errors an *actionable* message ("try filter=X"), not a raw stack trace.
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastmcp import FastMCP

from example_server.models import PaginationParams, ResponseFormat
from example_server.utils import fetch_json, paginate


def register(mcp: FastMCP) -> None:
    """Register the example tool with the MCP server."""

    @mcp.tool(
        name="example_search_datasets",
        annotations={
            "title": "Search Datasets (example)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def example_search_datasets(
        query: Annotated[str, "Keywords to search dataset titles and descriptions."],
        pagination: PaginationParams | None = None,
        response_format: Annotated[
            ResponseFormat,
            "Return machine-readable JSON (default) or human-readable Markdown.",
        ] = ResponseFormat.JSON,
    ) -> dict[str, Any] | str:
        """Search federal datasets matching a query string. (STUB — replace me.)

        This stub shows the shape of a real tool without calling a live API.
        Swap the body for an actual request using `fetch_json(...)`; a worked
        pattern is included below in a comment.

        Args:
            query: What to search for.
            pagination: Optional limit/offset (defaults to limit=20, offset=0).
            response_format: "json" or "markdown".

        Returns:
            A pagination envelope (JSON) or a Markdown summary of the matches.
        """
        pagination = pagination or PaginationParams()

        # ── Replace everything below with a real API call ────────────────────
        #
        # from example_server.config import settings
        #
        # try:
        #     payload = await fetch_json(
        #         "https://api.example.gov/v1/datasets",
        #         params={"q": query, "rows": pagination.limit,
        #                 "start": pagination.offset},
        #         headers={"X-API-Key": settings.example_api_key},
        #     )
        # except httpx.HTTPStatusError as exc:
        #     return {
        #         "error": f"API returned {exc.response.status_code}.",
        #         "hint": "Check your API key and that the query isn't empty.",
        #     }
        # results = payload.get("results", [])
        #
        # ─────────────────────────────────────────────────────────────────────

        # Placeholder data so the template runs out-of-the-box:
        results = [
            {"id": f"dataset-{i}", "title": f"Example result {i} for '{query}'"}
            for i in range(1, 6)
        ]

        page = paginate(results, pagination.limit, pagination.offset)

        if response_format is ResponseFormat.MARKDOWN:
            lines = [f"# Datasets matching '{query}'", ""]
            lines += [f"- **{r['title']}** (`{r['id']}`)" for r in page["items"]]
            lines.append("")
            lines.append(
                f"_Showing {page['count']} of {page['total']}._"
                + (f" Next offset: {page['next_offset']}." if page["has_more"] else "")
            )
            return "\n".join(lines)

        return page

    # Keep httpx + fetch_json imported so the commented example above is
    # copy-paste ready (remove these once you wire in the real API call).
    _ = (httpx, fetch_json)
