"""Tests for ADPPayStatementsToolsComponent."""

import base64
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_pay_statements_tools import (
    ADPPayStatementsToolsComponent,
    PATH_DETAIL,
    PATH_IMAGE,
    PATH_LIST,
)


def _make(connection) -> ADPPayStatementsToolsComponent:
    return ADPPayStatementsToolsComponent(connection=connection)


@pytest.mark.asyncio
async def test_list_routes_to_list_path(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC"},
        )
    assert mock_call.call_args.kwargs["path"] == PATH_LIST.format(aoid="G3ABC")
    assert mock_call.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_list_respects_numberoflastpaydates(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC", "numberoflastpaydates": 5},
        )
    assert mock_call.call_args.kwargs["params"] == {"numberoflastpaydates": 5}


@pytest.mark.asyncio
async def test_detail_routes_to_detail_path(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC", "pay_statement_id": "PS-7"},
        )
    assert mock_call.call_args.kwargs["path"] == PATH_DETAIL.format(
        aoid="G3ABC", pay_statement_id="PS-7",
    )


@pytest.mark.asyncio
async def test_image_routes_with_extension(adp_connection):
    c = _make(adp_connection)
    mock_img = AsyncMock(return_value={"content_base64": "abc", "content_type": "application/pdf"})
    with patch.object(c, "_fetch_image", new=mock_img):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "get_worker_pay_statement_image").ainvoke(
            {
                "associate_oid": "G3ABC",
                "pay_statement_id": "PS-7",
                "image_id": "IMG-1",
                "image_extension": "pdf",
            },
        )
    assert mock_img.call_args.kwargs["path"] == PATH_IMAGE.format(
        aoid="G3ABC", pay_statement_id="PS-7", image_id="IMG-1", image_extension="pdf",
    )


@pytest.mark.asyncio
async def test_fetch_image_returns_base64_and_content_type(adp_connection):
    c = _make(adp_connection)
    raw = b"%PDF-1.7\n...binary..."
    fake_response = httpx.Response(
        200, content=raw, headers={"content-type": "application/pdf"},
    )
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_pay_statements_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._fetch_image(
            adp_connection,
            path=PATH_IMAGE.format(
                aoid="G3ABC", pay_statement_id="PS-7", image_id="IMG-1", image_extension="pdf",
            ),
        )

    assert result["content_type"] == "application/pdf"
    assert result["content_length"] == len(raw)
    assert base64.b64decode(result["content_base64"]) == raw


@pytest.mark.asyncio
async def test_fetch_image_error_dict_on_404(adp_connection):
    c = _make(adp_connection)
    fake_response = httpx.Response(404, json={"errorCode": "NOT_FOUND"})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_pay_statements_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._fetch_image(adp_connection, path="/payroll/v1/workers/X/bad")

    assert result == {"error": {"errorCode": "NOT_FOUND"}, "status_code": 404}


@pytest.mark.asyncio
async def test_build_tools_returns_two_reads(adp_connection):
    c = _make(adp_connection)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"get_worker_pay_statements", "get_worker_pay_statement_image"}


def test_path_constants():
    assert PATH_LIST == "/payroll/v1/workers/{aoid}/organizational-pay-statements"
    assert PATH_DETAIL == "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
    assert PATH_IMAGE == (
        "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
        "/images/{image_id}.{image_extension}"
    )
