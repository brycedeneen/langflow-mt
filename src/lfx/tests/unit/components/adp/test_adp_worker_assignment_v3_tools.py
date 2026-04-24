"""Tests for ADPWorkerAssignmentV3ToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_assignment_v3_tools import (
    ADPWorkerAssignmentV3ToolsComponent,
    WORK_ASSIGNMENT_PATH_TEMPLATE,
    build_add_work_assignment_body,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkerAssignmentV3ToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_add_work_assignment_body_minimum():
    body = build_add_work_assignment_body(hire_date="2026-05-01")
    assert body == {"workAssignment": {"hireDate": "2026-05-01"}}


def test_build_add_work_assignment_body_full():
    body = build_add_work_assignment_body(
        hire_date="2026-05-01",
        primary_indicator=True,
        job_code="SWE-2",
        job_title="Senior Engineer",
        worker_type_code="Regular",
        position_id="P-123",
        position_title="Senior Software Engineer",
        reports_to_associate_oid="G3MGR",
        department_name="Engineering",
        work_location_name="Remote",
        annual_base_pay=150000.0,
    )
    wa = body["workAssignment"]
    assert wa["hireDate"] == "2026-05-01"
    assert wa["primaryIndicator"] is True
    assert wa["job"] == {"jobCode": {"code": "SWE-2"}, "jobTitle": "Senior Engineer"}
    assert wa["workerTypeCode"] == {"code": "Regular"}
    assert wa["positionID"] == "P-123"
    assert wa["positionTitle"] == "Senior Software Engineer"
    assert wa["reportsTo"] == [{"associateOID": "G3MGR"}]
    assert wa["organizationalUnits"][0]["unitName"] == "Engineering"
    assert wa["organizationalUnits"][0]["unitTypeCode"] == {"code": "Department"}
    assert wa["workLocations"][0]["locationName"] == "Remote"
    assert wa["directFinancialCompensation"]["compensationRates"][0]["rate"] == 150000.0


def test_build_add_work_assignment_body_additional_fields_deep_merge():
    body = build_add_work_assignment_body(
        hire_date="2026-05-01",
        job_title="Engineer",
        additional_fields={"job": {"jobFamilies": [{"jobFamilyCode": {"code": "SWE"}}]}},
    )
    wa = body["workAssignment"]
    assert wa["job"]["jobTitle"] == "Engineer"
    assert wa["job"]["jobFamilies"][0]["jobFamilyCode"] == {"code": "SWE"}


@pytest.mark.asyncio
async def test_build_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_tool_invocation_builds_url_with_aoid(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"ok": True})
    with patch.object(c, "_post_add_work_assignment", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["add_employee_work_assignment"].ainvoke(
            {"associate_oid": "G3ABC", "hire_date": "2026-05-01"},
        )
    call = mock_post.call_args
    assert call.kwargs["associate_oid"] == "G3ABC"
    assert WORK_ASSIGNMENT_PATH_TEMPLATE.format(aoid="G3ABC") == "/hr/v3/workers/G3ABC/work-assignments"
