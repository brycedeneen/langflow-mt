"""ADPWorkerDemographicToolsComponent — name + demographic-status mutations.

Backs the ADP WFN `workers-demographic-data-management v2` tile (6 mutations).
Consolidated into 2 agent tools:
  * `change_employee_name` — birth | legal | preferred
  * `change_employee_demographic_status` — marital | military_classification | military_status
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

NameType = Literal["birth", "legal", "preferred"]
StatusType = Literal["marital", "military_classification", "military_status"]

NAME_PATH = {
    "birth": "/events/hr/v1/worker.birth-name.change",
    "legal": "/events/hr/v1/worker.legal-name.change",
    "preferred": "/events/hr/v1/worker.preferred-name.change",
}
NAME_FIELD = {"birth": "birthName", "legal": "legalName", "preferred": "preferredName"}

STATUS_PATH = {
    "marital": "/events/hr/v1/worker.marital-status.change",
    "military_classification": "/events/hr/v1/worker.military-classification.change",
    "military_status": "/events/hr/v1/worker.military-status.change",
}
STATUS_FIELD = {
    "marital": "maritalStatusCode",
    "military_classification": "militaryClassificationCode",
    "military_status": "militaryStatusCode",
}

PATH_PREFERRED_GENDER_PRONOUN = "/events/hr/v1/worker.associate-profile.preferred-gender-pronoun.change"


def _wrap_transform(
    *, worker_person: dict[str, Any], effective_date: str | None, reason_code: str | None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {"worker": {"person": worker_person}}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return transform


def build_change_name_event(
    *,
    name_type: NameType,
    associate_oid: str,
    given_name: str | None = None,
    middle_name: str | None = None,
    family_name: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    name_body: dict[str, Any] = {}
    if given_name is not None:
        name_body["givenName"] = given_name
    if middle_name is not None:
        name_body["middleName"] = middle_name
    if family_name is not None:
        name_body["familyName1"] = family_name
    transform = _wrap_transform(
        worker_person={NAME_FIELD[name_type]: name_body},
        effective_date=effective_date,
        reason_code=reason_code,
    )
    body = {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": {"associateOID": associate_oid}},
                    "transform": transform,
                },
            },
        ],
    }
    return NAME_PATH[name_type], body


def build_change_preferred_gender_pronoun_event(
    *,
    associate_oid: str,
    pronoun_code: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform = _wrap_transform(
        worker_person={"preferredGenderPronounCode": {"codeValue": pronoun_code}},
        effective_date=effective_date,
        reason_code=reason_code,
    )
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


def build_change_demographic_status_event(
    *,
    status_type: StatusType,
    associate_oid: str,
    code_value: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    transform = _wrap_transform(
        worker_person={STATUS_FIELD[status_type]: {"statusCode": {"codeValue": code_value}}},
        effective_date=effective_date,
        reason_code=reason_code,
    )
    body = {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": {"associateOID": associate_oid}},
                    "transform": transform,
                },
            },
        ],
    }
    return STATUS_PATH[status_type], body


class ChangeEmployeeNameInput(BaseModel):
    name_type: NameType = Field(description="Which name to change: 'birth', 'legal', or 'preferred'.")
    associate_oid: str = Field(description="ADP associate OID.")
    given_name: str | None = Field(default=None, description="First name.")
    middle_name: str | None = Field(default=None, description="Middle name.")
    family_name: str | None = Field(default=None, description="Family name / surname (familyName1).")
    effective_date: str | None = Field(default=None, description="ISO-8601 date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ChangeEmployeeDemographicStatusInput(BaseModel):
    status_type: StatusType = Field(
        description="Which status to change: 'marital', 'military_classification', 'military_status'.",
    )
    associate_oid: str = Field(description="ADP associate OID.")
    code_value: str = Field(description="New status code value (e.g. 'Married', 'Single', 'Veteran').")
    effective_date: str | None = Field(default=None, description="ISO-8601 date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ChangePreferredGenderPronounInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID.")
    pronoun_code: str = Field(description="Preferred gender pronoun code (e.g. 'She/Her', 'He/Him', 'They/Them').")
    effective_date: str | None = Field(default=None, description="ISO-8601 date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code.")


class ADPWorkerDemographicToolsComponent(Component):
    display_name = "ADP Worker Demographic Tools"
    description = (
        "Name and demographic-status mutation tools for Langflow Agents, backing ADP WFN "
        "`workers-demographic-data-management v2`. Two consolidated tools cover 6 endpoints. "
        "Gated behind `enable_mutations`."
    )
    icon = "UserPen"
    name = "ADPWorkerDemographicTools"
    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 consolidated agent tools for ADP WFN "
                "workers-demographic-data-management v2: `change_employee_name` (birth/legal/preferred), "
                "`change_employee_demographic_status` (marital/military-classification/military-status). "
                "Gated behind `enable_mutations` (default off)."
            ),
        ),
        ChangelogEntry(
            version=2,
            changes=(
                "Added `change_employee_preferred_gender_pronoun` — wraps ADP WFN "
                "`worker-associate-profiles v2` pronoun-change event so a single component "
                "covers all personal-identity mutations."
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
            info="Expose demographic mutation tools. Off by default.",
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

        async def _change_name(**kw: Any) -> dict[str, Any]:
            path, body = build_change_name_event(**kw)
            return await component._post_event(conn, path=path, body=body)

        async def _change_status(**kw: Any) -> dict[str, Any]:
            path, body = build_change_demographic_status_event(**kw)
            return await component._post_event(conn, path=path, body=body)

        async def _change_preferred_gender_pronoun(**kw: Any) -> dict[str, Any]:
            body = build_change_preferred_gender_pronoun_event(**kw)
            return await component._post_event(conn, path=PATH_PREFERRED_GENDER_PRONOUN, body=body)

        return [
            StructuredTool.from_function(
                name="change_employee_name",
                description=(
                    "Change an employee's birth name, legal name, or preferred name. Pass `name_type` "
                    "plus the name fields to update."
                ),
                coroutine=_change_name,
                args_schema=ChangeEmployeeNameInput,
            ),
            StructuredTool.from_function(
                name="change_employee_demographic_status",
                description=(
                    "Change an employee's marital status, military classification, or military "
                    "status by code value. Pass `status_type` to pick which one."
                ),
                coroutine=_change_status,
                args_schema=ChangeEmployeeDemographicStatusInput,
            ),
            StructuredTool.from_function(
                name="change_employee_preferred_gender_pronoun",
                description=(
                    "Change an employee's preferred gender pronoun (e.g. 'She/Her', 'He/Him', "
                    "'They/Them') by code value."
                ),
                coroutine=_change_preferred_gender_pronoun,
                args_schema=ChangePreferredGenderPronounInput,
            ),
        ]
