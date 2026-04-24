"""ADPWorkerIdentificationToolsComponent — government ID add/change.

Backs the ADP WFN `workers-identification-management v2` tile. Two endpoints:
add a government ID (SSN, SIN, NIN) and change an existing one. Gated behind
`enable_mutations` — PII mutations are high-blast-radius.
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

PATH_ADD_GOVERNMENT_ID = "/events/hr/v1/worker.government-id.add"
PATH_CHANGE_GOVERNMENT_ID = "/events/hr/v1/worker.government-id.change"


def _government_id_payload(
    *,
    id_value: str | None,
    name_code: str | None,
    country_code: str | None,
    status_code: str | None,
    effective_date: str | None,
    expiration_date: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if id_value is not None:
        payload["idValue"] = id_value
    if name_code:
        payload["nameCode"] = {"codeValue": name_code}
    if country_code:
        payload["countryCode"] = country_code
    if status_code:
        payload["statusCode"] = {"codeValue": status_code}
    if effective_date:
        payload["statusCode"] = payload.get("statusCode", {})
        payload["statusCode"]["effectiveDate"] = effective_date
    if expiration_date:
        payload["expirationDate"] = expiration_date
    return payload


def build_add_government_id_event(
    *,
    associate_oid: str,
    id_value: str,
    name_code: str,
    country_code: str | None = None,
    status_code: str | None = None,
    id_effective_date: str | None = None,
    expiration_date: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    payload = _government_id_payload(
        id_value=id_value,
        name_code=name_code,
        country_code=country_code,
        status_code=status_code,
        effective_date=id_effective_date,
        expiration_date=expiration_date,
    )
    transform: dict[str, Any] = {"worker": {"person": {"governmentID": payload}}}
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


def build_change_government_id_event(
    *,
    associate_oid: str,
    government_id_item_id: str,
    id_value: str | None = None,
    name_code: str | None = None,
    country_code: str | None = None,
    status_code: str | None = None,
    id_effective_date: str | None = None,
    expiration_date: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    payload = _government_id_payload(
        id_value=id_value,
        name_code=name_code,
        country_code=country_code,
        status_code=status_code,
        effective_date=id_effective_date,
        expiration_date=expiration_date,
    )
    payload["itemID"] = government_id_item_id
    transform: dict[str, Any] = {"worker": {"person": {"governmentID": payload}}}
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
                            "person": {"governmentID": {"itemID": government_id_item_id}},
                        },
                    },
                    "transform": transform,
                },
            },
        ],
    }


class AddGovernmentIdInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    id_value: str = Field(description="Government ID value (SSN, SIN, NIN, etc.).")
    name_code: str = Field(description="Type of government ID (e.g. 'SSN', 'SIN').")
    country_code: str | None = Field(default=None, description="ISO-3166 country code (e.g. 'US').")
    status_code: str | None = Field(default=None, description="ID status (e.g. 'Active').")
    id_effective_date: str | None = Field(default=None, description="ID effective date (YYYY-MM-DD).")
    expiration_date: str | None = Field(default=None, description="ID expiration date (YYYY-MM-DD).")
    effective_date: str | None = Field(default=None, description="Event effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ChangeGovernmentIdInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    government_id_item_id: str = Field(description="Item ID of the government-ID entry to change.")
    id_value: str | None = Field(default=None, description="New ID value. Omit to keep unchanged.")
    name_code: str | None = Field(default=None, description="New ID type nameCode. Omit to keep unchanged.")
    country_code: str | None = Field(default=None, description="ISO-3166 country code.")
    status_code: str | None = Field(default=None, description="New ID status.")
    id_effective_date: str | None = Field(default=None, description="New ID effective date.")
    expiration_date: str | None = Field(default=None, description="New expiration date.")
    effective_date: str | None = Field(default=None, description="Event effective date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ADPWorkerIdentificationToolsComponent(Component):
    display_name = "ADP Worker Identification Tools"
    description = (
        "Government-ID mutation tools for Langflow Agents, backing ADP WFN "
        "`workers-identification-management v2`: add a government ID (SSN/SIN/NIN), "
        "change an existing one. Gated behind `enable_mutations`."
    )
    icon = "IdCard"
    name = "ADPWorkerIdentificationTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 agent tools for ADP WFN worker-identification-management v2: "
                "`add_employee_government_id`, `change_employee_government_id`. "
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
            info=(
                "Expose the government-ID mutation tools to the agent. Off by default — "
                "this is PII. Only enable in flows intended to act on identification data."
            ),
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

        async def _add_government_id(**kwargs: Any) -> dict[str, Any]:
            body = build_add_government_id_event(**kwargs)
            return await component._post_event(conn, path=PATH_ADD_GOVERNMENT_ID, body=body)

        async def _change_government_id(**kwargs: Any) -> dict[str, Any]:
            body = build_change_government_id_event(**kwargs)
            return await component._post_event(conn, path=PATH_CHANGE_GOVERNMENT_ID, body=body)

        return [
            StructuredTool.from_function(
                name="add_employee_government_id",
                description=(
                    "Add a government ID (SSN, SIN, NIN, etc.) for an employee. "
                    "Use `name_code` to specify the type."
                ),
                coroutine=_add_government_id,
                args_schema=AddGovernmentIdInput,
            ),
            StructuredTool.from_function(
                name="change_employee_government_id",
                description=(
                    "Change an existing government ID entry for an employee. "
                    "Requires the government-ID itemID."
                ),
                coroutine=_change_government_id,
                args_schema=ChangeGovernmentIdInput,
            ),
        ]
