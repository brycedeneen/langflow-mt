"""ADPDataCollectionEntriesToolsComponent — time/data-collection-entries v1.

Tile has one POST `data-collection-entries.process` event + one GET for the
event result by event-id. Exposes two tools: `process_data_collection_entries`
(gated) and `get_data_collection_event_result` (read).
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

PATH_PROCESS = "/events/time/v1/data-collection-entries.process"
PATH_RESULT = "/events/time/v1/data-collection-entries.process/{event_id}"


class ProcessDataCollectionEntriesInput(BaseModel):
    event_body: dict[str, Any] = Field(
        description=(
            "Full ADP event body: the `{events: [{data: {eventContext, transform: {...}}}]}` "
            "envelope. Pass through ADP-shaped data unchanged."
        ),
    )


class GetDataCollectionEventResultInput(BaseModel):
    event_id: str = Field(description="Event ID returned from the .process POST.")


class ADPDataCollectionEntriesToolsComponent(Component):
    display_name = "ADP Data Collection Entries Tools"
    description = (
        "Tools for ADP WFN `time/data-collection-entries v1`. Fire the "
        "`data-collection-entries.process` event (gated) and fetch the result by event ID."
    )
    icon = "Database"
    name = "ADPDataCollectionEntriesTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 agent tools for ADP WFN time/data-collection-entries v1: "
                "`process_data_collection_entries` (gated) + `get_data_collection_event_result`."
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
            info="Expose the process-data-collection-entries tool. Off by default.",
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self, client: httpx.AsyncClient, *, method: str, url: str, headers: dict[str, str],
        json_body: dict[str, Any] | None, timeout: float,
    ) -> httpx.Response:
        return await client.request(method=method, url=url, headers=headers, json=json_body, timeout=timeout)

    async def _call(
        self, conn: ADPConnection, *, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(
                client, method=method, url=url, headers=headers, json_body=body, timeout=30.0,
            )
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, method=method, url=url, headers=headers, json_body=body, timeout=30.0,
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

        async def _get_data_collection_event_result(event_id: str) -> dict[str, Any]:
            path = PATH_RESULT.format(event_id=event_id)
            return await component._call(conn, method="GET", path=path)

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_data_collection_event_result",
                description=(
                    "Get the result/status of a prior data-collection-entries.process event "
                    "by its event ID."
                ),
                coroutine=_get_data_collection_event_result,
                args_schema=GetDataCollectionEventResultInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _process_data_collection_entries(event_body: dict[str, Any]) -> dict[str, Any]:
            return await component._call(conn, method="POST", path=PATH_PROCESS, body=event_body)

        tools.append(
            StructuredTool.from_function(
                name="process_data_collection_entries",
                description=(
                    "Fire the ADP data-collection-entries.process event. Pass a full ADP event "
                    "envelope (`{events: [...]}`) as `event_body`."
                ),
                coroutine=_process_data_collection_entries,
                args_schema=ProcessDataCollectionEntriesInput,
            ),
        )
        return tools
