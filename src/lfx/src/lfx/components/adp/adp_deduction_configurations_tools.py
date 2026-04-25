"""ADP payroll deduction-configurations read."""

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

PATH = "/payroll/v3/deduction-configurations"


class GetDeductionConfigurationsInput(BaseModel):
    filter: str | None = Field(default=None, alias="$filter", description="OData $filter.")
    skip: int | None = Field(default=None, alias="$skip", description="OData $skip.")
    top: int | None = Field(default=None, alias="$top", description="OData $top.")

    model_config = {"populate_by_name": True}


async def _fetch_deduction_configurations(
    conn: ADPConnection,
    *,
    path: str,
    params: dict[str, Any] | None,
    request_cache: RequestCache,
) -> dict[str, Any]:
    """GET deduction configurations with cache peek before opening mTLS client."""
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


def build_deduction_configurations_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
) -> list[Tool]:
    """Build ADP deduction-configurations read tool."""
    conn = connection

    async def _get_deduction_configurations(**kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for source_key, api_key in (("filter", "$filter"), ("skip", "$skip"), ("top", "$top")):
            val = kwargs.get(source_key)
            if val is not None:
                params[api_key] = val
        return await _fetch_deduction_configurations(
            conn, path=PATH, params=params or None, request_cache=request_cache,
        )

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
