"""Tests for adp_worker_business_communication_tools — build_worker_business_communication_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_business_communication_tools import (
    build_business_communication_event,
    build_worker_business_communication_tools,
    event_path,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_event_path_formatting():
    assert event_path("email", "add") == "/events/hr/v1/worker.business-communication.email.add"
    assert event_path("mobile", "change") == "/events/hr/v1/worker.business-communication.mobile.change"
    assert event_path("fax", "remove") == "/events/hr/v1/worker.business-communication.fax.remove"


def test_build_email_add():
    body = build_business_communication_event(
        action="add",
        channel="email",
        associate_oid="G3ABC",
        email_uri="Asciber@adp.com",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"worker": {"associateOID": "G3ABC"}}
    assert event["data"]["transform"] == {
        "worker": {"businessCommunication": {"email": {"emailUri": "Asciber@adp.com"}}},
    }


def test_build_phone_add():
    body = build_business_communication_event(
        action="add",
        channel="landline",
        associate_oid="G3ABC",
        area_dialing="973",
        dial_number="5553247",
    )
    landline = body["events"][0]["data"]["transform"]["worker"]["businessCommunication"]["landline"]
    assert landline == {"areaDialing": "973", "dialNumber": "5553247"}


def test_build_remove_requires_identifier():
    with pytest.raises(ValueError, match="requires item_id"):
        build_business_communication_event(
            action="remove",
            channel="mobile",
            associate_oid="G3ABC",
        )


def test_build_change_with_item_id():
    body = build_business_communication_event(
        action="change",
        channel="mobile",
        associate_oid="G3ABC",
        item_id="PH-1",
        dial_number="7133456",
    )
    mobile = body["events"][0]["data"]["transform"]["worker"]["businessCommunication"]["mobile"]
    assert mobile == {"itemID": "PH-1", "dialNumber": "7133456"}


def test_build_additional_fields_merged():
    body = build_business_communication_event(
        action="add",
        channel="pager",
        associate_oid="G3ABC",
        area_dialing="973",
        dial_number="5551212",
        additional_fields={"customField": "Foo"},
    )
    pager = body["events"][0]["data"]["transform"]["worker"]["businessCommunication"]["pager"]
    assert pager["customField"] == "Foo"


@pytest.mark.asyncio
async def test_build_tools_returns_one_tool():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_business_communication_tools(conn, cache)
    assert len(tools) == 1
    assert tools[0].name == "manage_worker_business_communication"


@pytest.mark.asyncio
async def test_manage_routes_correct_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = build_worker_business_communication_tools(conn, cache)
    tool = tools[0]

    with patch("lfx.components.adp.adp_worker_business_communication_tools.build_mtls_httpx_client", fake_client):
        await tool.ainvoke(
            {
                "action": "add",
                "channel": "email",
                "associate_oid": "G3ABC",
                "email_uri": "w@adp.com",
            },
        )

    posted_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert "/events/hr/v1/worker.business-communication.email.add" in posted_url


@pytest.mark.asyncio
async def test_manage_remove_without_id_returns_validation():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    client = AsyncMock(spec=httpx.AsyncClient)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = build_worker_business_communication_tools(conn, cache)
    tool = tools[0]

    with patch("lfx.components.adp.adp_worker_business_communication_tools.build_mtls_httpx_client", fake_client):
        result = await tool.ainvoke(
            {"action": "remove", "channel": "fax", "associate_oid": "G3ABC"},
        )

    assert result["status_code"] == 422
    client.request.assert_not_called()
