"""ADPTimeCardsToolsComponent — time-entries mutation tool.

Backs ADP WFN `time/time-cards v2`. Single POST `/events/time/v2/time-entries.modify`
that accepts a batch of structured time entries (hours, time pairs, with optional
labor allocations). One agent tool, gated.
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
        for key, value in additional_context_fields.items():
            event_context[key] = value
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


class ADPTimeCardsToolsComponent(Component):
    display_name = "ADP Time Cards Tools"
    description = (
        "Submit time-entry modifications for ADP WFN `time/time-cards v2`. Single tool "
        "`submit_time_entries` — accepts a worker's OID, work-assignment id, and a batch of "
        "structured time entries (hours or time-pair). Gated behind `enable_mutations`."
    )
    icon = "Clock"
    name = "ADPTimeCardsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — single agent tool `submit_time_entries` backing ADP WFN "
                "time/time-cards v2. Gated behind `enable_mutations`."
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
                "Expose the submit-time-entries tool to the agent. Off by default — time-entry "
                "writes affect payroll downstream."
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

        async def _submit_time_entries(**kwargs: Any) -> dict[str, Any]:
            body = build_time_entries_modify_event(**kwargs)
            return await component._post_event(conn, path=PATH_MODIFY, body=body)

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
