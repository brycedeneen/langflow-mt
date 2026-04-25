"""ADP payroll pay-statements (v1) reads.

Backs ADP WFN `payroll/pay-statements v1`. All read-only:

- `get_worker_pay_statements` — list + detail consolidated (optional `pay_statement_id`
  picks detail). Supports `number_of_last_pay_dates` query param for list scope.
- `get_worker_pay_statement_image` — fetches the image (PDF/PNG/JPG) for a specific
  pay statement. Returns bytes under `content_base64` plus content-type + filename.
"""

from __future__ import annotations

import base64
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

PATH_LIST = "/payroll/v1/workers/{aoid}/organizational-pay-statements"
PATH_DETAIL = "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
PATH_IMAGE = (
    "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
    "/images/{image_id}.{image_extension}"
)


class GetWorkerPayStatementsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    pay_statement_id: str | None = Field(
        default=None,
        description="Specific pay-statement ID to fetch. Omit to list statements.",
    )
    number_of_last_pay_dates: int | None = Field(
        default=None,
        alias="numberoflastpaydates",
        description="Maximum number of statements to return (list scope only).",
    )

    model_config = {"populate_by_name": True}


class GetWorkerPayStatementImageInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    pay_statement_id: str = Field(description="Pay-statement ID the image belongs to.")
    image_id: str = Field(description="Image ID within the statement.")
    image_extension: str = Field(
        default="pdf",
        description="Image extension ('pdf', 'png', 'jpg', etc.). Default 'pdf'.",
    )


async def _fetch_pay_statements(
    conn: ADPConnection,
    *,
    path: str,
    params: dict[str, Any] | None,
    request_cache: RequestCache,
) -> dict[str, Any]:
    """GET pay-statements with cache peek before opening mTLS client."""
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


async def _fetch_image(
    conn: ADPConnection,
    *,
    path: str,
) -> dict[str, Any]:
    """Fetch a binary image; return base64-encoded bytes with content-type."""
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        response = await client.request(method="GET", url=url, headers=headers, timeout=30.0)
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request(method="GET", url=url, headers=headers, timeout=30.0)

    if response.status_code >= HTTP_CLIENT_ERROR_MIN:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return {"error": detail, "status_code": response.status_code}

    return {
        "content_type": response.headers.get("content-type", "application/octet-stream"),
        "content_length": len(response.content),
        "content_base64": base64.b64encode(response.content).decode("ascii"),
    }


def build_pay_statements_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
) -> list[Tool]:
    """Build ADP pay-statements read tools."""
    conn = connection

    async def _get_worker_pay_statements(**kwargs: Any) -> dict[str, Any]:
        associate_oid = kwargs["associate_oid"]
        pay_statement_id = kwargs.get("pay_statement_id")
        if pay_statement_id:
            path = PATH_DETAIL.format(aoid=associate_oid, pay_statement_id=pay_statement_id)
            return await _fetch_pay_statements(conn, path=path, params=None, request_cache=request_cache)
        path = PATH_LIST.format(aoid=associate_oid)
        params: dict[str, Any] = {}
        number_of_last = kwargs.get("number_of_last_pay_dates")
        if number_of_last is not None:
            params["numberoflastpaydates"] = number_of_last
        return await _fetch_pay_statements(
            conn, path=path, params=params or None, request_cache=request_cache,
        )

    async def _get_worker_pay_statement_image(
        associate_oid: str, pay_statement_id: str, image_id: str, image_extension: str = "pdf",
    ) -> dict[str, Any]:
        path = PATH_IMAGE.format(
            aoid=associate_oid,
            pay_statement_id=pay_statement_id,
            image_id=image_id,
            image_extension=image_extension,
        )
        return await _fetch_image(conn, path=path)

    return [
        StructuredTool.from_function(
            name="get_worker_pay_statements",
            description=(
                "Get a worker's pay statements. If `pay_statement_id` is provided, fetches "
                "that statement's detail (net/gross pay, earnings/deductions/memos, "
                "direct deposits, etc.). Otherwise lists statements summarized with payDate, "
                "net/gross amounts, totalHours, and payDetailUri. Optional "
                "`numberoflastpaydates` caps the list result."
            ),
            coroutine=_get_worker_pay_statements,
            args_schema=GetWorkerPayStatementsInput,
        ),
        StructuredTool.from_function(
            name="get_worker_pay_statement_image",
            description=(
                "Fetch a pay-statement image (PDF/PNG/JPG). Returns a dict with "
                "content_type, content_length, and content_base64 (base64-encoded bytes)."
            ),
            coroutine=_get_worker_pay_statement_image,
            args_schema=GetWorkerPayStatementImageInput,
        ),
    ]
