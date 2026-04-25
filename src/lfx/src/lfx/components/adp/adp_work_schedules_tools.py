"""ADP consolidated work-schedule tools.

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

from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

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
    context_pin_fields: dict[str, Any] | None = None,
    additional_transform_fields: dict[str, Any] | None = None,
    effective_date: str | None = None,
    event_reason_code: str | None = None,
) -> dict[str, Any]:
    if (scope, action) not in _SUPPORTED_COMBOS:
        msg = f"Unsupported (scope, action): ({scope!r}, {action!r})"
        raise ValueError(msg)

    meta = _SCOPE_META[scope]
    transform_key = meta["transform_key"]

    # ADP puts work-schedules natural-key pins at the TOP LEVEL of eventContext
    # (not nested under the transform key). Natural keys vary by scope+action:
    #   schedule.remove       → {associateOID, scheduleID}
    #   schedule_day.add      → {associateOID, schedulePeriod}
    #   schedule_day.change   → {associateOID, schedulePeriod}
    #   schedule_day.remove   → {associateOID, scheduleDayDate}  (+ schedulePeriod sometimes)
    #   schedule_entry.change → {associateOID, schedulePeriod, scheduleDayDate, scheduleEntryID}
    event_context: dict[str, Any] = {"associateOID": associate_oid}
    if context_pin_fields:
        event_context.update(context_pin_fields)

    # change/remove must identify the target — require a pin.
    if action in ("change", "remove") and not context_pin_fields:
        msg = (
            f"{action!r} on scope={scope!r} requires context_pin_fields "
            "(e.g. scheduleID / schedulePeriod / scheduleDayDate / scheduleEntryID "
            "depending on scope)."
        )
        raise ValueError(msg)

    transform: dict[str, Any] = {}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if event_reason_code:
        transform["eventReasonCode"] = {"codeValue": event_reason_code}
    if action != "remove":
        transform[transform_key] = dict(fields or {})
    # additional_transform_fields carries top-level transform keys like
    # `workerCopyTo`, `startDateCopyTo`, `eventStatusCode` that ADP expects
    # outside the scope entity.
    if additional_transform_fields:
        transform.update(additional_transform_fields)

    return {"events": [{"data": {"eventContext": event_context, "transform": transform}}]}


class GetWorkerWorkSchedulesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    filter: str | None = Field(default=None, alias="$filter", description="OData $filter.")
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
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Transform payload under the scope-specific entity key "
            "(workSchedule / scheduleDay / scheduleEntry). Example fields per scope: "
            "schedule → schedulePeriod, scheduleDays[]; "
            "schedule_day → daySequenceNumber, scheduleDayDate, scheduleEntries[]; "
            "schedule_entry → categoryTypeCode, shiftTypeCode, dateTimePeriod, payCode. "
            "Pass ADP-shaped dicts."
        ),
    )
    context_pin_fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Natural-key pins merged into the TOP LEVEL of eventContext. Required for change/"
            "remove. Typical pins per scope+action:\n"
            "- schedule.remove → {'scheduleID': '...'}\n"
            "- schedule_day.add / .change → {'schedulePeriod': {'startDate': '...', 'endDate': '...'}}\n"
            "- schedule_day.remove → {'scheduleDayDate': 'YYYY-MM-DD'} (+ schedulePeriod if needed)\n"
            "- schedule_entry.change → {'schedulePeriod': {...}, 'scheduleDayDate': '...', "
            "'scheduleEntryID': '...'}"
        ),
    )
    additional_transform_fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Extra top-level transform fields outside the scope entity. Commonly used for "
            "copy operations: {'workerCopyTo': {'associateOID': '...'}, 'startDateCopyTo': '...'}. "
            "Also used for {'eventStatusCode': {'codeValue': '...'}}."
        ),
    )
    effective_date: str | None = Field(
        default=None, description="Optional ISO-8601 effective date merged into transform.",
    )
    event_reason_code: str | None = Field(
        default=None, description="Optional ADP event-reason codeValue merged into transform.",
    )


async def _fetch_work_schedules(
    conn: ADPConnection,
    *,
    path: str,
    params: dict[str, Any] | None,
    request_cache: RequestCache,
) -> dict[str, Any]:
    """Cache-aware GET for work schedules."""
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    key = RequestCache.make_key("GET", url, params)

    # Peek before opening the mTLS client so cache hits skip PEM-file churn.
    cached = request_cache.peek(key)
    if cached is not None:
        return cached

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        result = await cached_get_json(
            client=client, cache=request_cache, url=url, headers=headers, params=params,
        )
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(
                client=client, cache=request_cache, url=url, headers=headers, params=params,
            )

    return result


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


def build_work_schedules_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    """Build ADP work-schedules tools.

    Always returns the read tool ``get_worker_work_schedules``. Appends the gated
    ``manage_work_schedule`` tool when ``enable_mutations`` is True.
    """
    conn = connection

    async def _get_worker_work_schedules(**kwargs: Any) -> dict[str, Any]:
        associate_oid = kwargs["associate_oid"]
        path = PATH_LIST_WORKER.format(aoid=associate_oid)
        params: dict[str, Any] = {}
        for source_key, api_key in (("filter", "$filter"), ("skip", "$skip"), ("top", "$top")):
            val = kwargs.get(source_key)
            if val is not None:
                params[api_key] = val
        return await _fetch_work_schedules(
            conn, path=path, params=params or None, request_cache=request_cache,
        )

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

    if not enable_mutations:
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
                context_pin_fields=kwargs.get("context_pin_fields") or {},
                additional_transform_fields=kwargs.get("additional_transform_fields") or {},
                effective_date=kwargs.get("effective_date"),
                event_reason_code=kwargs.get("event_reason_code"),
            )
            path = event_path(scope, action)
        except ValueError as err:
            return {"error": str(err), "status_code": 422}
        return await _post_event(conn, path=path, body=body)

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
