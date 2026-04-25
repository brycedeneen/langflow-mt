"""Tests for adp_job_requisitions_tools — build_job_requisitions_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_job_requisitions_tools import (
    PATH_DETAIL,
    PATH_LIST,
    build_job_requisitions_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- _fetch_requisitions helper -------------


@pytest.mark.asyncio
async def test_fetch_happy_path():
    conn = _make_connection()
    fake_response = httpx.Response(200, json={"jobRequisitions": []})
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    with patch(
        "lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ):
        tools = build_job_requisitions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        tool = tools[0]
        result = await tool.ainvoke({})

    assert result == {"jobRequisitions": []}


@pytest.mark.asyncio
async def test_fetch_401_retries():
    conn = _make_connection()
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_client = MagicMock()
    mock_client.request = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):  # noqa: ARG001
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch(
        "lfx.components.adp.adp_job_requisitions_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        tools = build_job_requisitions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({})

    assert mock_client.request.call_count == 2


# ------------- tool routing -------------


@pytest.mark.asyncio
async def test_list_without_params():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_requisitions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({})

    call_kwargs = mock_client.request.call_args.kwargs
    assert PATH_LIST in call_kwargs.get("url", "")
    # No filter params were provided — params should be None or an empty dict.
    assert not call_kwargs.get("params")


@pytest.mark.asyncio
async def test_list_with_filter_and_paging():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_requisitions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke(
            {
                "$filter": "requisitionStatusCode/codeValue eq 'Open'",
                "$skip": 0,
                "$top": 25,
            },
        )

    call_kwargs = mock_client.request.call_args.kwargs
    assert call_kwargs.get("params") == {
        "$filter": "requisitionStatusCode/codeValue eq 'Open'",
        "$skip": 0,
        "$top": 25,
    }


@pytest.mark.asyncio
async def test_detail_routes_to_detail_path():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_job_requisitions_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_requisitions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({"job_requisition_id": "REQ-7"})

    call_kwargs = mock_client.request.call_args.kwargs
    assert "REQ-7" in call_kwargs.get("url", "")


def test_build_tools_single_read_tool():
    tools = build_job_requisitions_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert len(tools) == 1
    assert tools[0].name == "get_job_requisitions"


def test_expected_path_constants():
    assert PATH_LIST == "/staffing/v1/job-requisitions"
    assert PATH_DETAIL == "/staffing/v1/job-requisitions/{job_requisition_id}"
