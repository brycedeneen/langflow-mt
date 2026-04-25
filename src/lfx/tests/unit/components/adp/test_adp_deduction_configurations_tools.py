"""Tests for adp_deduction_configurations_tools module-level builders."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_deduction_configurations_tools import (
    PATH,
    build_deduction_configurations_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@pytest.mark.asyncio
async def test_call_no_params():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_deduction_configurations_tools._fetch_deduction_configurations",
        new=mock_fetch,
    ):
        tools = build_deduction_configurations_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({})
    assert mock_fetch.call_args.kwargs["path"] == PATH
    assert mock_fetch.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_call_with_paging():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_deduction_configurations_tools._fetch_deduction_configurations",
        new=mock_fetch,
    ):
        tools = build_deduction_configurations_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({"$filter": "statusCode eq 'A'", "$top": 10})
    assert mock_fetch.call_args.kwargs["params"] == {"$filter": "statusCode eq 'A'", "$top": 10}


def test_path_constant():
    assert PATH == "/payroll/v3/deduction-configurations"
