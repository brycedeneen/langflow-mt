"""ADP worker deployment tools — change standard hours / worker type.

Backs the ADP WFN `workers-work-deployment-management v2` tile. Two mutation
endpoints: change the standard work hours on a work assignment, and change the
worker type code (e.g. regular vs. contractor).
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
# Backward-compat stub — orchestrator will update __init__.py later.
# ---------------------------------------------------------------------------
class ADPWorkerDeploymentToolsComponent:
    """Deprecated stub — use build_worker_deployment_tools instead."""


PATH_CHANGE_STANDARD_HOURS = "/events/hr/v1/worker.work-assignment.standard-hours.change"
PATH_CHANGE_WORKER_TYPE = "/events/hr/v1/worker.work-assignment.worker-type.change"


def _envelope(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    work_assignment_transform: dict[str, Any],
    effective_date: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {"workAssignment": work_assignment_transform}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
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


def build_change_standard_hours_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    hours_quantity: float,
    units_code: str = "Hour",
    frequency_code: str = "Weekly",
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return _envelope(
        associate_oid=associate_oid,
        work_assignment_item_id=work_assignment_item_id,
        work_assignment_transform={
            "standardHours": {
                "hoursQuantity": hours_quantity,
                "unitCode": {"codeValue": units_code},
                "unitTimeCode": {"codeValue": frequency_code},
            },
        },
        effective_date=effective_date,
        reason_code=reason_code,
    )


def build_change_worker_type_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    worker_type_code: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return _envelope(
        associate_oid=associate_oid,
        work_assignment_item_id=work_assignment_item_id,
        work_assignment_transform={"workerTypeCode": {"codeValue": worker_type_code}},
        effective_date=effective_date,
        reason_code=reason_code,
    )


class ChangeStandardHoursInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_item_id: str = Field(description="Item ID of the work assignment to update.")
    hours_quantity: float = Field(description="New standard-hours quantity (e.g. 40.0).")
    units_code: str = Field(default="Hour", description="Hour | Day | Minute. Usually 'Hour'.")
    frequency_code: str = Field(default="Weekly", description="Weekly | Daily | Biweekly | Monthly. Usually 'Weekly'.")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ChangeWorkerTypeInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_item_id: str = Field(description="Item ID of the work assignment to update.")
    worker_type_code: str = Field(
        description="New worker type (e.g. 'Regular', 'Contractor', 'Temporary', 'Intern').",
    )
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


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


def build_worker_deployment_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _change_standard_hours(**kwargs: Any) -> dict[str, Any]:
        body = build_change_standard_hours_event(**kwargs)
        return await _post_event(conn, path=PATH_CHANGE_STANDARD_HOURS, body=body)

    async def _change_worker_type(**kwargs: Any) -> dict[str, Any]:
        body = build_change_worker_type_event(**kwargs)
        return await _post_event(conn, path=PATH_CHANGE_WORKER_TYPE, body=body)

    return [
        StructuredTool.from_function(
            name="change_employee_standard_hours",
            description=(
                "Change an employee's standard (scheduled) work hours on a work assignment."
            ),
            coroutine=_change_standard_hours,
            args_schema=ChangeStandardHoursInput,
        ),
        StructuredTool.from_function(
            name="change_employee_worker_type",
            description=(
                "Change an employee's worker type on a work assignment "
                "(e.g. Regular, Contractor, Temporary)."
            ),
            coroutine=_change_worker_type,
            args_schema=ChangeWorkerTypeInput,
        ),
    ]
