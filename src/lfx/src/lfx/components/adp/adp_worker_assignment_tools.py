"""ADP worker assignment tools — work-assignment mutations.

Backs the ADP WFN `workers-work-assignment-management v2` tile. Four mutation
endpoints: change reports-to (manager), change assigned organizational units,
modify a work assignment generically, terminate a specific work assignment.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_CLIENT_ERROR_MIN,
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry


# ---------------------------------------------------------------------------
# Backward-compat stub — __init__.py still imports this name; orchestrator
# will update __init__.py in a consolidated commit after all batches land.
# ---------------------------------------------------------------------------
class ADPWorkerAssignmentToolsComponent:
    """Deprecated stub — use build_worker_assignment_tools instead."""

PATH_REPORTS_TO_MODIFY = "/events/hr/v1/worker.reports-to.modify"
PATH_ORG_UNITS_MODIFY = "/events/hr/v1/worker.work-assignment.assigned-organizational-units.modify"
PATH_WORK_ASSIGNMENT_MODIFY = "/events/hr/v1/worker.work-assignment.modify"
PATH_WORK_ASSIGNMENT_TERMINATE = "/events/hr/v1/worker.work-assignment.terminate"


def _event(
    *,
    event_context: dict[str, Any],
    transform: dict[str, Any],
    effective_date: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    full_transform = dict(transform)
    if effective_date:
        full_transform["effectiveDateTime"] = effective_date
    if reason_code:
        full_transform["eventReasonCode"] = {"codeValue": reason_code}
    return {"events": [{"data": {"eventContext": event_context, "transform": full_transform}}]}


def build_change_reports_to_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    new_manager_associate_oid: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return _event(
        event_context={
            "associateOID": associate_oid,
            "workAssignmentID": work_assignment_item_id,
        },
        transform={
            "workAssignment": {
                "reportsTo": [{"associateOID": new_manager_associate_oid}],
            },
        },
        effective_date=effective_date,
        reason_code=reason_code,
    )


def build_change_org_units_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    organizational_units: list[dict[str, str]],
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """`organizational_units` is a list of `{type_code, name_code}` dicts.

    type_code examples: "Department", "Division", "CostCenter".
    """
    units = [
        {
            "typeCode": {"codeValue": u["type_code"]},
            "nameCode": {"codeValue": u["name_code"]},
        }
        for u in organizational_units
    ]
    return _event(
        event_context={
            "worker": {
                "associateOID": associate_oid,
                "workAssignment": {"itemID": work_assignment_item_id},
            },
        },
        transform={"worker": {"workAssignment": {"assignedOrganizationalUnits": units}}},
        effective_date=effective_date,
        reason_code=reason_code,
    )


def build_modify_work_assignment_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    work_assignment_fields: dict[str, Any],
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """Generic work-assignment modification.

    Caller provides the fields to change as an ADP-shaped dict
    (e.g. `{"jobTitle": "Senior Engineer"}`).
    """
    return _event(
        event_context={
            "worker": {
                "associateOID": associate_oid,
                "workAssignment": {"itemID": work_assignment_item_id},
            },
        },
        transform={"worker": {"workAssignment": work_assignment_fields}},
        effective_date=effective_date,
        reason_code=reason_code,
    )


def build_terminate_work_assignment_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    termination_date: str | None = None,
    comment: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {
        "worker": {"workAssignment": {"terminationDate": termination_date} if termination_date else {}},
    }
    if comment:
        transform["comment"] = {"text": comment}
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    if termination_date:
        transform["effectiveDateTime"] = termination_date
    return {
        "events": [
            {
                "data": {
                    "eventContext": {
                        "worker": {
                            "associateOID": associate_oid,
                            "workAssignment": {"itemID": work_assignment_item_id},
                        },
                    },
                    "transform": transform,
                },
            },
        ],
    }


class ChangeReportsToInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the employee whose manager is changing.")
    work_assignment_item_id: str = Field(description="Item ID of the employee's work assignment.")
    new_manager_associate_oid: str = Field(description="ADP associate OID of the new manager.")
    effective_date: str | None = Field(default=None, description="ISO-8601 date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ChangeOrgUnitsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID.")
    work_assignment_item_id: str = Field(description="Work-assignment item ID.")
    organizational_units: list[dict[str, str]] = Field(
        description="List of {type_code, name_code} dicts, e.g. "
        "[{'type_code':'Department','name_code':'Engineering'}].",
    )
    effective_date: str | None = Field(default=None, description="ISO-8601 date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ModifyWorkAssignmentInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID.")
    work_assignment_item_id: str = Field(description="Work-assignment item ID.")
    work_assignment_fields: dict[str, Any] = Field(
        description="ADP-shaped dict of work-assignment fields to change "
        "(e.g. {'jobTitle':'Senior Engineer','jobCode':{'codeValue':'SWE-2'}}).",
    )
    effective_date: str | None = Field(default=None, description="ISO-8601 date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class TerminateWorkAssignmentInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID.")
    work_assignment_item_id: str = Field(description="Work-assignment item ID to terminate.")
    termination_date: str | None = Field(default=None, description="ISO-8601 termination date.")
    comment: str | None = Field(default=None, description="Free-text comment for the termination.")
    reason_code: str | None = Field(
        default=None, description="Reason (e.g. 'Voluntary Resignation', 'Position Eliminated').",
    )


async def _post_event(conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST a single ADP event, with one 401-refresh retry."""
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}
    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        response = await client.request("POST", url=url, headers=headers, json=body, timeout=30.0)
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request("POST", url=url, headers=headers, json=body, timeout=30.0)
    if response.status_code >= HTTP_CLIENT_ERROR_MIN:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return {"error": detail, "status_code": response.status_code}
    try:
        return response.json()
    except ValueError:
        return {"ok": True, "status_code": response.status_code}


