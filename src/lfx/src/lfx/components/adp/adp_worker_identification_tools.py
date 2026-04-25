"""ADP worker identification tools — government ID add/change.

Backs the ADP WFN `workers-identification-management v2` tile. Two endpoints:
add a government ID (SSN, SIN, NIN) and change an existing one.
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


def build_worker_identification_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _add_government_id(**kwargs: Any) -> dict[str, Any]:
        body = build_add_government_id_event(**kwargs)
        return await _post_event(conn, path=PATH_ADD_GOVERNMENT_ID, body=body)

    async def _change_government_id(**kwargs: Any) -> dict[str, Any]:
        body = build_change_government_id_event(**kwargs)
        return await _post_event(conn, path=PATH_CHANGE_GOVERNMENT_ID, body=body)

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
