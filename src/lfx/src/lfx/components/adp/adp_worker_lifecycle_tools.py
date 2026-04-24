"""ADPWorkerLifecycleToolsComponent — rehire (and future hire/terminate).

Backs the ADP WFN `workers-lifecycle-management v2` tile. Currently exposes
`worker.rehire` with a minimum-viable field set plus an `additional_worker_fields`
escape hatch for any ADP-shaped worker attributes the narrow args don't cover.
Gated behind `enable_mutations`.
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

PATH_REHIRE = "/events/hr/v1/worker.rehire"


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def build_rehire_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    rehire_date: str,
    job_code: str | None = None,
    job_title: str | None = None,
    worker_type_code: str | None = None,
    work_location_name: str | None = None,
    department_name: str | None = None,
    reports_to_associate_oid: str | None = None,
    annual_base_pay: float | None = None,
    currency_code: str = "USD",
    reason_code: str | None = None,
    additional_worker_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a rehire event body.

    Essentials are exposed as named args; deeper ADP fields go through
    `additional_worker_fields` and get merged into `transform.worker`.
    """
    work_assignment: dict[str, Any] = {
        "itemID": work_assignment_item_id,
        "hireDate": rehire_date,
    }
    if job_code:
        work_assignment["jobCode"] = {"codeValue": job_code}
    if job_title:
        work_assignment["jobTitle"] = job_title
    if worker_type_code:
        work_assignment["workerTypeCode"] = {"codeValue": worker_type_code}
    if work_location_name:
        work_assignment["homeWorkLocation"] = {"nameCode": {"codeValue": work_location_name}}
    if department_name:
        work_assignment["homeOrganizationalUnits"] = [
            {"typeCode": {"codeValue": "Department"}, "nameCode": {"codeValue": department_name}},
        ]
    if reports_to_associate_oid:
        work_assignment["reportsTo"] = [{"associateOID": reports_to_associate_oid}]
    if annual_base_pay is not None:
        work_assignment["baseRemuneration"] = {
            "annualRateAmount": {"amountValue": annual_base_pay, "currencyCode": currency_code},
        }

    worker: dict[str, Any] = {
        "associateOID": associate_oid,
        "workerDates": {"rehireDate": rehire_date},
        "workAssignment": work_assignment,
    }
    if additional_worker_fields:
        _deep_merge(worker, additional_worker_fields)

    transform: dict[str, Any] = {"worker": worker, "effectiveDateTime": rehire_date}
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}

    return {
        "events": [
            {
                "data": {
                    "eventContext": {
                        "associateOID": associate_oid,
                        "workAssignment": {"itemID": work_assignment_item_id},
                    },
                    "transform": transform,
                },
            },
        ],
    }


class RehireEmployeeInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the person being rehired.")
    work_assignment_item_id: str = Field(
        description="Item ID of the work assignment this rehire applies to.",
    )
    rehire_date: str = Field(description="Rehire date (YYYY-MM-DD). Also used as effectiveDateTime.")
    job_code: str | None = Field(default=None, description="ADP job code.")
    job_title: str | None = Field(default=None, description="Job title (free text).")
    worker_type_code: str | None = Field(
        default=None, description="Worker type (e.g. 'Regular', 'Contractor').",
    )
    work_location_name: str | None = Field(default=None, description="Home work location name.")
    department_name: str | None = Field(default=None, description="Home department name.")
    reports_to_associate_oid: str | None = Field(default=None, description="Manager's ADP associate OID.")
    annual_base_pay: float | None = Field(default=None, description="Annual base pay amount.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")
    additional_worker_fields: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Escape hatch: ADP-shaped worker fields to merge into transform.worker (e.g. "
            "{'person':{'legalName':{'givenName':'Jane','familyName1':'Doe'}}})."
        ),
    )


class ADPWorkerLifecycleToolsComponent(Component):
    display_name = "ADP Worker Lifecycle Tools"
    description = (
        "Worker lifecycle mutation tools, backing ADP WFN `workers-lifecycle-management v2`. "
        "Currently exposes rehire; hire and terminate are planned follow-ups. "
        "Gated behind `enable_mutations`."
    )
    icon = "UserPlus"
    name = "ADPWorkerLifecycleTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 1 agent tool for ADP WFN workers-lifecycle-management v2: "
                "`rehire_employee` with narrow structured args + `additional_worker_fields` "
                "escape hatch for the full worker schema. Gated behind `enable_mutations` "
                "(default off)."
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
            info="Expose rehire tool. Off by default — rehires are high-blast-radius.",
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

    async def _post_event(self, conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
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

        async def _rehire_employee(**kw: Any) -> dict[str, Any]:
            body = build_rehire_event(**kw)
            return await component._post_event(conn, path=PATH_REHIRE, body=body)

        return [
            StructuredTool.from_function(
                name="rehire_employee",
                description=(
                    "Rehire a former employee. Pass the essentials (associate OID, work assignment "
                    "item ID, rehire date, and optional job/pay/location). Use "
                    "`additional_worker_fields` for ADP attributes not in the narrow arg list."
                ),
                coroutine=_rehire_employee,
                args_schema=RehireEmployeeInput,
            ),
        ]
