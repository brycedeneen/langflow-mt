"""Tests for adp_worker_identification_tools — build_worker_identification_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_identification_tools import (
    PATH_ADD_GOVERNMENT_ID,
    PATH_CHANGE_GOVERNMENT_ID,
    build_add_government_id_event,
    build_change_government_id_event,
    build_worker_identification_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_add_government_id_event():
    body = build_add_government_id_event(
        associate_oid="G3ABC",
        id_value="123-45-6789",
        name_code="SSN",
        country_code="US",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"] == {"associateOID": "G3ABC"}
    gid = event["data"]["transform"]["worker"]["person"]["governmentID"]
    assert gid["idValue"] == "123-45-6789"
    assert gid["nameCode"] == {"codeValue": "SSN"}
    assert gid["countryCode"] == "US"


def test_build_change_government_id_event_has_item_id_in_context_and_transform():
    body = build_change_government_id_event(
        associate_oid="G3ABC",
        government_id_item_id="GID-1",
        id_value="987-65-4321",
    )
    event = body["events"][0]
    ctx = event["data"]["eventContext"]["worker"]
    assert ctx["person"]["governmentID"] == {"itemID": "GID-1"}
    gid = event["data"]["transform"]["worker"]["person"]["governmentID"]
    assert gid["itemID"] == "GID-1"
    assert gid["idValue"] == "987-65-4321"


@pytest.mark.asyncio
async def test_build_tools_returns_two_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_identification_tools(conn, cache)
    assert {t.name for t in tools} == {
        "add_employee_government_id",
        "change_employee_government_id",
    }


@pytest.mark.asyncio
async def test_tool_routes_to_correct_paths():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "R-1"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_identification_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_identification_tools.build_mtls_httpx_client", fake_client):
        await tools["add_employee_government_id"].ainvoke({
            "associate_oid": "G3ABC", "id_value": "111-11-1111", "name_code": "SSN",
        })
        await tools["change_employee_government_id"].ainvoke({
            "associate_oid": "G3ABC", "government_id_item_id": "GID-1", "id_value": "222-22-2222",
        })

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_ADD_GOVERNMENT_ID in u for u in posted_urls)
    assert any(PATH_CHANGE_GOVERNMENT_ID in u for u in posted_urls)


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_identification_tools(conn, cache)
    tool = next(t for t in tools if t.name == "add_employee_government_id")

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"message": "unauthorized"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_identification_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_identification_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke({
            "associate_oid": "G3ABC", "id_value": "111-11-1111", "name_code": "SSN",
        })

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
