"""ADP consolidated time-off tools across v2/v3 reads and a v3 modify.

Backs three related ADP WFN time-off tiles:

- `time/time-off-requests v2` — three read endpoints (balances, configurations,
  requests) that all return the same schema; consolidated into a single
  `get_worker_time_off_details` tool with a `view` Literal.
- `time/time-off-requests v3` — two read endpoints (self + team request-summary);
  consolidated into `get_time_off_request_summaries` with a `scope` Literal.
- `time/time-off-balances v3` — one POST `time-off-balances.modify` event;
  exposed as `modify_time_off_balances` (gated).
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

TimeOffView = Literal["balances", "configurations", "requests"]
SummaryScope = Literal["self", "team"]

_V2_PATHS: dict[str, str] = {
    "balances": "/time/v2/workers/{aoid}/time-off-details/time-off-balances",
    "configurations": "/time/v2/workers/{aoid}/time-off-details/time-off-configurations",
    "requests": "/time/v2/workers/{aoid}/time-off-details/time-off-requests",
}

_V3_SUMMARY_PATHS: dict[str, str] = {
    "self": "/time/v3/workers/{aoid}/time-off-request-summaries",
    "team": "/time/v3/workers/{aoid}/team-time-off-request-summaries",
}

PATH_BALANCES_MODIFY = "/events/time/v3/time-off-balances.modify"


class GetWorkerTimeOffDetailsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    view: TimeOffView = Field(
        description=(
            "Which projection to fetch — the underlying schema is the same across the three "
            "but ADP scopes/paginates each differently. 'balances' returns current balances, "
            "'configurations' returns plan configs, 'requests' returns request history."
        ),
    )


class GetTimeOffRequestSummariesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker (or supervisor for team scope).")
    scope: SummaryScope = Field(
        description="'self' for the worker's own summaries, 'team' for a supervisor's team.",
    )


class ModifyTimeOffBalancesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Transform fields merged under transform.timeOffBalances. Pass ADP-shaped dicts "
            "(balance adjustments, accrual overrides, etc.)."
        ),
    )
    additional_context_fields: dict[str, Any] = Field(
        default_factory=dict, description="Extra eventContext fields.",
    )


def build_balances_modify_event(
    *, associate_oid: str,
    fields: dict[str, Any] | None = None,
    additional_context_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_context: dict[str, Any] = {"associateOID": associate_oid}
    if additional_context_fields:
        event_context.update(additional_context_fields)
    return {
        "events": [
            {
                "data": {
                    "eventContext": event_context,
                    "transform": {"timeOffBalances": dict(fields or {})},
                },
            },
        ],
    }


async def _fetch_get(
    conn: ADPConnection,
    *,
    path: str,
    request_cache: RequestCache,
) -> dict[str, Any]:
    """Cache-aware GET for time-off read endpoints."""
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    key = RequestCache.make_key("GET", url, None)

    # Peek before opening the mTLS client so cache hits skip PEM-file churn.
    cached = request_cache.peek(key)
    if cached is not None:
        return cached

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)

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


def build_time_off_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    """Build ADP consolidated time-off tools.

    Returns 2 read tools always, plus the gated ``modify_time_off_balances`` tool
    when ``enable_mutations`` is True.
    """
    conn = connection

    async def _get_worker_time_off_details(associate_oid: str, view: str) -> dict[str, Any]:
        path = _V2_PATHS[view].format(aoid=associate_oid)
        return await _fetch_get(conn, path=path, request_cache=request_cache)

    async def _get_time_off_request_summaries(associate_oid: str, scope: str) -> dict[str, Any]:
        path = _V3_SUMMARY_PATHS[scope].format(aoid=associate_oid)
        return await _fetch_get(conn, path=path, request_cache=request_cache)

    tools: list[Tool] = [
        StructuredTool.from_function(
            name="get_worker_time_off_details",
            description=(
                "Get a worker's time-off details from the v2 API. `view='balances'` returns "
                "current balances, 'configurations' returns plan configs, 'requests' returns "
                "request history. All three share a schema with paidTimeOffConfiguration, "
                "paidTimeOffBalances, paidTimeOffRequests."
            ),
            coroutine=_get_worker_time_off_details,
            args_schema=GetWorkerTimeOffDetailsInput,
        ),
        StructuredTool.from_function(
            name="get_time_off_request_summaries",
            description=(
                "Get time-off request summaries from the v3 API. `scope='self'` for the "
                "worker's own summaries; `scope='team'` for a supervisor's team. Returns "
                "requestStatusTotals (approved/denied/pending) + worker/assignment info."
            ),
            coroutine=_get_time_off_request_summaries,
            args_schema=GetTimeOffRequestSummariesInput,
        ),
    ]

    if not enable_mutations:
        return tools

    async def _modify_time_off_balances(**kwargs: Any) -> dict[str, Any]:
        body = build_balances_modify_event(**kwargs)
        return await _post_event(conn, path=PATH_BALANCES_MODIFY, body=body)

    tools.append(
        StructuredTool.from_function(
            name="modify_time_off_balances",
            description=(
                "Fire an ADP time-off-balances.modify event for a worker. Pass `fields` with "
                "ADP-shaped transform payload (balance adjustments, accruals, etc.)."
            ),
            coroutine=_modify_time_off_balances,
            args_schema=ModifyTimeOffBalancesInput,
        ),
    )
    return tools
