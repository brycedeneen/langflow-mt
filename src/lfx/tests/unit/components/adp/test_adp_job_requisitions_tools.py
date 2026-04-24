"""Tests for ADPJobRequisitionsToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_job_requisitions_tools import (
    ADPJobRequisitionsToolsComponent,
    PATH_DETAIL,
    PATH_LIST,
)


def _make_component(connection) -> ADPJobRequisitionsToolsComponent:
    return ADPJobRequisitionsToolsComponent(connection=connection)


# ------------- _call helper -------------


@pytest.mark.asyncio
async def test_call_happy_path(adp_connection):
    c = _make_component(adp_connection)
    fake_response = httpx.Response(200, json={"jobRequisitions": []})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._call(adp_connection, path=PATH_LIST)

    assert result == {"jobRequisitions": []}


@pytest.mark.asyncio
async def test_call_401_retries(adp_connection):
    c = _make_component(adp_connection)
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_job_requisitions_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        await c._call(adp_connection, path=PATH_LIST)

    assert mock_exec.call_count == 2


# ------------- tool routing -------------


@pytest.mark.asyncio
async def test_list_without_params(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke({})

    assert mock_call.call_args.kwargs["path"] == PATH_LIST
    assert mock_call.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_list_with_filter_and_paging(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke(
            {
                "$filter": "requisitionStatusCode/codeValue eq 'Open'",
                "$skip": 0,
                "$top": 25,
            },
        )

    params = mock_call.call_args.kwargs["params"]
    assert params == {
        "$filter": "requisitionStatusCode/codeValue eq 'Open'",
        "$skip": 0,
        "$top": 25,
    }


@pytest.mark.asyncio
async def test_detail_routes_to_detail_path(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke({"job_requisition_id": "REQ-7"})

    assert mock_call.call_args.kwargs["path"] == PATH_DETAIL.format(job_requisition_id="REQ-7")
    # Detail path shouldn't include query params from the list-only fields.
    assert "params" not in mock_call.call_args.kwargs or mock_call.call_args.kwargs.get("params") is None


@pytest.mark.asyncio
async def test_build_tools_single_read_tool(adp_connection):
    c = _make_component(adp_connection)
    tools = await c.build_tools()
    assert len(tools) == 1
    assert tools[0].name == "get_job_requisitions"


def test_expected_path_constants():
    assert PATH_LIST == "/staffing/v1/job-requisitions"
    assert PATH_DETAIL == "/staffing/v1/job-requisitions/{job_requisition_id}"
