"""Tests for ADPWorkerAssignmentToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_assignment_tools import (
    ADPWorkerAssignmentToolsComponent,
    PATH_ORG_UNITS_MODIFY,
    PATH_REPORTS_TO_MODIFY,
    PATH_WORK_ASSIGNMENT_MODIFY,
    PATH_WORK_ASSIGNMENT_TERMINATE,
    build_change_org_units_event,
    build_change_reports_to_event,
    build_modify_work_assignment_event,
    build_terminate_work_assignment_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkerAssignmentToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_change_reports_to_event():
    body = build_change_reports_to_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        new_manager_associate_oid="G3MGR",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3EMP", "workAssignmentID": "WA-1"}
    assert event["data"]["transform"]["workAssignment"]["reportsTo"] == [{"associateOID": "G3MGR"}]


def test_build_change_org_units_event():
    body = build_change_org_units_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        organizational_units=[{"type_code": "Department", "name_code": "Engineering"}],
    )
    units = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]["assignedOrganizationalUnits"]
    assert units[0]["typeCode"] == {"codeValue": "Department"}
    assert units[0]["nameCode"] == {"codeValue": "Engineering"}


def test_build_modify_work_assignment_event_accepts_arbitrary_fields():
    body = build_modify_work_assignment_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        work_assignment_fields={"jobTitle": "Senior Engineer"},
    )
    wa = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]
    assert wa == {"jobTitle": "Senior Engineer"}


def test_build_terminate_work_assignment_event():
    body = build_terminate_work_assignment_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        termination_date="2026-06-01", comment="Position eliminated",
        reason_code="Position Eliminated",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"]["workAssignment"] == {"itemID": "WA-1"}
    assert event["data"]["transform"]["worker"]["workAssignment"] == {"terminationDate": "2026-06-01"}
    assert event["data"]["transform"]["comment"] == {"text": "Position eliminated"}
    assert event["data"]["transform"]["eventReasonCode"] == {"codeValue": "Position Eliminated"}


@pytest.mark.asyncio
async def test_build_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_four(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "change_employee_manager",
        "change_employee_organizational_units",
        "modify_employee_work_assignment",
        "terminate_employee_work_assignment",
    }


@pytest.mark.asyncio
async def test_tools_route_to_correct_paths(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"ok": True})
    with patch.object(c, "_post_event", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["change_employee_manager"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W",
             "new_manager_associate_oid": "M"},
        )
        await tools["change_employee_organizational_units"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "organizational_units": []},
        )
        await tools["modify_employee_work_assignment"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "work_assignment_fields": {}},
        )
        await tools["terminate_employee_work_assignment"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W"},
        )
    paths = [c.kwargs["path"] for c in mock_post.call_args_list]
    assert paths == [
        PATH_REPORTS_TO_MODIFY,
        PATH_ORG_UNITS_MODIFY,
        PATH_WORK_ASSIGNMENT_MODIFY,
        PATH_WORK_ASSIGNMENT_TERMINATE,
    ]
