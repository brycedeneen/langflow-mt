"""ADP worker assignment v3 tools — add a work assignment via the HR v3 REST API.

Backs the ADP WFN `hr-work-assignment-management v3` tile. Unlike the v2 tile,
this uses a RESTful `POST /hr/v3/workers/{aoid}/work-assignments` with the
workAssignment body directly (no event envelope). The body can be very large
(100+ fields); this module exposes narrow args for the common ones plus an
`additional_fields` escape hatch.
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


WORK_ASSIGNMENT_PATH_TEMPLATE = "/hr/v3/workers/{aoid}/work-assignments"


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def build_add_work_assignment_body(
    *,
    hire_date: str,
    primary_indicator: bool | None = None,
    job_code: str | None = None,
    job_title: str | None = None,
    worker_type_code: str | None = None,
    position_id: str | None = None,
    position_title: str | None = None,
    reports_to_associate_oid: str | None = None,
    department_name: str | None = None,
    work_location_name: str | None = None,
    annual_base_pay: float | None = None,
    currency_code: str = "USD",  # noqa: ARG001 — reserved for future comp rate support; schema exposes it
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the body for `POST /hr/v3/workers/{aoid}/work-assignments`.

    The v3 body is a single workAssignment object under a top-level key.
    """
    wa: dict[str, Any] = {"hireDate": hire_date}
    if primary_indicator is not None:
        wa["primaryIndicator"] = primary_indicator
    if job_code or job_title:
        job: dict[str, Any] = {}
        if job_code:
            job["jobCode"] = {"code": job_code}
        if job_title:
            job["jobTitle"] = job_title
        wa["job"] = job
    if worker_type_code:
        wa["workerTypeCode"] = {"code": worker_type_code}
    if position_id:
        wa["positionID"] = position_id
    if position_title:
        wa["positionTitle"] = position_title
    if reports_to_associate_oid:
        wa["reportsTo"] = [{"associateOID": reports_to_associate_oid}]
    if department_name:
        wa["organizationalUnits"] = [
            {
                "unitTypeCode": {"code": "Department"},
                "unitName": department_name,
                "assignedUnitIndicator": True,
            },
        ]
    if work_location_name:
        wa["workLocations"] = [
            {"locationName": work_location_name, "assignedLocationIndicator": True},
        ]
    if annual_base_pay is not None:
        wa["directFinancialCompensation"] = {
            "compensationRates": [
                {
                    "rate": annual_base_pay,
                    "unitCode": {"code": "Annual"},
                    "classificationCode": {"code": "Base"},
                    "effectiveDate": hire_date,
                },
            ],
        }
    if additional_fields:
        _deep_merge(wa, additional_fields)
    return {"workAssignment": wa}


class AddWorkAssignmentInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the employee.")
    hire_date: str = Field(description="Hire date (ISO-8601 YYYY-MM-DD). Also used for comp effectiveDate.")
    primary_indicator: bool | None = Field(
        default=None, description="True if this is the employee's primary work assignment.",
    )
    job_code: str | None = Field(default=None, description="ADP job code.")
    job_title: str | None = Field(default=None, description="Job title (free text).")
    worker_type_code: str | None = Field(
        default=None, description="Worker type (e.g. 'Regular', 'Contractor').",
    )
    position_id: str | None = Field(default=None, description="Position ID.")
    position_title: str | None = Field(default=None, description="Position title.")
    reports_to_associate_oid: str | None = Field(default=None, description="Manager's associate OID.")
    department_name: str | None = Field(default=None, description="Department name.")
    work_location_name: str | None = Field(default=None, description="Work location name.")
    annual_base_pay: float | None = Field(default=None, description="Annual base pay amount.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code.")
    additional_fields: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Escape hatch: ADP-shaped workAssignment fields to merge (e.g. payrollProfile, "
            "legislativeComplianceClassifications, customFieldGroup)."
        ),
    )


async def _post_add_work_assignment(
    conn: ADPConnection, *, associate_oid: str, body: dict[str, Any],
) -> dict[str, Any]:
    """POST the add-work-assignment body, with one 401-refresh retry."""
    path = WORK_ASSIGNMENT_PATH_TEMPLATE.format(aoid=associate_oid)
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


def build_worker_assignment_v3_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _add_work_assignment(**kw: Any) -> dict[str, Any]:
        associate_oid = kw.pop("associate_oid")
        body = build_add_work_assignment_body(**kw)
        return await _post_add_work_assignment(conn, associate_oid=associate_oid, body=body)

    return [
        StructuredTool.from_function(
            name="add_employee_work_assignment",
            description=(
                "Create a new work assignment for an employee via the v3 REST endpoint. "
                "Pass the hire date plus common fields (job, position, comp, location, "
                "manager). Use `additional_fields` for deeper ADP attributes."
            ),
            coroutine=_add_work_assignment,
            args_schema=AddWorkAssignmentInput,
        ),
    ]
