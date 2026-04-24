"""Tests for ADPWorkerDeploymentToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_deployment_tools import (
    ADPWorkerDeploymentToolsComponent,
    PATH_CHANGE_STANDARD_HOURS,
    PATH_CHANGE_WORKER_TYPE,
    build_change_standard_hours_event,
    build_change_worker_type_event,
)


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerDeploymentToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_change_standard_hours_event():
    body = build_change_standard_hours_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        hours_quantity=32.0,
        effective_date="2026-05-01",
        reason_code="Schedule Change",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"] == {
        "associateOID": "G3ABC",
        "workAssignment": {"itemID": "WA-1"},
    }
    sh = event["data"]["transform"]["workAssignment"]["standardHours"]
    assert sh["hoursQuantity"] == 32.0
    assert sh["unitCode"] == {"codeValue": "Hour"}
    assert sh["unitTimeCode"] == {"codeValue": "Weekly"}
    assert event["data"]["transform"]["effectiveDateTime"] == "2026-05-01"
    assert event["data"]["transform"]["eventReasonCode"] == {"codeValue": "Schedule Change"}


def test_build_change_worker_type_event():
    body = build_change_worker_type_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        worker_type_code="Contractor",
    )
    wa = body["events"][0]["data"]["transform"]["workAssignment"]
    assert wa["workerTypeCode"] == {"codeValue": "Contractor"}


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_two_tools(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "change_employee_standard_hours",
        "change_employee_worker_type",
    }


@pytest.mark.asyncio
async def test_tool_routes_to_correct_paths(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "R-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        hours = next(t for t in tools if t.name == "change_employee_standard_hours")
        await hours.ainvoke({
            "associate_oid": "G3ABC", "work_assignment_item_id": "WA-1", "hours_quantity": 40.0,
        })
        wtype = next(t for t in tools if t.name == "change_employee_worker_type")
        await wtype.ainvoke({
            "associate_oid": "G3ABC", "work_assignment_item_id": "WA-1", "worker_type_code": "Regular",
        })

    assert mock_post.call_args_list[0].kwargs["path"] == PATH_CHANGE_STANDARD_HOURS
    assert mock_post.call_args_list[1].kwargs["path"] == PATH_CHANGE_WORKER_TYPE
