"""Shared helpers: HTTP client, response formatting, and pagination.

Import these from your tool modules instead of re-implementing them. Keeping
I/O and formatting here keeps each tool file focused on its own logic.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

# Federal APIs can be slow or intermittently unresponsive — always use an
# explicit timeout. Bump this for large exports.
DEFAULT_TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 5_000_000

# Keep outbound origins operator-controlled. Do not replace this with a tool
# argument; add another narrowly scoped client when integrating another API.
API_BASE_URL = "https://api.example.gov/v1/"


class UpstreamServiceError(RuntimeError):
    """Sanitized external-service failure safe to return to an MCP client."""


def _validate_relative_path(path: str) -> str:
    """Reject paths that could select or escape the configured API origin."""
    parsed = urlsplit(path)
    decoded_path = parsed.path
    for _ in range(3):
        decoded = unquote(decoded_path)
        if decoded == decoded_path:
            break
        decoded_path = decoded
    segments = decoded_path.replace("\\", "/").split("/")
    if (
        not path
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or decoded_path.startswith(("/", "\\"))
        or any(segment in {".", ".."} for segment in segments)
    ):
        raise ValueError("path must be a relative API path without a query or fragment")
    return path


async def fetch_json(
    path: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET a path from the fixed API origin and return parsed JSON.

    Raises:
        ValueError: if path could select or escape the configured API origin.
        UpstreamServiceError: with a sanitized message for external failures.
    """
    safe_path = _validate_relative_path(path)
    try:
        async with httpx.AsyncClient(
            base_url=API_BASE_URL,
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET", safe_path, params=params, headers=headers
            ) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise UpstreamServiceError(
                            "Upstream response exceeded the size limit."
                        )
                return json.loads(content)
    except UpstreamServiceError:
        raise
    except httpx.HTTPStatusError as exc:
        raise UpstreamServiceError(
            f"Upstream service returned status {exc.response.status_code}."
        ) from None
    except (httpx.DecodingError, json.JSONDecodeError, UnicodeDecodeError):
        raise UpstreamServiceError("Upstream service returned invalid JSON.") from None
    except httpx.RequestError:
        raise UpstreamServiceError("Upstream service request failed.") from None


def paginate(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    """Slice a list and return a standard pagination envelope.

    Returns a dict with `total`, `count`, `offset`, `items`, `has_more`, and
    `next_offset` — the shape recommended in the MCP best-practices guide.
    """
    total = len(items)
    window = items[offset : offset + limit]
    next_offset = offset + len(window)
    return {
        "total": total,
        "count": len(window),
        "offset": offset,
        "items": window,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
    }
