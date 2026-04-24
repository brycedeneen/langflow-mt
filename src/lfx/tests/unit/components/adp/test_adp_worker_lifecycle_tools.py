"""Tests for ADPWorkerLifecycleToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_lifecycle_tools import (
    ADPWorkerLifecycleToolsComponent,
    PATH_REHIRE,
    build_rehire_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkerLifecycleToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_rehire_event_minimum():
    body = build_rehire_event(
        associate_oid="G3ABC", work_assignment_item_id="WA-1", rehire_date="2026-05-01",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["associateOID"] == "G3ABC"
    assert event["data"]["eventContext"]["workAssignment"] == {"itemID": "WA-1"}
    worker = event["data"]["transform"]["worker"]
    assert worker["associateOID"] == "G3ABC"
    assert worker["workerDates"] == {"rehireDate": "2026-05-01"}
    assert worker["workAssignment"]["hireDate"] == "2026-05-01"
    assert event["data"]["transform"]["effectiveDateTime"] == "2026-05-01"


def test_build_rehire_event_with_rich_fields():
    body = build_rehire_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        rehire_date="2026-05-01",
        job_code="SWE-2",
        job_title="Senior Engineer",
        worker_type_code="Regular",
        work_location_name="Remote",
        department_name="Engineering",
        reports_to_associate_oid="G3MGR",
        annual_base_pay=150000.0,
        reason_code="Rehire",
    )
    wa = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]
    assert wa["jobCode"] == {"codeValue": "SWE-2"}
    assert wa["jobTitle"] == "Senior Engineer"
    assert wa["workerTypeCode"] == {"codeValue": "Regular"}
    assert wa["homeWorkLocation"] == {"nameCode": {"codeValue": "Remote"}}
    assert wa["homeOrganizationalUnits"][0]["nameCode"] == {"codeValue": "Engineering"}
    assert wa["reportsTo"] == [{"associateOID": "G3MGR"}]
    assert wa["baseRemuneration"]["annualRateAmount"]["amountValue"] == 150000.0
    assert body["events"][0]["data"]["transform"]["eventReasonCode"] == {"codeValue": "Rehire"}


def test_build_rehire_event_additional_fields_deep_merge():
    body = build_rehire_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        rehire_date="2026-05-01",
        department_name="Engineering",
        additional_worker_fields={
            "person": {"legalName": {"givenName": "Jane", "familyName1": "Doe"}},
        },
    )
    worker = body["events"][0]["data"]["transform"]["worker"]
    assert worker["person"]["legalName"] == {"givenName": "Jane", "familyName1": "Doe"}
    # Existing narrow-arg field still present — deep_merge doesn't clobber siblings.
    assert worker["workAssignment"]["homeOrganizationalUnits"][0]["nameCode"] == {"codeValue": "Engineering"}


@pytest.mark.asyncio
async def test_build_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_rehire_tool_routes_to_path(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"ok": True})
    with patch.object(c, "_post_event", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["rehire_employee"].ainvoke({
            "associate_oid": "G3ABC",
            "work_assignment_item_id": "WA-1",
            "rehire_date": "2026-05-01",
        })
    assert mock_post.call_args.kwargs["path"] == PATH_REHIRE
