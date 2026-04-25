"""ADP team-time-cards read tools.

Backs the ADP WFN `time/team-time-cards v2` tile. Read-only tile with a single
GET endpoint. Exposes one consolidated tool.
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
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

HTTP_CLIENT_ERROR_MIN = 400

PATH_GET = "/time/v2/workers/{aoid}/team-time-cards"


class GetTeamTimeCardsInput(BaseModel):
    associate_oid: str = Field(
        description="ADP associate OID of the supervisor whose team's time cards to fetch.",
    )
    filter: str | None = Field(
        default=None,
        alias="$filter",
        description="OData $filter (e.g. date range or status predicate).",
    )
    skip: int | None = Field(default=None, alias="$skip", description="OData $skip — start sequence.")
    top: int | None = Field(default=None, alias="$top", description="OData $top — max rows.")
    select: str | None = Field(
        default=None, alias="$select", description="OData $select — projection/fields.",
    )
    expand: str | None = Field(
        default=None, alias="$expand", description="OData $expand — expand criterion.",
    )
    custom_filter: str | None = Field(
        default=None,
        alias="customFilter",
        description="Points to a hyperfind query configured in ADP SOR.",
    )
    indirect_reportees: bool | None = Field(
        default=None,
        alias="indirectReportees",
        description="If true, includes both direct and indirect reports.",
    )
    visibility_code: str | None = Field(
        default=None,
        alias="visibilityCode",
        description="Visibility scope (public vs. private) of the timecards.",
    )

    model_config = {"populate_by_name": True}


async def _fetch_team_time_cards(
    conn: ADPConnection,
    *,
    path: str,
    params: dict[str, Any] | None,
    request_cache: RequestCache,
) -> dict[str, Any]:
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


def build_team_time_cards_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]:
    """Build ADP team time cards read tools."""
    conn = connection

    async def _get_team_time_cards(**kwargs: Any) -> dict[str, Any]:
        associate_oid = kwargs["associate_oid"]
        path = PATH_GET.format(aoid=associate_oid)
        param_map = {
            "filter": "$filter",
            "skip": "$skip",
            "top": "$top",
            "select": "$select",
            "expand": "$expand",
            "custom_filter": "customFilter",
            "indirect_reportees": "indirectReportees",
            "visibility_code": "visibilityCode",
        }
        params: dict[str, Any] = {}
        for source_key, api_key in param_map.items():
            value = kwargs.get(source_key)
            if value is not None:
                params[api_key] = value
        return await _fetch_team_time_cards(
            conn, path=path, params=params or None, request_cache=request_cache,
        )

    return [
        StructuredTool.from_function(
            name="get_team_time_cards",
            description=(
                "Get the team time cards for a supervisor by their ADP associate OID. Returns "
                "associateOID, workerID, personLegalName, and the timeCards array. Supports "
                "OData $filter/$skip/$top/$select/$expand, plus an indirect_reportees flag to "
                "include indirect reports."
            ),
            coroutine=_get_team_time_cards,
            args_schema=GetTeamTimeCardsInput,
        ),
    ]
