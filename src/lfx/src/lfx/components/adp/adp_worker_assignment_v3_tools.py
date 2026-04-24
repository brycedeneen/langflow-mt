"""ADPWorkerAssignmentV3ToolsComponent — add a work assignment via the HR v3 REST API.

Backs the ADP WFN `hr-work-assignment-management v3` tile. Unlike the v2 tile,
this uses a RESTful `POST /hr/v3/workers/{aoid}/work-assignments` with the
workAssignment body directly (no event envelope). The body can be very large
(100+ fields); this component exposes narrow args for the common ones plus an
`additional_fields` escape hatch.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import ADPConnection, build_mtls_httpx_client, fetch_token, validate_adp_url
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import BoolInput, HandleInput, Output

HTTP_UNAUTHORIZED = 401
HTTP_CLIENT_ERROR_MIN = 400

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
    currency_code: str = "USD",
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


class ADPWorkerAssignmentV3ToolsComponent(Component):
    display_name = "ADP Worker Assignment Tools (v3 REST)"
    description = (
        "Add-work-assignment tool for Langflow Agents, backing ADP WFN "
        "`hr-work-assignment-management v3` (RESTful POST, not event envelope). "
        "Gated behind `enable_mutations`."
    )
    icon = "BriefcaseBusiness"
    name = "ADPWorkerAssignmentV3Tools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 1 agent tool for ADP WFN hr-work-assignment-management v3: "
                "`add_employee_work_assignment` (RESTful POST). Narrow args + "
                "`additional_fields` escape hatch. Gated behind `enable_mutations` (default off)."
            ),
        ),
    ]

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        BoolInput(
            name="enable_mutations",
            display_name="Enable Mutations",
            info="Expose add-work-assignment tool. Off by default.",
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self, client: httpx.AsyncClient, *, url: str, headers: dict[str, str],
        json_body: dict[str, Any], timeout: float,
    ) -> httpx.Response:
        return await client.request("POST", url, headers=headers, json=json_body, timeout=timeout)

    async def _post_add_work_assignment(
        self, conn: ADPConnection, *, associate_oid: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        path = WORK_ASSIGNMENT_PATH_TEMPLATE.format(aoid=associate_oid)
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(client, url=url, headers=headers, json_body=body, timeout=30.0)
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, url=url, headers=headers, json_body=body, timeout=30.0,
                )
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

    async def build_tools(self) -> list[Tool]:
        if not self.enable_mutations:
            return []
        conn: ADPConnection = self.connection
        component = self

        async def _add_work_assignment(**kw: Any) -> dict[str, Any]:
            associate_oid = kw.pop("associate_oid")
            body = build_add_work_assignment_body(**kw)
            return await component._post_add_work_assignment(conn, associate_oid=associate_oid, body=body)

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
