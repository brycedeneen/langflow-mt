"""ADPPayStatementsToolsComponent — payroll pay-statements (v1) reads.

Backs ADP WFN `payroll/pay-statements v1`. All read-only:

- `get_worker_pay_statements` — list + detail consolidated (optional `pay_statement_id`
  picks detail). Supports `number_of_last_pay_dates` query param for list scope.
- `get_worker_pay_statement_image` — fetches the image (PDF/PNG/JPG) for a specific
  pay statement. Returns bytes under `content_base64` plus content-type + filename.
"""

from __future__ import annotations

import base64
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


class ADPPayStatementsToolsComponent(Component):
    display_name = "ADP Pay Statements Tools"
    description = (
        "Read tools for ADP WFN `payroll/pay-statements v1`. `get_worker_pay_statements` "
        "lists or fetches pay statements. `get_worker_pay_statement_image` retrieves the "
        "statement image (PDF/PNG/JPG) as base64-encoded bytes."
    )
    icon = "ReceiptText"
    name = "ADPPayStatementsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 agent tools for ADP WFN payroll/pay-statements v1: "
                "`get_worker_pay_statements` (list + detail consolidated) and "
                "`get_worker_pay_statement_image` (binary fetch, base64-encoded). Read-only tile."
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
            method="GET", url=url, headers=headers, params=params, timeout=timeout,
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

    async def _fetch_image(self, conn: ADPConnection, *, path: str) -> dict[str, Any]:
        """Fetch a binary image; return base64-encoded bytes with content-type."""
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(
                client, url=url, headers=headers, params=None, timeout=30.0,
            )
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, url=url, headers=headers, params=None, timeout=30.0,
                )

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

    async def build_tools(self) -> list[Tool]:
        conn: ADPConnection = self.connection
        component = self

        async def _get_worker_pay_statements(**kwargs: Any) -> dict[str, Any]:
            associate_oid = kwargs["associate_oid"]
            pay_statement_id = kwargs.get("pay_statement_id")
            if pay_statement_id:
                path = PATH_DETAIL.format(aoid=associate_oid, pay_statement_id=pay_statement_id)
                return await component._call(conn, path=path)
            path = PATH_LIST.format(aoid=associate_oid)
            params: dict[str, Any] = {}
            number_of_last = kwargs.get("number_of_last_pay_dates")
            if number_of_last is not None:
                params["numberoflastpaydates"] = number_of_last
            return await component._call(conn, path=path, params=params or None)

        async def _get_worker_pay_statement_image(
            associate_oid: str, pay_statement_id: str, image_id: str, image_extension: str = "pdf",
        ) -> dict[str, Any]:
            path = PATH_IMAGE.format(
                aoid=associate_oid,
                pay_statement_id=pay_statement_id,
                image_id=image_id,
                image_extension=image_extension,
            )
            return await component._fetch_image(conn, path=path)

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
