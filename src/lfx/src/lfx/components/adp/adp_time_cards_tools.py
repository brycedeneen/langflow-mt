"""ADP time-entry mutation tools.

Backs ADP WFN `time/time-cards v2`. Single POST `/events/time/v2/time-entries.modify`
that accepts a batch of structured time entries (hours, time pairs, with optional
labor allocations). One agent tool, gated.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

HTTP_CLIENT_ERROR_MIN = 400

PATH_MODIFY = "/events/time/v2/time-entries.modify"


def build_time_entries_modify_event(
    *,
    associate_oid: str,
    work_assignment_id: str | None = None,
    time_entries: list[dict[str, Any]] | None = None,
    additional_context_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_context: dict[str, Any] = {"associateOID": associate_oid}
    if work_assignment_id:
        event_context["workAssignmentID"] = work_assignment_id
    if additional_context_fields:
        event_context.update(additional_context_fields)
    return {
        "events": [
            {
                "data": {
                    "eventContext": event_context,
                    "transform": {"timeEntries": list(time_entries or [])},
                },
            },
        ],
    }


class SubmitTimeEntriesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    work_assignment_id: str | None = Field(
        default=None, description="Work assignment itemID for the entries (optional).",
    )
    time_entries: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Structured time entries. Each entry is an ADP-shaped dict with fields like: "
            "entryTypeCode ({codeValue: 'hoursEntry'|'timePairEntry'}), entryCode, entryDate, "
            "timeDuration (ISO-8601 duration like 'PT8H'), startPeriod.{startDateTime}, "
            "endPeriod.{endDateTime}, laborAllocations[]. Pass verbatim ADP shapes."
        ),
    )
    additional_context_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch for extra eventContext fields (payrollGroup, etc.).",
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


def build_time_cards_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # noqa: ARG001 — accepted for registry uniformity; unused for writes
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    """Build ADP time cards mutation tools.

    Returns a list of StructuredTools. The list is empty when ``enable_mutations``
    is False (the default) — time-entry writes affect payroll downstream.
    """
    if not enable_mutations:
        return []

    conn = connection

    async def _submit_time_entries(**kwargs: Any) -> dict[str, Any]:
        body = build_time_entries_modify_event(**kwargs)
        return await _post_event(conn, path=PATH_MODIFY, body=body)

    return [
        StructuredTool.from_function(
            name="submit_time_entries",
            description=(
                "Submit a batch of time entries for a worker (hours or time-pair). Requires "
                "associate_oid; include work_assignment_id when the entries target a specific "
                "assignment. Pass `time_entries` as a list of ADP-shaped dicts."
            ),
            coroutine=_submit_time_entries,
            args_schema=SubmitTimeEntriesInput,
        ),
    ]
