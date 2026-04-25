"""Tests for adp_worker_biological_tools — build_worker_biological_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_biological_tools import (
    ATTR_PATH,
    PATH_BIRTH_DATE,
    build_change_biological_attribute_event,
    build_change_birth_date_event,
    build_worker_biological_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_change_birth_date_event():
    body = build_change_birth_date_event(associate_oid="G3ABC", birth_date="1990-01-02")
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["birthDate"] == "1990-01-02"


def test_build_change_biological_attribute_event_gender():
    path, body = build_change_biological_attribute_event(
        attribute_type="gender", associate_oid="G3ABC", code_value="Male",
    )
    assert path == ATTR_PATH["gender"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["genderCode"] == {"codeValue": "Male"}


def test_build_change_biological_attribute_event_race():
    path, body = build_change_biological_attribute_event(
        attribute_type="race", associate_oid="G3ABC", code_value="Asian",
    )
    assert path == ATTR_PATH["race"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["raceCode"] == {"codeValue": "Asian"}


@pytest.mark.asyncio
async def test_build_tools_returns_two_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_biological_tools(conn, cache)
    assert {t.name for t in tools} == {"change_employee_birth_date", "change_employee_biological_attribute"}


@pytest.mark.asyncio
async def test_tools_route_to_paths():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_biological_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_biological_tools.build_mtls_httpx_client", fake_client):
        await tools["change_employee_birth_date"].ainvoke(
            {"associate_oid": "A", "birth_date": "1990-01-01"},
        )
        await tools["change_employee_biological_attribute"].ainvoke(
            {"attribute_type": "gender_identity", "associate_oid": "A", "code_value": "NonBinary"},
        )

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_BIRTH_DATE in u for u in posted_urls)
    assert any(ATTR_PATH["gender_identity"] in u for u in posted_urls)


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_biological_tools(conn, cache)
    tool = next(t for t in tools if t.name == "change_employee_birth_date")

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

    with patch("lfx.components.adp.adp_worker_biological_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_biological_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke({"associate_oid": "A", "birth_date": "1990-01-01"})

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
