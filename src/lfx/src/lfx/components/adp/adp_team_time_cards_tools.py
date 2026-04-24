"""ADPTeamTimeCardsToolsComponent — team-time-cards read tool for Langflow Agents.

Backs the ADP WFN `time/team-time-cards v2` tile. Read-only tile with a single
GET endpoint. Exposes one consolidated tool.
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
from lfx.io import HandleInput, Output

HTTP_UNAUTHORIZED = 401
HTTP_CLIENT_ERROR_MIN = 400

PATH_GET = "/time/v2/workers/{aoid}/team-time-cards"


class GetTeamTimeCardsInput(BaseModel):
    associate_oid: str = Field(
        description="ADP associate OID of the supervisor whose team's time cards to fetch.",
    )
    filter: str | None = Field(  # noqa: A003
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


class ADPTeamTimeCardsToolsComponent(Component):
    display_name = "ADP Team Time Cards Tools"
    description = (
        "Read tool for ADP WFN `time/team-time-cards v2`. `get_team_time_cards` returns "
        "the supervisor's team's time cards (direct + optional indirect reports), with "
        "OData filter/skip/top/select/expand support."
    )
    icon = "ClipboardCheck"
    name = "ADPTeamTimeCardsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — single agent tool `get_team_time_cards` backing ADP WFN "
                "time/team-time-cards v2. Read-only tile."
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
        params: dict[str, Any] | None,
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    async def _call(
        self,
        conn: ADPConnection,
        *,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(
                client, url=url, headers=headers, params=params, timeout=30.0,
            )
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, url=url, headers=headers, params=params, timeout=30.0,
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
        conn: ADPConnection = self.connection
        component = self

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
            return await component._call(conn, path=path, params=params or None)

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