def build_worker_assignment_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _change_manager(**kw: Any) -> dict[str, Any]:
        return await _post_event(conn, path=PATH_REPORTS_TO_MODIFY, body=build_change_reports_to_event(**kw))

    async def _change_org_units(**kw: Any) -> dict[str, Any]:
        return await _post_event(conn, path=PATH_ORG_UNITS_MODIFY, body=build_change_org_units_event(**kw))

    async def _modify_work_assignment(**kw: Any) -> dict[str, Any]:
        return await _post_event(
            conn, path=PATH_WORK_ASSIGNMENT_MODIFY, body=build_modify_work_assignment_event(**kw),
        )

    async def _terminate_work_assignment(**kw: Any) -> dict[str, Any]:
        return await _post_event(
            conn, path=PATH_WORK_ASSIGNMENT_TERMINATE, body=build_terminate_work_assignment_event(**kw),
        )

    return [
        StructuredTool.from_function(
            name="change_employee_manager",
            description="Change the employee's reports-to manager on a work assignment.",
            coroutine=_change_manager,
            args_schema=ChangeReportsToInput,
        ),
        StructuredTool.from_function(
            name="change_employee_organizational_units",
            description=(
                "Change the organizational units (department, division, cost center, etc.) "
                "assigned to an employee's work assignment."
            ),
            coroutine=_change_org_units,
            args_schema=ChangeOrgUnitsInput,
        ),
        StructuredTool.from_function(
            name="modify_employee_work_assignment",
            description=(
                "Generic modification of an employee's work assignment. Caller provides an "
                "ADP-shaped `work_assignment_fields` dict with the properties to change."
            ),
            coroutine=_modify_work_assignment,
            args_schema=ModifyWorkAssignmentInput,
        ),
        StructuredTool.from_function(
            name="terminate_employee_work_assignment",
            description=(
                "Terminate a specific work assignment (not the employee overall). Use the "
                "lifecycle tile for full-worker termination."
            ),
            coroutine=_terminate_work_assignment,
            args_schema=TerminateWorkAssignmentInput,
        ),
    ]
