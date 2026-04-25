"""Tests for adp_data_collection_entries_tools — build_data_collection_entries_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_data_collection_entries_tools import (
    PATH_PROCESS,
    PATH_RESULT,
    build_data_collection_entries_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@pytest.mark.asyncio
async def test_get_result_routes_with_event_id():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_data_collection_entries_tools.build_mtls_httpx_client", fake_client):
        tools = build_data_collection_entries_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_data_collection_event_result").ainvoke({"event_id": "EV-1"})

    call_url = mock_client.request.call_args.kwargs.get("url", "")
    assert PATH_RESULT.format(event_id="EV-1") in call_url


def test_process_gated():
    tools = build_data_collection_entries_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False,
    )
    assert {t.name for t in tools} == {"get_data_collection_event_result"}

    tools = build_data_collection_entries_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    assert "process_data_collection_entries" in {t.name for t in tools}


@pytest.mark.asyncio
async def test_process_posts_event_body():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_data_collection_entries_tools.build_mtls_httpx_client", fake_client):
        tools = build_data_collection_entries_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        await next(t for t in tools if t.name == "process_data_collection_entries").ainvoke(
            {"event_body": {"events": [{"data": {}}]}},
        )

    call_kwargs = mock_client.request.call_args.kwargs
    assert PATH_PROCESS in call_kwargs.get("url", "")
    assert call_kwargs.get("json") == {"events": [{"data": {}}]}
