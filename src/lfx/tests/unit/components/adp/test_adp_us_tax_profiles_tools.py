"""Tests for adp_us_tax_profiles_tools module-level builders."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_us_tax_profiles_tools import (
    build_tax_instruction_event,
    build_us_tax_profiles_tools,
    event_path,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_event_path_supported_combos():
    assert event_path("federal", "change").endswith("federal-income-tax-instruction.change")
    assert event_path("state", "add").endswith("state-income-tax-instruction.add")
    assert event_path("state", "change").endswith("state-income-tax-instruction.change")
    assert event_path("local", "add").endswith("local-income-tax-instruction.add")
    assert event_path("local", "change").endswith("local-income-tax-instruction.change")
    assert event_path("local", "remove").endswith("local-income-tax-instruction.remove")


def test_event_path_unsupported_combo_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        event_path("federal", "add")
    with pytest.raises(ValueError, match="Unsupported"):
        event_path("state", "remove")


def test_build_federal_change_event():
    body = build_tax_instruction_event(
        jurisdiction="federal", action="change", associate_oid="G3ABC", item_id="F-1",
        fields={"additionalTaxAmount": {"amountValue": 25, "currencyCode": "USD"}},
    )
    data = body["events"][0]["data"]
    assert data["eventContext"]["federalIncomeTaxInstruction"] == {"itemID": "F-1"}
    assert data["transform"]["federalIncomeTaxInstruction"]["additionalTaxAmount"]["amountValue"] == 25


def test_build_local_remove_requires_id():
    with pytest.raises(ValueError, match="requires item_id or context_pin_fields"):
        build_tax_instruction_event(jurisdiction="local", action="remove", associate_oid="G3ABC")


def test_build_state_add_no_pin_needed():
    body = build_tax_instruction_event(
        jurisdiction="state", action="add", associate_oid="G3ABC",
        fields={"taxAuthorityCode": {"codeValue": "CA"}},
    )
    assert "stateIncomeTaxInstruction" not in body["events"][0]["data"]["eventContext"]


@pytest.mark.asyncio
async def test_read_summary_path():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_us_tax_profiles_tools._fetch_us_tax_profile", new=mock_fetch,
    ):
        tools = build_us_tax_profiles_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_worker_us_tax_profile").ainvoke(
            {"associate_oid": "G3ABC", "view": "summary"},
        )
    assert mock_fetch.call_args.kwargs["path"] == "/payroll/v1/workers/G3ABC/us-tax-profiles"


@pytest.mark.asyncio
async def test_read_state_requires_profile_id():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_us_tax_profiles_tools._fetch_us_tax_profile", new=mock_fetch,
    ):
        tools = build_us_tax_profiles_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        result = await next(t for t in tools if t.name == "get_worker_us_tax_profile").ainvoke(
            {"associate_oid": "G3ABC", "view": "state"},
        )
    assert result["status_code"] == 422
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_read_local_with_profile_id():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})
    with patch(
        "lfx.components.adp.adp_us_tax_profiles_tools._fetch_us_tax_profile", new=mock_fetch,
    ):
        tools = build_us_tax_profiles_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await next(t for t in tools if t.name == "get_worker_us_tax_profile").ainvoke(
            {"associate_oid": "G3ABC", "view": "local", "profile_id": "P-1"},
        )
    assert mock_fetch.call_args.kwargs["path"] == "/payroll/v1/workers/G3ABC/us-tax-profiles/P-1/local"


@pytest.mark.asyncio
async def test_manage_routes_state_add():
    conn = _make_connection()
    mock_post = AsyncMock(return_value={})
    with patch("lfx.components.adp.adp_us_tax_profiles_tools._post_event", new=mock_post):
        tools = build_us_tax_profiles_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        await next(t for t in tools if t.name == "manage_worker_us_tax_instruction").ainvoke(
            {
                "jurisdiction": "state",
                "action": "add",
                "associate_oid": "G3ABC",
                "fields": {"taxAuthorityCode": {"codeValue": "CA"}},
            },
        )
    assert mock_post.call_args.kwargs["path"].endswith("state-income-tax-instruction.add")


@pytest.mark.asyncio
async def test_manage_unsupported_combo_returns_422():
    conn = _make_connection()
    mock_post = AsyncMock()
    with patch("lfx.components.adp.adp_us_tax_profiles_tools._post_event", new=mock_post):
        tools = build_us_tax_profiles_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        result = await next(t for t in tools if t.name == "manage_worker_us_tax_instruction").ainvoke(
            {"jurisdiction": "federal", "action": "add", "associate_oid": "G3ABC"},
        )
    assert result["status_code"] == 422
    mock_post.assert_not_called()
