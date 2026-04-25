"""ADP job-requisitions read tools — module-level builder.

Backs the ADP WFN `staffing/job-requisitions v1` tile. Exposes a single
consolidated read tool (list + detail) since the tile is read-only and
the response payload, while broad, is flat enough to return whole.
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

PATH_LIST = "/staffing/v1/job-requisitions"
PATH_DETAIL = "/staffing/v1/job-requisitions/{job_requisition_id}"


class GetJobRequisitionsInput(BaseModel):
    job_requisition_id: str | None = Field(
        default=None,
        description="Specific job-requisition ID to fetch. Omit to list requisitions.",
    )
    filter: str | None = Field(
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


async def _fetch_requisitions(
    conn: ADPConnection,
    *,
    path: str,
    params: dict[str, Any] | None = None,
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
        result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers, params=params)
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers, params=params)

    return result


def build_job_requisitions_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]:
    conn = connection

    async def _get_job_requisitions(
        job_requisition_id: str | None = None,
        filter: str | None = None,  # noqa: A002
        skip: int | None = None,
        top: int | None = None,
    ) -> dict[str, Any]:
        if job_requisition_id:
            return await _fetch_requisitions(
                conn,
                path=PATH_DETAIL.format(job_requisition_id=job_requisition_id),
                request_cache=request_cache,
            )
        params: dict[str, Any] = {}
        if filter is not None:
            params["$filter"] = filter
        if skip is not None:
            params["$skip"] = skip
        if top is not None:
            params["$top"] = top
        return await _fetch_requisitions(conn, path=PATH_LIST, params=params or None, request_cache=request_cache)

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


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.
# ---------------------------------------------------------------------------
class ADPJobRequisitionsToolsComponent:
    name = "ADPJobRequisitionsTools"
