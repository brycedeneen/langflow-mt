"""Tests for adp_time_cards_tools module-level builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_time_cards_tools import (
    PATH_MODIFY,
    build_time_cards_tools,
    build_time_entries_modify_event,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_event_with_work_assignment():
    body = build_time_entries_modify_event(
        associate_oid="G3ABC",
        work_assignment_id="WA-1",
        time_entries=[
            {"entryTypeCode": {"codeValue": "hoursEntry"}, "entryDate": "2024-01-02", "timeDuration": "PT8H"},
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "workAssignmentID": "WA-1"}
    assert event["data"]["transform"]["timeEntries"][0]["timeDuration"] == "PT8H"


def test_build_event_without_work_assignment():
    body = build_time_entries_modify_event(associate_oid="G3ABC", time_entries=[])
    assert body["events"][0]["data"]["eventContext"] == {"associateOID": "G3ABC"}
    assert body["events"][0]["data"]["transform"]["timeEntries"] == []


def test_tools_disabled_empty():
    tools = build_time_cards_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert tools == []


@pytest.mark.asyncio
async def test_tool_routes_correct_path():
    client = MagicMock()
    response = httpx.Response(200, json={"ok": True})
    client.request = AsyncMock(return_value=response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_time_cards_tools.build_mtls_httpx_client", fake_client):
        tools = build_time_cards_tools(
            _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        await tools[0].ainvoke(
            {"associate_oid": "G3ABC", "work_assignment_id": "WA-1", "time_entries": []},
        )

    called_url = client.request.call_args[1]["url"]
    assert called_url.endswith(PATH_MODIFY)


def test_path_constant():
    assert PATH_MODIFY == "/events/time/v2/time-entries.modify"
