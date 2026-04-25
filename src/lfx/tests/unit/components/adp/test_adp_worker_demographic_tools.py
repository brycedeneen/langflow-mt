"""Tests for build_worker_demographic_tools (pure-write tile)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_demographic_tools import (
    NAME_PATH,
    PATH_PREFERRED_GENDER_PRONOUN,
    STATUS_PATH,
    build_change_demographic_status_event,
    build_change_name_event,
    build_change_preferred_gender_pronoun_event,
    build_worker_demographic_tools,
)


def _make_connection(*, access_token="T1", api_base_url="https://api.adp.com"):
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_change_name_event_legal():
    path, body = build_change_name_event(
        name_type="legal", associate_oid="G3ABC",
        given_name="Jane", family_name="Doe",
    )
    assert path == NAME_PATH["legal"]
    legal = body["events"][0]["data"]["transform"]["worker"]["person"]["legalName"]
    assert legal == {"givenName": "Jane", "familyName1": "Doe"}


def test_build_change_name_event_preferred_paths():
    path, _body = build_change_name_event(name_type="preferred", associate_oid="G3ABC", given_name="J")
    assert path == NAME_PATH["preferred"]


def test_build_change_demographic_status_event_marital():
    path, body = build_change_demographic_status_event(
        status_type="marital", associate_oid="G3ABC", code_value="Married",
    )
    assert path == STATUS_PATH["marital"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["maritalStatusCode"] == {"statusCode": {"codeValue": "Married"}}


def test_build_change_demographic_status_event_military_classification():
    path, body = build_change_demographic_status_event(
        status_type="military_classification", associate_oid="G3ABC", code_value="Veteran",
    )
    assert path == STATUS_PATH["military_classification"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["militaryClassificationCode"] == {"statusCode": {"codeValue": "Veteran"}}


def test_build_change_preferred_gender_pronoun_event():
    body = build_change_preferred_gender_pronoun_event(
        associate_oid="G3ABC", pronoun_code="They/Them",
    )
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["preferredGenderPronounCode"] == {"codeValue": "They/Them"}


@pytest.mark.asyncio
async def test_build_tools_returns_three_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_demographic_tools(conn, cache)
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {
        "change_employee_name",
        "change_employee_demographic_status",
        "change_employee_preferred_gender_pronoun",
    }


@pytest.mark.asyncio
async def test_tools_route_to_all_paths():
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

    tools = {t.name: t for t in build_worker_demographic_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_demographic_tools.build_mtls_httpx_client", fake_client):
        await tools["change_employee_name"].ainvoke(
            {"name_type": "birth", "associate_oid": "A", "given_name": "Birth"},
        )
        await tools["change_employee_demographic_status"].ainvoke(
            {"status_type": "military_status", "associate_oid": "A", "code_value": "Active"},
        )
        await tools["change_employee_preferred_gender_pronoun"].ainvoke(
            {"associate_oid": "A", "pronoun_code": "She/Her"},
        )

    calls = client.request.call_args_list
    assert len(calls) == 3
    posted_urls = [c.kwargs.get("url") or c.args[1] for c in calls]
    assert any(NAME_PATH["birth"] in u for u in posted_urls)
    assert any(STATUS_PATH["military_status"] in u for u in posted_urls)
    assert any(PATH_PREFERRED_GENDER_PRONOUN in u for u in posted_urls)


@pytest.mark.asyncio
async def test_writes_do_not_populate_cache():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_demographic_tools(conn, cache)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 204
    response.text = ""

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    # Use the preferred-gender-pronoun tool — all required fields are plain strings.
    pronoun_tool = next(t for t in tools if "pronoun" in t.name)

    with patch("lfx.components.adp.adp_worker_demographic_tools.build_mtls_httpx_client", fake_client):
        await pronoun_tool.ainvoke({"associate_oid": "G3ABC", "pronoun_code": "They/Them"})

    # Cache must be empty: writes never read from or write to the request cache.
    assert len(cache._entries) == 0
