"""ADPDeductionConfigurationsToolsComponent — payroll deduction-configurations read."""

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

PATH = "/payroll/v3/deduction-configurations"


class GetDeductionConfigurationsInput(BaseModel):
    filter: str | None = Field(default=None, alias="$filter", description="OData $filter.")  # noqa: A003
    skip: int | None = Field(default=None, alias="$skip", description="OData $skip.")
    top: int | None = Field(default=None, alias="$top", description="OData $top.")

    model_config = {"populate_by_name": True}


class ADPDeductionConfigurationsToolsComponent(Component):
    display_name = "ADP Deduction Configurations Tools"
    description = (
        "Read tool for ADP WFN `payroll/deduction-configurations v3`. Single tool "
        "`get_deduction_configurations` returning the client's deduction-configuration catalog "
        "(deduction codes, categories, etc.) for joining to per-worker deduction instructions."
    )
    icon = "List"
    name = "ADPDeductionConfigurationsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — single read tool backing ADP WFN payroll/deduction-configurations v3."
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
        self, client: httpx.AsyncClient, *, url: str, headers: dict[str, str],
        params: dict[str, Any] | None, timeout: float,
    ) -> httpx.Response:
        return await client.request(method="GET", url=url, headers=headers, params=params, timeout=timeout)

    async def _call(
        self, conn: ADPConnection, *, path: str, params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(client, url=url, headers=headers, params=params, timeout=30.0)
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

        async def _get_deduction_configurations(**kwargs: Any) -> dict[str, Any]:
            params: dict[str, Any] = {}
            for source_key, api_key in (("filter", "$filter"), ("skip", "$skip"), ("top", "$top")):
                val = kwargs.get(source_key)
                if val is not None:
                    params[api_key] = val
            return await component._call(conn, path=PATH, params=params or None)

        return [
            StructuredTool.from_function(
                name="get_deduction_configurations",
                description=(
                    "Get the client's deduction-configuration catalog from ADP WFN "
                    "payroll/deduction-configurations v3. Supports OData $filter/$skip/$top."
                ),
                coroutine=_get_deduction_configurations,
                args_schema=GetDeductionConfigurationsInput,
            ),
        ]
