"""Regression tests for the starter's outbound request boundary."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from example_server import utils


@pytest.mark.parametrize(
    "path",
    [
        "http://169.254.169.254/latest/meta-data",
        "https://localhost/admin",
        "//127.0.0.1/admin",
        "/absolute/path",
        "../admin",
        "datasets/../../admin",
        "%2e%2e/admin",
        "%252e%252e/admin",
        "%2f%2f127.0.0.1/admin",
        "datasets?target=http://127.0.0.1",
        "datasets#fragment",
        "\\\\127.0.0.1\\admin",
        "",
    ],
)
def test_validate_relative_path_rejects_destination_override(path: str) -> None:
    with pytest.raises(ValueError, match="relative API path"):
        utils._validate_relative_path(path)


def test_validate_relative_path_accepts_expected_api_path() -> None:
    assert utils._validate_relative_path("datasets/search") == "datasets/search"


class _FakeClient:
    """Capture client policy while returning a controlled upstream response."""

    init_kwargs: dict[str, Any] = {}
    response = httpx.Response(200, json={"results": []})

    def __init__(self, **kwargs: Any) -> None:
        type(self).init_kwargs = kwargs

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    class _Stream:
        def __init__(self, response: httpx.Response) -> None:
            self.response = response

        async def __aenter__(self) -> httpx.Response:
            return self.response

        async def __aexit__(self, *args: object) -> None:
            return None

    def stream(self, method: str, path: str, **kwargs: Any) -> _Stream:
        self.response.request = httpx.Request(
            method, f"https://api.example.gov/v1/{path}"
        )
        return self._Stream(self.response)


@pytest.mark.asyncio
async def test_fetch_json_uses_fixed_origin_and_safe_client_policy(monkeypatch) -> None:
    monkeypatch.setattr(utils.httpx, "AsyncClient", _FakeClient)

    assert await utils.fetch_json("datasets", params={"q": "health"}) == {"results": []}
    assert _FakeClient.init_kwargs["base_url"] == utils.API_BASE_URL
    assert _FakeClient.init_kwargs["follow_redirects"] is False
    assert _FakeClient.init_kwargs["trust_env"] is False


@pytest.mark.asyncio
async def test_fetch_json_does_not_send_rejected_path(monkeypatch) -> None:
    class UnexpectedClient:
        def __init__(self, **kwargs: Any) -> None:
            raise AssertionError("HTTP client must not be created for rejected input")

    monkeypatch.setattr(utils.httpx, "AsyncClient", UnexpectedClient)

    with pytest.raises(ValueError, match="relative API path"):
        await utils.fetch_json("http://169.254.169.254/latest/meta-data")


@pytest.mark.asyncio
async def test_upstream_error_does_not_expose_sensitive_response(
    monkeypatch, caplog
) -> None:
    sensitive = "SSN 123-45-6789 DOB 1940-01-01 token=secret"
    _FakeClient.response = httpx.Response(500, text=sensitive)
    monkeypatch.setattr(utils.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(utils.UpstreamServiceError) as captured:
        await utils.fetch_json("datasets")

    message = str(captured.value)
    assert message == "Upstream service returned status 500."
    assert sensitive not in message
    assert sensitive not in caplog.text


@pytest.mark.asyncio
async def test_invalid_json_is_sanitized(monkeypatch) -> None:
    sensitive = "not-json SSN 123-45-6789"
    _FakeClient.response = httpx.Response(200, content=sensitive)
    monkeypatch.setattr(utils.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(utils.UpstreamServiceError) as captured:
        await utils.fetch_json("datasets")

    assert str(captured.value) == "Upstream service returned invalid JSON."
    assert sensitive not in str(captured.value)
