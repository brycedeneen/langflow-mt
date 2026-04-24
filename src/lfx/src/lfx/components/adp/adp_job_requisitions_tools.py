"""ADPJobRequisitionsToolsComponent — job-requisitions read tools for Langflow Agents.

Backs the ADP WFN `staffing/job-requisitions v1` tile. Exposes a single
consolidated read tool (list + detail) since the tile is read-only and
the response payload, while broad, is flat enough to return whole.
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

PATH_LIST = "/staffing/v1/job-requisitions"
PATH_DETAIL = "/staffing/v1/job-requisitions/{job_requisition_id}"


class GetJobRequisitionsInput(BaseModel):
    job_requisition_id: str | None = Field(
        default=None,
        description="Specific job-requisition ID to fetch. Omit to list requisitions.",
    )
    filter: str | None = Field(  # noqa: A003
        default=None,
        alias="$filter",
        description="OData $filter expression (e.g. \"requisitionStatusCode/codeValue eq 'Open'\"). Only used on list.",
    )
    skip: int | None = Field(
        default=None,
        alias="$skip",
        description="OData $skip — start sequence. Only used on list.",
    )
    top: int | None = Field(
        default=None,
        alias="$top",
        description="OData $top — max rows (default per ADP). Only used on list.",
    )

    model_config = {"populate_by_name": True}


class ADPJobRequisitionsToolsComponent(Component):
    display_name = "ADP Job Requisitions Tools"
    description = (
        "Read tool for ADP WFN `staffing/job-requisitions v1`. "
        "`get_job_requisitions` lists requisitions (with optional $filter/$skip/$top) or "
        "fetches a single one by ID."
    )
    icon = "ClipboardList"
    name = "ADPJobRequisitionsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — single agent tool `get_job_requisitions` (list + detail "
                "consolidated) backing ADP WFN staffing/job-requisitions v1. Read-only tile."
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

        async def _get_job_requisitions(
            job_requisition_id: str | None = None,
            filter: str | None = None,  # noqa: A002
            skip: int | None = None,
            top: int | None = None,
        ) -> dict[str, Any]:
            if job_requisition_id:
                return await component._call(
                    conn, path=PATH_DETAIL.format(job_requisition_id=job_requisition_id),
                )
            params: dict[str, Any] = {}
            if filter is not None:
                params["$filter"] = filter
            if skip is not None:
                params["$skip"] = skip
            if top is not None:
                params["$top"] = top
            return await component._call(conn, path=PATH_LIST, params=params or None)

        return [
            StructuredTool.from_function(
                name="get_job_requisitions",
                description=(
                    "Get ADP job requisitions. If `job_requisition_id` is provided, fetches that "
                    "single requisition; otherwise lists with optional OData $filter (e.g. "
                    "\"requisitionStatusCode/codeValue eq 'Open'\"), $skip, $top. Each "
                    "requisition includes clientRequisitionID, status, title, description, job, "
                    "position, hiring-team, compensation, locations, and screening requirements."
                ),
                coroutine=_get_job_requisitions,
                args_schema=GetJobRequisitionsInput,
            ),
        ]
