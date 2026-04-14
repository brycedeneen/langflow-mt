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
