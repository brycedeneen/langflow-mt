"""ADPBenefitsToolsComponent — consolidated benefits tools.

Covers three ADP WFN benefits tiles:

- `benefits/beneficiaries v1` — `get_associate_beneficiaries` (read)
- `benefits/dependents v1` — `get_associate_dependents` (read)
- `benefits/external-plans v1` — `publish_external_benefit_plans` +
  `confirm_external_benefit_plan_data` (writes, gated). Note: ADP's published
  swagger has empty request-body schemas for these two endpoints, so the tools
  accept a `body: dict` passthrough — populate per external-partner docs.
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

PATH_BENEFICIARIES = "/benefits/v1/associates/{aoid}/beneficiaries"
PATH_DEPENDENTS = "/benefits/v1/associates/{aoid}/dependents"
PATH_EXTERNAL_PLANS_PUBLISH = "/benefits/v1/external-partner/benefit-plans"
PATH_EXTERNAL_PLAN_CONFIRM = "/event-notifications/benefits/v1/external-benefit-plan.data.confirm"


class GetAssociateBeneficiariesInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")


class GetAssociateDependentsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")


class ExternalBenefitBodyInput(BaseModel):
    body: dict[str, Any] = Field(
        description=(
            "Request body for the external-partner endpoint. ADP's swagger schemas are empty "
            "for these endpoints — populate per the ADP external-partner integration docs for "
            "your client."
        ),
    )


class ADPBenefitsToolsComponent(Component):
    display_name = "ADP Benefits Tools"
    description = (
        "Benefits tools for ADP WFN beneficiaries v1 (read), dependents v1 (read), and "
        "external-plans v1 (writes, gated). External-plans bodies are free-form per ADP's "
        "partner docs — passed through unchanged."
    )
    icon = "ShieldPlus"
    name = "ADPBenefitsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — `get_associate_beneficiaries`, `get_associate_dependents`, "
                "plus gated `publish_external_benefit_plans` + `confirm_external_benefit_plan_data`."
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
            info="Expose the external-plans write tools. Off by default.",
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

        async def _get_associate_beneficiaries(associate_oid: str) -> dict[str, Any]:
            return await component._call(
                conn, method="GET", path=PATH_BENEFICIARIES.format(aoid=associate_oid),
            )

        async def _get_associate_dependents(associate_oid: str) -> dict[str, Any]:
            return await component._call(
                conn, method="GET", path=PATH_DEPENDENTS.format(aoid=associate_oid),
            )

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_associate_beneficiaries",
                description="Get a worker's benefit beneficiaries by their ADP associate OID.",
                coroutine=_get_associate_beneficiaries,
                args_schema=GetAssociateBeneficiariesInput,
            ),
            StructuredTool.from_function(
                name="get_associate_dependents",
                description=(
                    "Get a worker's benefit dependents (spouse, children, domestic partner, "
                    "etc.) by ADP associate OID."
                ),
                coroutine=_get_associate_dependents,
                args_schema=GetAssociateDependentsInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _publish_external_benefit_plans(body: dict[str, Any]) -> dict[str, Any]:
            return await component._call(conn, method="POST", path=PATH_EXTERNAL_PLANS_PUBLISH, body=body)

        async def _confirm_external_benefit_plan_data(body: dict[str, Any]) -> dict[str, Any]:
            return await component._call(conn, method="POST", path=PATH_EXTERNAL_PLAN_CONFIRM, body=body)

        tools.append(
            StructuredTool.from_function(
                name="publish_external_benefit_plans",
                description=(
                    "POST external benefit plans to ADP WFN. Body shape is defined by ADP's "
                    "external-partner integration docs — pass the JSON payload as `body`."
                ),
                coroutine=_publish_external_benefit_plans,
                args_schema=ExternalBenefitBodyInput,
            ),
        )
        tools.append(
            StructuredTool.from_function(
                name="confirm_external_benefit_plan_data",
                description=(
                    "POST a confirmation/response to ADP WFN for an external benefit plan data "
                    "notification. Body shape is defined by ADP's external-partner docs."
                ),
                coroutine=_confirm_external_benefit_plan_data,
                args_schema=ExternalBenefitBodyInput,
            ),
        )
        return tools
