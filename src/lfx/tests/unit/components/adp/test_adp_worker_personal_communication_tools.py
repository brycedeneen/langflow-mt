"""Tests for ADPWorkerPersonalCommunicationToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_personal_communication_tools import (
    ADPWorkerPersonalCommunicationToolsComponent,
    build_address_event,
    build_email_event,
    build_phone_event,
)


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerPersonalCommunicationToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
    # Remove event has no transform.worker
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


# ---------------- gating + tool registration ----------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_three_tools(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "update_employee_address",
        "update_employee_phone",
        "update_employee_email",
    }


@pytest.mark.asyncio
async def test_tool_invocation_routes_to_correct_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "R-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        phone_tool = next(t for t in tools if t.name == "update_employee_phone")
        result = await phone_tool.ainvoke({
            "operation": "add",
            "phone_type": "mobile",
            "associate_oid": "G3ABC",
            "formatted_number": "555-0199",
        })

    assert result == {"confirmMessage": {"requestID": "R-1"}}
    call = mock_post.call_args
    assert call.kwargs["path"] == "/events/hr/v1/worker.personal-communication.mobile.add"


@pytest.mark.asyncio
async def test_post_event_401_retries_with_fresh_token(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"confirmMessage": {"requestID": "R-2"}}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "new-token"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_worker_personal_communication_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_worker_personal_communication_tools.fetch_token",
        new=AsyncMock(side_effect=fake_refresh),
    ):
        await c._post_event(adp_connection, path="/events/hr/v1/worker.personal-communication.email.add", body={})

    assert mock_exec.call_count == 2
