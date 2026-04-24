"""Tests for ADPWorkerBusinessCommunicationToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_business_communication_tools import (
    ADPWorkerBusinessCommunicationToolsComponent,
    build_business_communication_event,
    event_path,
)


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerBusinessCommunicationToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
async def test_build_tools_disabled_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_one_tool(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert len(tools) == 1
    assert tools[0].name == "manage_worker_business_communication"


@pytest.mark.asyncio
async def test_manage_routes_correct_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke(
            {
                "action": "add",
                "channel": "email",
                "associate_oid": "G3ABC",
                "email_uri": "w@adp.com",
            },
        )

    assert mock_post.call_args.kwargs["path"] == "/events/hr/v1/worker.business-communication.email.add"


@pytest.mark.asyncio
async def test_manage_remove_without_id_returns_validation(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock()

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = tools[0]
        result = await tool.ainvoke(
            {"action": "remove", "channel": "fax", "associate_oid": "G3ABC"},
        )

    assert result["status_code"] == 422
    mock_post.assert_not_called()
