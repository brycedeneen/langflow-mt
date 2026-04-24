"""ADPWorkSchedulesToolsComponent — consolidated work-schedule tools.

Backs ADP WFN `time/work-schedules v1` (19 endpoints total — 9 POSTs +
9 /meta + 2 GETs). The POSTs cover 3 scopes at varying granularities:

- **schedule** (whole employee schedule) — add/change/copy/remove
- **schedule_day** (a day within a schedule) — add/change/copy/remove
- **schedule_entry** (a single entry within a day) — change only

Exposes 2 tools: `get_worker_work_schedules` (read) and
`manage_work_schedule` (gated; scope + action literals route to the right
event endpoint and set the right transform key).
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

PATH_LIST_WORKER = "/time/v1/workers/{aoid}/work-schedules"
PATH_LIST_TEAM_DEPRECATED = "/time/v1/work-schedules"

Scope = Literal["schedule", "schedule_day", "schedule_entry"]
Action = Literal["add", "change", "copy", "remove"]

# scope → (event-path slug, transform key).
_SCOPE_META: dict[str, dict[str, str]] = {
    "schedule": {"slug": "work-schedule", "transform_key": "workSchedule"},
    "schedule_day": {"slug": "work-schedule-day", "transform_key": "scheduleDay"},
    "schedule_entry": {"slug": "work-schedule-entry", "transform_key": "scheduleEntry"},
}

# (scope, action) → supported per ADP swagger
_SUPPORTED_COMBOS: set[tuple[str, str]] = {
    ("schedule", "add"),
    ("schedule", "change"),
    ("schedule", "copy"),
    ("schedule", "remove"),
    ("schedule_day", "add"),
    ("schedule_day", "change"),
    ("schedule_day", "copy"),
    ("schedule_day", "remove"),
    ("schedule_entry", "change"),
}


def event_path(scope: Scope, action: Action) -> str:
    if (scope, action) not in _SUPPORTED_COMBOS:
        msg = f"Unsupported (scope, action): ({scope!r}, {action!r})"
        raise ValueError(msg)
    slug = _SCOPE_META[scope]["slug"]
    return f"/events/time/v1/{slug}.{action}"


def build_work_schedule_event(
    *,
    scope: Scope,
    action: Action,
    associate_oid: str,
    fields: dict[str, Any] | None = None,
    item_id: str | None = None,
    context_pin_fields: dict[str, Any] | None = None,
    effective_date: str | None = None,
    event_reason_code: str | None = None,
) -> dict[str, Any]:
    if (scope, action) not in _SUPPORTED_COMBOS:
        msg = f"Unsupported (scope, action): ({scope!r}, {action!r})"
        raise ValueError(msg)

    meta = _SCOPE_META[scope]
    transform_key = meta["transform_key"]

    event_context: dict[str, Any] = {"associateOID": associate_oid}
    if action in ("change", "copy", "remove"):
        pin: dict[str, Any] = {}
        if item_id:
            pin["itemID"] = item_id
        if context_pin_fields:
            for k, v in context_pin_fields.items():
                pin[k] = v
        if action in ("change", "remove") and not pin:
            msg = f"{action!r} action on scope={scope!r} requires item_id or context_pin_fields"
            raise ValueError(msg)
        if pin:
            event_context[transform_key] = pin

    transform: dict[str, Any] = {}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if event_reason_code:
        transform["eventReasonCode"] = {"codeValue": event_reason_code}
    if action != "remove":
        transform[transform_key] = dict(fields or {})

    return {"events": [{"data": {"eventContext": event_context, "transform": transform}}]}


class GetWorkerWorkSchedulesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    filter: str | None = Field(default=None, alias="$filter", description="OData $filter.")  # noqa: A003
    skip: int | None = Field(default=None, alias="$skip", description="OData $skip.")
    top: int | None = Field(default=None, alias="$top", description="OData $top.")

    model_config = {"populate_by_name": True}


class ManageWorkScheduleInput(BaseModel):
    scope: Scope = Field(
        description=(
            "Granularity: 'schedule' (whole employee schedule), 'schedule_day' (a single day), "
            "or 'schedule_entry' (a single entry within a day; change only)."
        ),
    )
    action: Action = Field(
        description=(
            "Event: 'add', 'change', 'copy', or 'remove'. 'schedule_entry' only supports 'change'."
        ),
    )
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    item_id: str | None = Field(
        default=None,
        description="Existing schedule/day/entry itemID (required for change/remove).",
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Transform payload under the scope-specific key. For 'schedule': scheduleStartDate, "
            "scheduleEndDate, scheduleDays[]. For 'schedule_day': scheduleDate, scheduleEntries[]. "
            "For 'schedule_entry': startPeriod, endPeriod, positionID, laborAllocations[]. Pass "
            "ADP-shaped dicts."
        ),
    )
    context_pin_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Fields to pin the entity in eventContext alongside or instead of item_id.",
    )
    effective_date: str | None = Field(
        default=None, description="Optional ISO-8601 effective date merged into transform.",
    )
    event_reason_code: str | None = Field(
        default=None, description="Optional ADP event-reason codeValue merged into transform.",
    )


class ADPWorkSchedulesToolsComponent(Component):
    display_name = "ADP Work Schedules Tools"
    description = (
        "Consolidated tools for ADP WFN `time/work-schedules v1`. `get_worker_work_schedules` "
        "reads a worker's schedules. `manage_work_schedule` fires the right work-schedule / "
        "-day / -entry event via `scope` + `action` literals (covering 9 POST endpoints). "
        "Mutations gated behind `enable_mutations`."
    )
    icon = "CalendarDays"
    name = "ADPWorkSchedulesTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 consolidated agent tools covering ADP WFN time/work-schedules "
                "v1: `get_worker_work_schedules` (read) + `manage_work_schedule` (9 mutation "
                "endpoints via scope/action literals). Mutation gated behind `enable_mutations`."
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
            info="Expose the work-schedule mutation tool. Off by default.",
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self, client: httpx.AsyncClient, *, method: str, url: str, headers: dict[str, str],
        params: dict[str, Any] | None, json_body: dict[str, Any] | None, timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method=method, url=url, headers=headers, params=params, json=json_body, timeout=timeout,
        )

    async def _call(
        self, conn: ADPConnection, *, method: str, path: str,
        params: dict[str, Any] | None = None, body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(
                client, method=method, url=url, headers=headers,
                params=params, json_body=body, timeout=30.0,
            )
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, method=method, url=url, headers=headers,
                    params=params, json_body=body, timeout=30.0,
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

    async def _post_event(self, conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._call(conn, method="POST", path=path, body=body)

    async def build_tools(self) -> list[Tool]:
        conn: ADPConnection = self.connection
        component = self

        async def _get_worker_work_schedules(**kwargs: Any) -> dict[str, Any]:
            associate_oid = kwargs["associate_oid"]
            path = PATH_LIST_WORKER.format(aoid=associate_oid)
            params: dict[str, Any] = {}
            for source_key, api_key in (("filter", "$filter"), ("skip", "$skip"), ("top", "$top")):
                val = kwargs.get(source_key)
                if val is not None:
                    params[api_key] = val
            return await component._call(conn, method="GET", path=path, params=params or None)

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_worker_work_schedules",
                description=(
                    "Get a worker's work schedules (per-worker scope) from ADP WFN time/"
                    "work-schedules v1. Supports OData $filter/$skip/$top. Returns workSchedules, "
                    "workScheduleTotals, and confirmMessage."
                ),
                coroutine=_get_worker_work_schedules,
                args_schema=GetWorkerWorkSchedulesInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _manage_work_schedule(**kwargs: Any) -> dict[str, Any]:
            scope = kwargs["scope"]
            action = kwargs["action"]
            try:
                body = build_work_schedule_event(
                    scope=scope,
                    action=action,
                    associate_oid=kwargs["associate_oid"],
                    fields=kwargs.get("fields") or {},
                    item_id=kwargs.get("item_id"),
                    context_pin_fields=kwargs.get("context_pin_fields") or {},
                    effective_date=kwargs.get("effective_date"),
                    event_reason_code=kwargs.get("event_reason_code"),
                )
                path = event_path(scope, action)
            except ValueError as err:
                return {"error": str(err), "status_code": 422}
            return await component._post_event(conn, path=path, body=body)

        tools.append(
            StructuredTool.from_function(
                name="manage_work_schedule",
                description=(
                    "Fire a work-schedule event at the selected scope + action. Scopes: "
                    "'schedule' (whole employee schedule), 'schedule_day' (a day), "
                    "'schedule_entry' (a single entry — change only). Actions: add/change/copy/"
                    "remove (schedule_entry supports only change). Pass ADP-shaped `fields` for "
                    "the transform payload; include item_id for change/remove/copy."
                ),
                coroutine=_manage_work_schedule,
                args_schema=ManageWorkScheduleInput,
            ),
        )
        return tools
