"""Tests for adp_pay_statements_tools module-level builders."""

import base64
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_pay_statements_tools import (
    PATH_DETAIL,
    PATH_IMAGE,
    PATH_LIST,
    build_pay_statements_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@pytest.mark.asyncio
async def test_list_routes_to_list_path():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_pay_statements_tools._fetch_pay_statements", new=mock_fetch,
    ):
        tools = build_pay_statements_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC"},
        )
    assert mock_fetch.call_args.kwargs["path"] == PATH_LIST.format(aoid="G3ABC")
    assert mock_fetch.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_list_respects_numberoflastpaydates():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_pay_statements_tools._fetch_pay_statements", new=mock_fetch,
    ):
        tools = build_pay_statements_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC", "numberoflastpaydates": 5},
        )
    assert mock_fetch.call_args.kwargs["params"] == {"numberoflastpaydates": 5}


@pytest.mark.asyncio
async def test_detail_routes_to_detail_path():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_pay_statements_tools._fetch_pay_statements", new=mock_fetch,
    ):
        tools = build_pay_statements_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_worker_pay_statements").ainvoke(
            {"associate_oid": "G3ABC", "pay_statement_id": "PS-7"},
        )
    assert mock_fetch.call_args.kwargs["path"] == PATH_DETAIL.format(
        aoid="G3ABC", pay_statement_id="PS-7",
    )


@pytest.mark.asyncio
async def test_image_routes_with_extension():
    conn = _make_connection()
    mock_img = AsyncMock(return_value={"content_base64": "abc", "content_type": "application/pdf"})
    with patch("lfx.components.adp.adp_pay_statements_tools._fetch_image", new=mock_img):
        tools = build_pay_statements_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
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
async def test_fetch_image_returns_base64_and_content_type():
    conn = _make_connection()
    raw = b"%PDF-1.7\n...binary..."
    fake_response = httpx.Response(
        200, content=raw, headers={"content-type": "application/pdf"},
    )
    client = MagicMock()
    client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_pay_statements_tools.build_mtls_httpx_client", fake_client):
        from lfx.components.adp.adp_pay_statements_tools import _fetch_image
        result = await _fetch_image(
            conn,
            path=PATH_IMAGE.format(
                aoid="G3ABC", pay_statement_id="PS-7", image_id="IMG-1", image_extension="pdf",
            ),
        )

    assert result["content_type"] == "application/pdf"
    assert result["content_length"] == len(raw)
    assert base64.b64decode(result["content_base64"]) == raw


@pytest.mark.asyncio
async def test_fetch_image_error_dict_on_404():
    conn = _make_connection()
    fake_response = httpx.Response(404, json={"errorCode": "NOT_FOUND"})
    client = MagicMock()
    client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_pay_statements_tools.build_mtls_httpx_client", fake_client):
        from lfx.components.adp.adp_pay_statements_tools import _fetch_image
        result = await _fetch_image(conn, path="/payroll/v1/workers/X/bad")

    assert result == {"error": {"errorCode": "NOT_FOUND"}, "status_code": 404}


@pytest.mark.asyncio
async def test_build_tools_returns_two_reads():
    tools = build_pay_statements_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert {t.name for t in tools} == {"get_worker_pay_statements", "get_worker_pay_statement_image"}


def test_path_constants():
    assert PATH_LIST == "/payroll/v1/workers/{aoid}/organizational-pay-statements"
    assert PATH_DETAIL == "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
    assert PATH_IMAGE == (
        "/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay_statement_id}"
        "/images/{image_id}.{image_extension}"
    )
