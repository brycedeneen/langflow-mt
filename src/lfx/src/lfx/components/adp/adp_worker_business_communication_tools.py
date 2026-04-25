"""ADP worker business communication tools — business contact-channel mutations.

Backs the ADP WFN `workers-business-communication-management v2` tile. The tile
covers 15 endpoints — 5 channels (email/fax/landline/mobile/pager) x 3
operations (add/change/remove) — all sharing an identical transform shape:
`transform.worker.businessCommunication.{channel}`. Consolidated into a single
agent-facing tool with `channel` + `action` literals.
"""

from __future__ import annotations

from typing import Any, Literal

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


BusinessChannel = Literal["email", "fax", "landline", "mobile", "pager"]
BusinessAction = Literal["add", "change", "remove"]


def event_path(channel: BusinessChannel, action: BusinessAction) -> str:
    return f"/events/hr/v1/worker.business-communication.{channel}.{action}"


def _phone_payload(item: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if item.get("area_dialing") is not None:
        payload["areaDialing"] = item["area_dialing"]
    if item.get("dial_number") is not None:
        payload["dialNumber"] = item["dial_number"]
    if item.get("country_dialing") is not None:
        payload["countryDialing"] = item["country_dialing"]
    if item.get("extension") is not None:
        payload["extension"] = item["extension"]
    if item.get("formatted_number") is not None:
        payload["formattedNumber"] = item["formatted_number"]
    if item.get("item_id") is not None:
        payload["itemID"] = item["item_id"]
    return payload


def build_business_communication_event(
    *,
    action: BusinessAction,
    channel: BusinessChannel,
    associate_oid: str,
    email_uri: str | None = None,
    area_dialing: str | None = None,
    dial_number: str | None = None,
    country_dialing: str | None = None,
    extension: str | None = None,
    formatted_number: str | None = None,
    item_id: str | None = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    channel_payload: dict[str, Any] = {}
    if channel == "email":
        if email_uri is not None:
            channel_payload["emailUri"] = email_uri
        if item_id is not None:
            channel_payload["itemID"] = item_id
    else:
        channel_payload = _phone_payload(
            {
                "area_dialing": area_dialing,
                "dial_number": dial_number,
                "country_dialing": country_dialing,
                "extension": extension,
                "formatted_number": formatted_number,
                "item_id": item_id,
            },
        )

    if additional_fields:
        for key, value in additional_fields.items():
            channel_payload[key] = value

    # remove keeps channel_payload minimal (usually just itemID).
    if action == "remove" and not item_id and not channel_payload:
        msg = "'remove' action requires item_id (or additional_fields to identify the row)"
        raise ValueError(msg)

    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": {"associateOID": associate_oid}},
                    "transform": {
                        "worker": {"businessCommunication": {channel: channel_payload}},
                    },
                },
            },
        ],
    }


class ManageBusinessCommunicationInput(BaseModel):
    action: BusinessAction = Field(
        description="Event to fire: 'add' (new channel entry), 'change' (update), or 'remove'.",
    )
    channel: BusinessChannel = Field(
        description="Communication channel: 'email', 'fax', 'landline', 'mobile', or 'pager'.",
    )
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    item_id: str | None = Field(
        default=None,
        description="Existing channel-entry itemID (from a read). Required for change/remove.",
    )
    email_uri: str | None = Field(
        default=None, description="Email address (email channel only).",
    )
    area_dialing: str | None = Field(
        default=None, description="Area/area-code portion of a phone number (phone channels).",
    )
    dial_number: str | None = Field(
        default=None, description="Dial-number portion of a phone number (phone channels).",
    )
    country_dialing: str | None = Field(
        default=None, description="Country code (phone channels; optional).",
    )
    extension: str | None = Field(
        default=None, description="Extension (phone channels; optional).",
    )
    formatted_number: str | None = Field(
        default=None, description="Fully-formatted number, if ADP requires it.",
    )
    additional_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch — extra fields merged into the channel payload.",
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


def build_worker_business_communication_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _manage_worker_business_communication(**kwargs: Any) -> dict[str, Any]:
        try:
            body = build_business_communication_event(**kwargs)
        except ValueError as err:
            return {"error": str(err), "status_code": 422}
        path = event_path(kwargs["channel"], kwargs["action"])
        return await _post_event(conn, path=path, body=body)

    return [
        StructuredTool.from_function(
            name="manage_worker_business_communication",
            description=(
                "Add, change, or remove a worker's business communication entry for a given "
                "channel (email / fax / landline / mobile / pager). For email: use email_uri. "
                "For phone channels: use area_dialing + dial_number (and optionally "
                "country_dialing, extension, formatted_number). For change/remove: include "
                "item_id (from a prior read)."
            ),
            coroutine=_manage_worker_business_communication,
            args_schema=ManageBusinessCommunicationInput,
        ),
    ]
