"""Pydantic models and enums for tool parameters and responses.

Typed parameters give MCP clients a precise schema, which helps the LLM call
your tools correctly. Prefer enums for closed sets of values and Pydantic
models for structured inputs/outputs.

These are illustrative — replace them with models for your own service.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResponseFormat(str, Enum):
    """How a tool should shape its return value.

    - JSON     → machine-readable dict/list (best for chaining tool calls)
    - MARKDOWN → human-readable text (best for direct display)
    """

    JSON = "json"
    MARKDOWN = "markdown"


class PaginationParams(BaseModel):
    """Reusable pagination inputs for list-style tools.

    Federal APIs almost always paginate. Expose these to the caller (or handle
    paging internally) and return `has_more` / `next_offset` in your response.
    """

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return (1–100).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip from the start of the result set.",
    )
