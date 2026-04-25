"""ADP benefits tools — module-level builder.

Covers three ADP WFN benefits tiles:

- `benefits/beneficiaries v1` — `get_associate_beneficiaries` (read)
- `benefits/dependents v1` — `get_associate_dependents` (read)
- `benefits/external-plans v1` — `publish_external_benefit_plans` +
  `confirm_external_benefit_plan_data` (writes, gated). Note: ADP's published
  swagger has empty request-body schemas for these two endpoints, so the tools
  accept a `body: dict` passthrough — populate per external-partner docs.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_CLIENT_ERROR_MIN,
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

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


async def _fetch_benefits(
    conn: ADPConnection,
    *,
    path: str,
    request_cache: RequestCache,
) -> dict[str, Any]:
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


def build_benefits_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    conn = connection

    async def _get_associate_beneficiaries(associate_oid: str) -> dict[str, Any]:
        return await _fetch_benefits(
            conn,
            path=PATH_BENEFICIARIES.format(aoid=associate_oid),
            request_cache=request_cache,
        )

    async def _get_associate_dependents(associate_oid: str) -> dict[str, Any]:
        return await _fetch_benefits(
            conn,
            path=PATH_DEPENDENTS.format(aoid=associate_oid),
            request_cache=request_cache,
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

    if not enable_mutations:
        return tools

    async def _publish_external_benefit_plans(body: dict[str, Any]) -> dict[str, Any]:
        return await _post_event(conn, path=PATH_EXTERNAL_PLANS_PUBLISH, body=body)

    async def _confirm_external_benefit_plan_data(body: dict[str, Any]) -> dict[str, Any]:
        return await _post_event(conn, path=PATH_EXTERNAL_PLAN_CONFIRM, body=body)

    tools.append(
        StructuredTool.from_function(
            name="publish_external_benefit_plans",
            description=(
                "POST external benefit plans to ADP WFN (carrier-to-ADP feed). Unlike ADP's "
                "event-envelope APIs, this endpoint uses a PascalCase EDI-style payload with "
                "top-level TransmissionGUID, SenderName, ReceiverName, CreationDateTime, "
                "TestProductionCode ('Test'|'Production'), TransmissionTypeCode ('FullFile'|"
                "'Delta'), SchemaVersionIdentifier, and Employers.Employer[] — each Employer "
                "carries ClientEvents.ClientEvent[].BenefitPlanEvents.BenefitPlanEvent[] with "
                "plan details (PlanDisplayName, BenefitPlanIdentifier, ProductType, "
                "CoverageTier, GroupPolicyNumber, PlanAnniversary, enrollments, rate tiers, "
                "etc.). Pass the full JSON payload as `body` per ADP's carrier-feed docs."
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


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.
# ---------------------------------------------------------------------------
class ADPBenefitsToolsComponent:
    name = "ADPBenefitsTools"
