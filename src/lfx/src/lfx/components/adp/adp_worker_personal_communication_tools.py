"""ADPWorkerPersonalCommunicationToolsComponent — personal contact-info mutations.

Backs the ADP WFN `workers-personal-communication-management v2` tile (21
mutation endpoints + 1 /meta). Consolidated into 3 agent-facing tools by
data kind — addresses, phones, emails — each taking an `operation` arg.
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

Operation = Literal["add", "change", "remove"]
AddressType = Literal["legal", "personal"]
PhoneType = Literal["landline", "mobile", "fax", "pager"]


def _address_path(address_type: AddressType, operation: Operation) -> str:
    segment = {"legal": "legal-address", "personal": "personal-address"}[address_type]
    return f"/events/hr/v1/worker.{segment}.{operation}"


def _phone_path(phone_type: PhoneType, operation: Operation) -> str:
    return f"/events/hr/v1/worker.personal-communication.{phone_type}.{operation}"


def _email_path(operation: Operation) -> str:
    return f"/events/hr/v1/worker.personal-communication.email.{operation}"


def _name_code(label: str | None) -> dict[str, Any] | None:
    return {"codeValue": label} if label else None


def _address_payload(
    *,
    line_one: str | None,
    line_two: str | None,
    city_name: str | None,
    country_subdivision_code: str | None,
    postal_code: str | None,
    country_code: str | None,
    label: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if line_one is not None:
        payload["lineOne"] = line_one
    if line_two is not None:
        payload["lineTwo"] = line_two
    if city_name is not None:
        payload["cityName"] = city_name
    if country_subdivision_code is not None:
        payload["countrySubdivisionLevel1"] = {"codeValue": country_subdivision_code}
    if postal_code is not None:
        payload["postalCode"] = postal_code
    if country_code is not None:
        payload["countryCode"] = country_code
    label_obj = _name_code(label)
    if label_obj:
        payload["nameCode"] = label_obj
    return payload


def _phone_payload(*, formatted_number: str | None, label: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if formatted_number is not None:
        payload["formattedNumber"] = formatted_number
    label_obj = _name_code(label)
    if label_obj:
        payload["nameCode"] = label_obj
    return payload


def _email_payload(*, email_uri: str | None, label: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if email_uri is not None:
        payload["emailUri"] = email_uri
    label_obj = _name_code(label)
    if label_obj:
        payload["nameCode"] = label_obj
    return payload


def _envelope(
    *,
    event_context_worker: dict[str, Any],
    transform_worker: dict[str, Any] | None,
    effective_date: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {}
    if transform_worker is not None:
        transform["worker"] = transform_worker
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": event_context_worker},
                    "transform": transform,
                },
            },
        ],
    }


def build_address_event(
    *,
    operation: Operation,
    address_type: AddressType,
    associate_oid: str,
    address_item_id: str | None = None,
    line_one: str | None = None,
    line_two: str | None = None,
    city_name: str | None = None,
    country_subdivision_code: str | None = None,
    postal_code: str | None = None,
    country_code: str | None = None,
    label: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    address_field = {"legal": "legalAddress", "personal": "otherPersonalAddresses"}[address_type]
    address_body = _address_payload(
        line_one=line_one, line_two=line_two, city_name=city_name,
        country_subdivision_code=country_subdivision_code, postal_code=postal_code,
        country_code=country_code, label=label,
    )

    event_ctx: dict[str, Any] = {"associateOID": associate_oid}
    transform_worker: dict[str, Any] | None

    if operation == "add":
        value = address_body if address_type == "legal" else [address_body]
        transform_worker = {"person": {address_field: value}}
    elif operation == "change":
        if not address_item_id:
            msg = "`address_item_id` is required for address change."
            raise ValueError(msg)
        ctx_value = {"itemID": address_item_id} if address_type != "legal" else {}
        event_ctx["person"] = {address_field: ctx_value if address_type != "legal" else {}}
        value_with_id = {**address_body}
        if address_type != "legal":
            value_with_id["itemID"] = address_item_id
        value = value_with_id if address_type == "legal" else [value_with_id]
        transform_worker = {"person": {address_field: value}}
    else:  # remove
        if not address_item_id and address_type != "legal":
            msg = "`address_item_id` is required for non-legal address remove."
            raise ValueError(msg)
        ctx_value = {"itemID": address_item_id} if address_item_id else {}
        event_ctx["person"] = {address_field: [ctx_value] if address_type != "legal" else {}}
        transform_worker = None

    body = _envelope(
        event_context_worker=event_ctx,
        transform_worker=transform_worker,
        effective_date=effective_date,
        reason_code=reason_code,
    )
    return _address_path(address_type, operation), body


def build_phone_event(
    *,
    operation: Operation,
    phone_type: PhoneType,
    associate_oid: str,
    phone_item_id: str | None = None,
    formatted_number: str | None = None,
    label: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    field_name = {"landline": "landlines", "mobile": "mobiles", "fax": "faxes", "pager": "pagers"}[phone_type]
    payload = _phone_payload(formatted_number=formatted_number, label=label)

    event_ctx: dict[str, Any] = {"associateOID": associate_oid}
    transform_worker: dict[str, Any] | None

    if operation == "add":
        transform_worker = {"person": {"communication": {field_name: [payload]}}}
    elif operation == "change":
        if not phone_item_id:
            msg = "`phone_item_id` is required for phone change."
            raise ValueError(msg)
        event_ctx["person"] = {"communication": {field_name: [{"itemID": phone_item_id}]}}
        transform_worker = {"person": {"communication": {field_name: [{**payload, "itemID": phone_item_id}]}}}
    else:  # remove
        if not phone_item_id:
            msg = "`phone_item_id` is required for phone remove."
            raise ValueError(msg)
        event_ctx["person"] = {"communication": {field_name: [{"itemID": phone_item_id}]}}
        transform_worker = None

    body = _envelope(
        event_context_worker=event_ctx,
        transform_worker=transform_worker,
        effective_date=effective_date,
        reason_code=reason_code,
    )
    return _phone_path(phone_type, operation), body


def build_email_event(
    *,
    operation: Operation,
    associate_oid: str,
    email_item_id: str | None = None,
    email_uri: str | None = None,
    label: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = _email_payload(email_uri=email_uri, label=label)

    event_ctx: dict[str, Any] = {"associateOID": associate_oid}
    transform_worker: dict[str, Any] | None

    if operation == "add":
        transform_worker = {"person": {"communication": {"emails": [payload]}}}
    elif operation == "change":
        if not email_item_id:
            msg = "`email_item_id` is required for email change."
            raise ValueError(msg)
        event_ctx["person"] = {"communication": {"emails": [{"itemID": email_item_id}]}}
        transform_worker = {"person": {"communication": {"emails": [{**payload, "itemID": email_item_id}]}}}
    else:  # remove
        if not email_item_id:
            msg = "`email_item_id` is required for email remove."
            raise ValueError(msg)
        event_ctx["person"] = {"communication": {"emails": [{"itemID": email_item_id}]}}
        transform_worker = None

    body = _envelope(
        event_context_worker=event_ctx,
        transform_worker=transform_worker,
        effective_date=effective_date,
        reason_code=reason_code,
    )
    return _email_path(operation), body


class UpdateEmployeeAddressInput(BaseModel):
    operation: Operation = Field(description="'add' a new address, 'change' an existing one, or 'remove' one.")
    address_type: AddressType = Field(description="'legal' (primary) or 'personal' (additional) address.")
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    address_item_id: str | None = Field(
        default=None,
        description="Required for change; required for personal-address remove. "
        "Legal address has no itemID — it's the single primary address.",
    )
    line_one: str | None = Field(default=None, description="Street line 1.")
    line_two: str | None = Field(default=None, description="Street line 2 (apt/suite). Optional.")
    city_name: str | None = Field(default=None, description="City.")
    country_subdivision_code: str | None = Field(
        default=None, description="State/province code (e.g. 'IL', 'CA').",
    )
    postal_code: str | None = Field(default=None, description="Postal/ZIP code.")
    country_code: str | None = Field(default=None, description="ISO-3166 country code (e.g. 'US').")
    label: str | None = Field(default=None, description="Address label nameCode (e.g. 'Home', 'Mailing').")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class UpdateEmployeePhoneInput(BaseModel):
    operation: Operation = Field(description="'add', 'change', or 'remove'.")
    phone_type: PhoneType = Field(description="'landline', 'mobile', 'fax', or 'pager'.")
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    phone_item_id: str | None = Field(
        default=None, description="Required for change/remove. Omit for add.",
    )
    formatted_number: str | None = Field(default=None, description="Phone number (e.g. '+1-555-0100').")
    label: str | None = Field(default=None, description="Phone label (e.g. 'Personal', 'Home').")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class UpdateEmployeeEmailInput(BaseModel):
    operation: Operation = Field(description="'add', 'change', or 'remove'.")
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    email_item_id: str | None = Field(
        default=None, description="Required for change/remove. Omit for add.",
    )
    email_uri: str | None = Field(default=None, description="Email address.")
    label: str | None = Field(default=None, description="Email label (e.g. 'Personal', 'Home').")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ADPWorkerPersonalCommunicationToolsComponent(Component):
    display_name = "ADP Worker Personal Communication Tools"
    description = (
        "Address/phone/email mutation tools for Langflow Agents, backing ADP WFN "
        "`workers-personal-communication-management v2`. Each tool takes an `operation` "
        "(add/change/remove) plus channel-specific fields. Gated behind `enable_mutations`."
    )
    icon = "ContactRound"
    name = "ADPWorkerPersonalCommunicationTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 3 agent tools covering 21 ADP WFN personal-communication "
                "mutation endpoints: `update_employee_address` (legal + personal), "
                "`update_employee_phone` (landline/mobile/fax/pager), `update_employee_email`. "
                "Each tool takes an `operation` arg (add/change/remove). Gated behind "
                "`enable_mutations` (default off)."
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
                "Expose personal-communication mutation tools to the agent. Off by default — "
                "changing an employee's address, phone, or email is high-blast-radius. Turn on "
                "only when the flow is meant to act on personal contact data."
            ),
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method="POST", url=url, headers=headers, json=json_body, timeout=timeout,
        )

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

        async def _update_employee_address(**kwargs: Any) -> dict[str, Any]:
            path, body = build_address_event(**kwargs)
            return await component._post_event(conn, path=path, body=body)

        async def _update_employee_phone(**kwargs: Any) -> dict[str, Any]:
            path, body = build_phone_event(**kwargs)
            return await component._post_event(conn, path=path, body=body)

        async def _update_employee_email(**kwargs: Any) -> dict[str, Any]:
            path, body = build_email_event(**kwargs)
            return await component._post_event(conn, path=path, body=body)

        return [
            StructuredTool.from_function(
                name="update_employee_address",
                description=(
                    "Add, change, or remove an employee's legal or personal address. "
                    "For `change` provide the address's itemID and the fields to update. "
                    "For `remove` on personal addresses provide the itemID."
                ),
                coroutine=_update_employee_address,
                args_schema=UpdateEmployeeAddressInput,
            ),
            StructuredTool.from_function(
                name="update_employee_phone",
                description=(
                    "Add, change, or remove an employee's phone number (landline, mobile, fax, "
                    "or pager). For `change`/`remove` provide the phone's itemID."
                ),
                coroutine=_update_employee_phone,
                args_schema=UpdateEmployeePhoneInput,
            ),
            StructuredTool.from_function(
                name="update_employee_email",
                description=(
                    "Add, change, or remove an employee's personal email address. "
                    "For `change`/`remove` provide the email's itemID."
                ),
                coroutine=_update_employee_email,
                args_schema=UpdateEmployeeEmailInput,
            ),
        ]
