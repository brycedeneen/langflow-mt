"""Tests for ADPWorkerIdentificationToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_identification_tools import (
    ADPWorkerIdentificationToolsComponent,
    PATH_ADD_GOVERNMENT_ID,
    PATH_CHANGE_GOVERNMENT_ID,
    build_add_government_id_event,
    build_change_government_id_event,
)


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerIdentificationToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_two_tools(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "add_employee_government_id",
        "change_employee_government_id",
    }


@pytest.mark.asyncio
async def test_tool_routes_to_correct_paths(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "R-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        add_t = next(t for t in tools if t.name == "add_employee_government_id")
        await add_t.ainvoke({
            "associate_oid": "G3ABC", "id_value": "111-11-1111", "name_code": "SSN",
        })
        chg = next(t for t in tools if t.name == "change_employee_government_id")
        await chg.ainvoke({
            "associate_oid": "G3ABC", "government_id_item_id": "GID-1", "id_value": "222-22-2222",
        })

    assert mock_post.call_args_list[0].kwargs["path"] == PATH_ADD_GOVERNMENT_ID
    assert mock_post.call_args_list[1].kwargs["path"] == PATH_CHANGE_GOVERNMENT_ID
