"""Tests for adp_worker_personal_communication_tools — build_worker_personal_communication_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_personal_communication_tools import (
    build_address_event,
    build_email_event,
    build_phone_event,
    build_worker_personal_communication_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ---------------- address envelope builder ----------------


def test_build_address_event_legal_add():
    path, body = build_address_event(
        operation="add",
        address_type="legal",
        associate_oid="G3ABC",
        line_one="123 Main St",
        city_name="Springfield",
        country_subdivision_code="IL",
        postal_code="62704",
        country_code="US",
    )
    assert path == "/events/hr/v1/worker.legal-address.add"
    transform_addr = body["events"][0]["data"]["transform"]["worker"]["person"]["legalAddress"]
    assert transform_addr["lineOne"] == "123 Main St"
    assert transform_addr["countrySubdivisionLevel1"] == {"codeValue": "IL"}


def test_build_address_event_personal_add_is_list():
    path, body = build_address_event(
        operation="add",
        address_type="personal",
        associate_oid="G3ABC",
        line_one="1 Vacation Ln",
        label="Summer Home",
    )
    assert path == "/events/hr/v1/worker.personal-address.add"
    addrs = body["events"][0]["data"]["transform"]["worker"]["person"]["otherPersonalAddresses"]
    assert isinstance(addrs, list)
    assert addrs[0]["lineOne"] == "1 Vacation Ln"
    assert addrs[0]["nameCode"] == {"codeValue": "Summer Home"}


def test_build_address_event_personal_change_requires_item_id():
    path, body = build_address_event(
        operation="change",
        address_type="personal",
        associate_oid="G3ABC",
        address_item_id="ADDR-1",
        line_one="2 New St",
    )
    assert path == "/events/hr/v1/worker.personal-address.change"
    ctx = body["events"][0]["data"]["eventContext"]["worker"]
    assert ctx["person"]["otherPersonalAddresses"] == {"itemID": "ADDR-1"}
    addrs = body["events"][0]["data"]["transform"]["worker"]["person"]["otherPersonalAddresses"]
    assert addrs[0]["itemID"] == "ADDR-1"
    assert addrs[0]["lineOne"] == "2 New St"


def test_build_address_event_personal_change_missing_item_id_raises():
    with pytest.raises(ValueError, match="address_item_id"):
        build_address_event(
            operation="change",
            address_type="personal",
            associate_oid="G3ABC",
            line_one="x",
        )


def test_build_address_event_personal_remove():
    path, body = build_address_event(
        operation="remove",
        address_type="personal",
        associate_oid="G3ABC",
        address_item_id="ADDR-1",
    )
    assert path == "/events/hr/v1/worker.personal-address.remove"
    ctx = body["events"][0]["data"]["eventContext"]["worker"]
    assert ctx["person"]["otherPersonalAddresses"] == [{"itemID": "ADDR-1"}]
    assert "worker" not in body["events"][0]["data"]["transform"]


# ---------------- phone envelope builder ----------------


def test_build_phone_event_landline_add():
    path, body = build_phone_event(
        operation="add",
        phone_type="landline",
        associate_oid="G3ABC",
        formatted_number="555-0100",
        label="Home",
    )
    assert path == "/events/hr/v1/worker.personal-communication.landline.add"
    landlines = body["events"][0]["data"]["transform"]["worker"]["person"]["communication"]["landlines"]
    assert landlines[0]["formattedNumber"] == "555-0100"
    assert landlines[0]["nameCode"] == {"codeValue": "Home"}


def test_build_phone_event_mobile_change_requires_item_id_in_ctx_and_transform():
    path, body = build_phone_event(
        operation="change",
        phone_type="mobile",
        associate_oid="G3ABC",
        phone_item_id="PH-9",
        formatted_number="555-0199",
    )
    assert path == "/events/hr/v1/worker.personal-communication.mobile.change"
    ctx = body["events"][0]["data"]["eventContext"]["worker"]
    assert ctx["person"]["communication"]["mobiles"] == [{"itemID": "PH-9"}]
    transform_mobiles = (
        body["events"][0]["data"]["transform"]["worker"]["person"]["communication"]["mobiles"]
    )
    assert transform_mobiles[0]["itemID"] == "PH-9"
    assert transform_mobiles[0]["formattedNumber"] == "555-0199"


def test_build_phone_event_fax_remove():
    path, body = build_phone_event(
        operation="remove",
        phone_type="fax",
        associate_oid="G3ABC",
        phone_item_id="FX-1",
    )
    assert path == "/events/hr/v1/worker.personal-communication.fax.remove"
    ctx = body["events"][0]["data"]["eventContext"]["worker"]
    assert ctx["person"]["communication"]["faxes"] == [{"itemID": "FX-1"}]
    assert "worker" not in body["events"][0]["data"]["transform"]


def test_build_phone_event_pager_change_missing_item_id_raises():
    with pytest.raises(ValueError, match="phone_item_id"):
        build_phone_event(
            operation="change",
            phone_type="pager",
            associate_oid="G3ABC",
            formatted_number="x",
        )


# ---------------- email envelope builder ----------------


def test_build_email_event_add():
    path, body = build_email_event(
        operation="add",
        associate_oid="G3ABC",
        email_uri="jane.personal@example.com",
        label="Personal",
    )
    assert path == "/events/hr/v1/worker.personal-communication.email.add"
    emails = body["events"][0]["data"]["transform"]["worker"]["person"]["communication"]["emails"]
    assert emails[0]["emailUri"] == "jane.personal@example.com"
    assert emails[0]["nameCode"] == {"codeValue": "Personal"}


def test_build_email_event_change():
    path, body = build_email_event(
        operation="change",
        associate_oid="G3ABC",
        email_item_id="EM-1",
        email_uri="jane.new@example.com",
    )
    assert path == "/events/hr/v1/worker.personal-communication.email.change"
    assert body["events"][0]["data"]["eventContext"]["worker"]["person"]["communication"]["emails"] == [
        {"itemID": "EM-1"},
    ]
    emails = body["events"][0]["data"]["transform"]["worker"]["person"]["communication"]["emails"]
    assert emails[0]["itemID"] == "EM-1"
    assert emails[0]["emailUri"] == "jane.new@example.com"


def test_build_email_event_remove():
    path, body = build_email_event(
        operation="remove",
        associate_oid="G3ABC",
        email_item_id="EM-1",
    )
    assert path == "/events/hr/v1/worker.personal-communication.email.remove"
    assert body["events"][0]["data"]["eventContext"]["worker"]["person"]["communication"]["emails"] == [
        {"itemID": "EM-1"},
    ]
    assert "worker" not in body["events"][0]["data"]["transform"]


def test_build_email_event_change_missing_item_id_raises():
    with pytest.raises(ValueError, match="email_item_id"):
        build_email_event(operation="change", associate_oid="G3ABC", email_uri="x")


# ---------------- effective date + reason_code ----------------


def test_envelope_effective_date_and_reason_code():
    _path, body = build_email_event(
        operation="add",
        associate_oid="G3ABC",
        email_uri="x@y.com",
        effective_date="2026-05-01",
        reason_code="Correction",
    )
    transform = body["events"][0]["data"]["transform"]
    assert transform["effectiveDateTime"] == "2026-05-01"
    assert transform["eventReasonCode"] == {"codeValue": "Correction"}


# ---------------- builder tests ----------------


@pytest.mark.asyncio
async def test_build_tools_returns_three_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_personal_communication_tools(conn, cache)
    assert {t.name for t in tools} == {
        "update_employee_address",
        "update_employee_phone",
        "update_employee_email",
    }


@pytest.mark.asyncio
async def test_tool_invocation_routes_to_correct_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "R-1"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_personal_communication_tools(conn, cache)}

    with patch(
        "lfx.components.adp.adp_worker_personal_communication_tools.build_mtls_httpx_client", fake_client,
    ):
        result = await tools["update_employee_phone"].ainvoke({
            "operation": "add",
            "phone_type": "mobile",
            "associate_oid": "G3ABC",
            "formatted_number": "555-0199",
        })

    assert result == {"confirmMessage": {"requestID": "R-1"}}
    posted_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert "/events/hr/v1/worker.personal-communication.mobile.add" in posted_url


@pytest.mark.asyncio
async def test_post_event_401_retries_with_fresh_token():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"error": "expired"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = {"confirmMessage": {"requestID": "R-2"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    async def fake_refresh(conn_arg, *, force=False):
        assert force is True
        conn_arg.access_token = "new-token"  # noqa: S105

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_personal_communication_tools(conn, cache)}

    with patch(
        "lfx.components.adp.adp_worker_personal_communication_tools.build_mtls_httpx_client", fake_client,
    ), patch(
        "lfx.components.adp.adp_worker_personal_communication_tools.fetch_token",
        AsyncMock(side_effect=fake_refresh),
    ):
        await tools["update_employee_email"].ainvoke({
            "operation": "add",
            "associate_oid": "G3ABC",
            "email_uri": "x@y.com",
        })

    assert client.request.await_count == 2
