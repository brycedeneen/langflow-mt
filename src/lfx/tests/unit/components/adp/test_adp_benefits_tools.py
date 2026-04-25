"""Tests for adp_benefits_tools — build_benefits_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_benefits_tools import (
    PATH_BENEFICIARIES,
    PATH_DEPENDENTS,
    PATH_EXTERNAL_PLAN_CONFIRM,
    PATH_EXTERNAL_PLANS_PUBLISH,
    build_benefits_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@pytest.mark.asyncio
async def test_read_tools_routing():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_benefits_tools.build_mtls_httpx_client", fake_client):
        tools = build_benefits_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))

        await next(t for t in tools if t.name == "get_associate_beneficiaries").ainvoke({"associate_oid": "G3ABC"})
        assert PATH_BENEFICIARIES.format(aoid="G3ABC") in mock_client.request.call_args.kwargs.get("url", "")

        mock_client.request.reset_mock()
        await next(t for t in tools if t.name == "get_associate_dependents").ainvoke({"associate_oid": "G3ABC"})
        assert PATH_DEPENDENTS.format(aoid="G3ABC") in mock_client.request.call_args.kwargs.get("url", "")


def test_write_tools_gated():
    tools = build_benefits_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False,
    )
    names = {t.name for t in tools}
    assert "publish_external_benefit_plans" not in names
    assert "confirm_external_benefit_plan_data" not in names

    tools = build_benefits_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    names = {t.name for t in tools}
    assert "publish_external_benefit_plans" in names
    assert "confirm_external_benefit_plan_data" in names


@pytest.mark.asyncio
async def test_publish_and_confirm_routes():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    with patch("lfx.components.adp.adp_benefits_tools.build_mtls_httpx_client", fake_client):
        tools = build_benefits_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )

        await next(t for t in tools if t.name == "publish_external_benefit_plans").ainvoke({"body": {"x": 1}})
        call_kwargs = mock_client.request.call_args.kwargs
        assert PATH_EXTERNAL_PLANS_PUBLISH in call_kwargs.get("url", "")
        assert call_kwargs.get("json") == {"x": 1}

        mock_client.request.reset_mock()
        await next(t for t in tools if t.name == "confirm_external_benefit_plan_data").ainvoke({"body": {"y": 2}})
        assert PATH_EXTERNAL_PLAN_CONFIRM in mock_client.request.call_args.kwargs.get("url", "")
