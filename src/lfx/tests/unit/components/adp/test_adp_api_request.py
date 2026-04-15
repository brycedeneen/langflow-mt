from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp.adp_api_request import ADPAPIRequestComponent


def _make_component(connection, **overrides) -> ADPAPIRequestComponent:
    defaults = {
        "connection": connection,
        "endpoint": "Workers",
        "custom_path": "",
        "resource_id": "",
        "method": "GET",
        "query_params": None,
        "body": [],
        "result_mode": "Top 20",
        "timeout": 30,
    }
    defaults.update(overrides)
    return ADPAPIRequestComponent(**defaults)


def test_resolve_path_workers_list(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers")
    assert c._resolve_path() == "/hr/v2/workers"


def test_resolve_path_workers_by_id(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", resource_id="G3ABC")
    assert c._resolve_path() == "/hr/v2/workers/G3ABC"


def test_resolve_path_pay_statements_requires_id(adp_connection):
    c = _make_component(adp_connection, endpoint="Pay Statements", resource_id="G3ABC")
    assert c._resolve_path() == "/payroll/v1/workers/G3ABC/pay-statements"


def test_resolve_path_pay_statements_missing_id_raises(adp_connection):
    c = _make_component(adp_connection, endpoint="Pay Statements", resource_id="")
    with pytest.raises(ValueError, match="resource_id is required"):
        c._resolve_path()


def test_resolve_path_custom(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Other (custom path)",
        custom_path="/staffing/v1/positions",
    )
    assert c._resolve_path() == "/staffing/v1/positions"


def test_resolve_path_custom_missing_raises(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Other (custom path)",
        custom_path="",
    )
    with pytest.raises(ValueError, match="custom_path is required"):
        c._resolve_path()


@pytest.mark.asyncio
async def test_make_request_top_20_single_call(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    fake_response = httpx.Response(200, json={"workers": [{"id": 1}, {"id": 2}]})

    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", new=fake_build_client), \
         patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)) as mock_exec:
        result = await c.make_api_request()

    assert mock_exec.call_count == 1
    # Top 20 must include $top=20
    call_kwargs = mock_exec.call_args.kwargs
    assert call_kwargs["params"]["$top"] == 20
    assert "$skip" not in call_kwargs["params"]
    assert result.data["result"]["workers"] == [{"id": 1}, {"id": 2}]
    assert result.data["status_code"] == 200


@pytest.mark.asyncio
async def test_make_request_all_paginates_until_short_page(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="All")

    responses = [
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100)]}),
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100, 150)]}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", new=fake_build_client), \
         patch.object(c, "_execute_request", new=mock_exec):
        result = await c.make_api_request()

    assert mock_exec.call_count == 2
    assert len(result.data["result"]["workers"]) == 150
    # Verify $top / $skip progression
    skip_values = [call.kwargs["params"].get("$skip", 0) for call in mock_exec.call_args_list]
    assert skip_values == [0, 100]


@pytest.mark.asyncio
async def test_make_request_all_stops_on_short_page(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="All")
    responses = [
        httpx.Response(200, json={"workers": [{"id": i} for i in range(50)]}),  # less than 100 → stop
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", new=fake_build_client), \
         patch.object(c, "_execute_request", new=mock_exec):
        result = await c.make_api_request()
    assert mock_exec.call_count == 1
    assert len(result.data["result"]["workers"]) == 50


@pytest.mark.asyncio
async def test_make_request_401_triggers_force_refresh_and_retry(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"workers": [{"id": 1}]}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "new-token"  # noqa: S105

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", new=fake_build_client), \
         patch.object(c, "_execute_request", new=mock_exec), \
         patch("lfx.components.adp.adp_api_request.fetch_token", new=AsyncMock(side_effect=fake_force_refresh)):
        result = await c.make_api_request()

    assert mock_exec.call_count == 2
    # Second call must use the refreshed token
    second_call_headers = mock_exec.call_args_list[1].kwargs["headers"]
    assert second_call_headers["Authorization"] == "Bearer new-token"
    assert result.data["status_code"] == 200


@pytest.mark.asyncio
async def test_make_request_401_twice_still_fails(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(401, json={"error": "still-bad"}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", new=fake_build_client), \
         patch.object(c, "_execute_request", new=mock_exec), \
         patch("lfx.components.adp.adp_api_request.fetch_token", new=AsyncMock()):
        result = await c.make_api_request()

    assert result.data["status_code"] == 401
    assert mock_exec.call_count == 2


@pytest.mark.asyncio
async def test_make_request_post_sends_body(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Workers",
        method="POST",
        body=[{"key": "name", "value": "Alice"}, {"key": "age", "value": "30"}],
        result_mode="Top 20",
    )

    captured: dict = {}

    @asynccontextmanager
    async def fake_client(_conn, *, timeout=30):  # noqa: ARG001
        yield MagicMock()

    async def fake_execute(_client, *, method, url, headers, params, json_body, timeout):  # noqa: ARG001
        captured["method"] = method
        captured["json_body"] = json_body
        return httpx.Response(200, json={"ok": True})

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", side_effect=fake_client), \
         patch.object(c, "_execute_request", new=AsyncMock(side_effect=fake_execute)):
        await c.make_api_request()

    assert captured["method"] == "POST"
    assert captured["json_body"] == {"name": "Alice", "age": "30"}


@pytest.mark.asyncio
async def test_make_request_get_sends_no_body(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Workers",
        method="GET",
        body=[{"key": "ignored", "value": "x"}],
        result_mode="Top 20",
    )

    captured: dict = {}

    @asynccontextmanager
    async def fake_client(_conn, *, timeout=30):  # noqa: ARG001
        yield MagicMock()

    async def fake_execute(_client, *, method, url, headers, params, json_body, timeout):  # noqa: ARG001
        captured["json_body"] = json_body
        return httpx.Response(200, json={"workers": []})

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", side_effect=fake_client), \
         patch.object(c, "_execute_request", new=AsyncMock(side_effect=fake_execute)):
        await c.make_api_request()

    assert captured["json_body"] is None


@pytest.mark.asyncio
async def test_make_request_all_stops_on_empty_page(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="All")
    responses = [
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100)]}),
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100, 200)]}),
        httpx.Response(200, json={"workers": []}),
    ]
    mock_exec = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_client(_conn, *, timeout=30):  # noqa: ARG001
        yield MagicMock()

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", side_effect=fake_client), \
         patch.object(c, "_execute_request", new=mock_exec):
        result = await c.make_api_request()

    assert mock_exec.call_count == 3
    assert len(result.data["result"]["workers"]) == 200
    skip_values = [call.kwargs["params"].get("$skip", 0) for call in mock_exec.call_args_list]
    assert skip_values == [0, 100, 200]


@pytest.mark.asyncio
async def test_make_request_invokes_ssrf_validation(adp_connection, monkeypatch):
    c = _make_component(adp_connection, endpoint="Workers")
    called: dict = {}

    def fake_validate(url, *, warn_only):
        called["url"] = url
        called["warn_only"] = warn_only

    monkeypatch.setattr("lfx.components.adp.adp_api_request.validate_url_for_ssrf", fake_validate)

    @asynccontextmanager
    async def fake_client(_conn, *, timeout=30):  # noqa: ARG001
        yield MagicMock()

    with patch("lfx.components.adp.adp_api_request.build_mtls_httpx_client", side_effect=fake_client), \
         patch.object(c, "_execute_request", new=AsyncMock(return_value=httpx.Response(200, json={"workers": []}))):
        await c.make_api_request()

    assert called["url"].startswith("https://api.adp.com/hr/v2/workers")
    assert called["warn_only"] is True
