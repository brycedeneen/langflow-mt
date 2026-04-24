"""ADPWorkerBiologicalToolsComponent — birth-date + gender/race mutations.

Backs the ADP WFN `workers-biological-data-management v2` tile (4 mutations + 1 meta).
Two consolidated agent tools:
  * `change_employee_birth_date` — date only
  * `change_employee_biological_attribute` — gender | gender_identity | race (code value)
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

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

PATH_BIRTH_DATE = "/events/hr/v1/worker.birth-date.change"

AttributeType = Literal["gender", "gender_identity", "race"]
ATTR_PATH = {
    "gender": "/events/hr/v1/worker.gender.change",
    "gender_identity": "/events/hr/v1/worker.gender-identity.change",
    "race": "/events/hr/v1/worker.race.change",
}
ATTR_FIELD = {
    "gender": "genderCode",
    "gender_identity": "genderIdentityCode",
    "race": "raceCode",
}


def _envelope(
    *, associate_oid: str, worker_person: dict[str, Any],
    effective_date: str | None, reason_code: str | None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {"worker": {"person": worker_person}}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": {"associateOID": associate_oid}},
                    "transform": transform,
                },
            },
        ],
    }


def build_change_birth_date_event(
    *,
    associate_oid: str,
    birth_date: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return _envelope(
        associate_oid=associate_oid,
        worker_person={"birthDate": birth_date},
        effective_date=effective_date,
        reason_code=reason_code,
    )


def build_change_biological_attribute_event(
    *,
    attribute_type: AttributeType,
    associate_oid: str,
    code_value: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    body = _envelope(
        associate_oid=associate_oid,
        worker_person={ATTR_FIELD[attribute_type]: {"codeValue": code_value}},
        effective_date=effective_date,
        reason_code=reason_code,
    )
    return ATTR_PATH[attribute_type], body


class ChangeEmployeeBirthDateInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID.")
    birth_date: str = Field(description="New birth date in ISO-8601 format (YYYY-MM-DD).")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ChangeBiologicalAttributeInput(BaseModel):
    attribute_type: AttributeType = Field(
        description="Which attribute: 'gender', 'gender_identity', or 'race'.",
    )
    associate_oid: str = Field(description="ADP associate OID.")
    code_value: str = Field(description="New code value (ADP codelist-driven).")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ADPWorkerBiologicalToolsComponent(Component):
    display_name = "ADP Worker Biological Tools"
    description = (
        "Birth-date and biological-attribute mutation tools, backing ADP WFN "
        "`workers-biological-data-management v2` (4 endpoints). Gated behind `enable_mutations`."
    )
    icon = "HeartPulse"
    name = "ADPWorkerBiologicalTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 consolidated agent tools for ADP WFN "
                "workers-biological-data-management v2: `change_employee_birth_date`, "
                "`change_employee_biological_attribute` (gender/gender_identity/race). "
                "Gated behind `enable_mutations` (default off)."
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
            info="Expose biological mutation tools. Off by default — PII.",
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

        async def _change_birth_date(**kw: Any) -> dict[str, Any]:
            body = build_change_birth_date_event(**kw)
            return await component._post_event(conn, path=PATH_BIRTH_DATE, body=body)

        async def _change_biological_attribute(**kw: Any) -> dict[str, Any]:
            path, body = build_change_biological_attribute_event(**kw)
            return await component._post_event(conn, path=path, body=body)

        return [
            StructuredTool.from_function(
                name="change_employee_birth_date",
                description="Change an employee's birth date.",
                coroutine=_change_birth_date,
                args_schema=ChangeEmployeeBirthDateInput,
            ),
            StructuredTool.from_function(
                name="change_employee_biological_attribute",
                description=(
                    "Change an employee's gender, gender identity, or race by code value. "
                    "Pass `attribute_type` to select which attribute."
                ),
                coroutine=_change_biological_attribute,
                args_schema=ChangeBiologicalAttributeInput,
            ),
        ]
