"""Tests for adp_talent_tools — path helpers, envelope builders, and build_talent_tools."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_talent_tools import (
    SERVICE_CATEGORY_CODE,
    build_ksaoc_event,
    build_talent_tools,
    event_path,
    read_path,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- path helpers -------------


def test_read_path_list():
    assert read_path("certification", associate_oid="G3ABC") == "/talent/v2/associates/G3ABC/associate-certifications"
    assert read_path("educational_degree", associate_oid="G3ABC") == (
        "/talent/v2/associates/G3ABC/associate-educational-degrees"
    )
    assert read_path("recognition", associate_oid="G3ABC") == "/talent/v2/associates/G3ABC/associate-recognitions"


def test_read_path_detail():
    assert read_path("competency", associate_oid="G3ABC", item_id="E-1") == (
        "/talent/v2/associates/G3ABC/associate-competencies/E-1"
    )


def test_read_path_unknown_kind_raises():
    with pytest.raises(ValueError, match="Unknown talent kind"):
        read_path("wombat", associate_oid="G3ABC")


def test_event_path_per_kind_and_action():
    assert event_path("certification", "add") == "/events/talent/v1/associate.ksaoc.certification.add"
    assert event_path("educational_degree", "change") == "/events/talent/v1/associate.ksaoc.educational-degree.change"
    assert event_path("license", "remove") == "/events/talent/v1/associate.ksaoc.license.remove"


# ------------- envelope builder -------------


def test_build_add_certification_event():
    body = build_ksaoc_event(
        kind="certification",
        action="add",
        associate_oid="G3ABC",
        fields={
            "certificationNameCode": {"codeValue": "CPR"},
            "firstIssueDate": "2019-09-21",
            "expirationDate": "2020-09-25",
        },
    )
    event = body["events"][0]
    assert event["serviceCategoryCode"] == {"codeValue": SERVICE_CATEGORY_CODE}
    assert event["eventNameCode"] == {"codeValue": "associate.ksaoc.certification.add"}
    assert event["actor"] == {"associateOID": "G3ABC"}

    data = event["data"]
    assert data["eventContext"] == {"associateOID": "G3ABC"}
    assert data["transform"] == {
        "associateCertification": {
            "certificationNameCode": {"codeValue": "CPR"},
            "firstIssueDate": "2019-09-21",
            "expirationDate": "2020-09-25",
        },
    }


def test_build_change_pins_item_id_in_context():
    body = build_ksaoc_event(
        kind="membership",
        action="change",
        associate_oid="G3ABC",
        item_id="M-1",
        fields={"memberTitle": "Senior Member"},
    )
    data = body["events"][0]["data"]
    assert data["eventContext"] == {
        "associateOID": "G3ABC",
        "associateMembership": {"itemID": "M-1"},
    }
    assert data["transform"] == {"associateMembership": {"memberTitle": "Senior Member"}}


def test_build_remove_requires_context_identifier():
    with pytest.raises(ValueError, match="requires item_id or context_pin_fields"):
        build_ksaoc_event(
            kind="license",
            action="remove",
            associate_oid="G3ABC",
        )


def test_build_remove_omits_transform():
    body = build_ksaoc_event(
        kind="license",
        action="remove",
        associate_oid="G3ABC",
        item_id="L-1",
    )
    data = body["events"][0]["data"]
    assert data["eventContext"] == {
        "associateOID": "G3ABC",
        "associateLicense": {"itemID": "L-1"},
    }
    assert "transform" not in data


def test_build_remove_with_natural_key_pin():
    body = build_ksaoc_event(
        kind="recognition",
        action="remove",
        associate_oid="G3ABC",
        context_pin_fields={"nameCode": {"codeValue": "Employee of the Month"}},
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx["associateRecognition"] == {"nameCode": {"codeValue": "Employee of the Month"}}


# ------------- read tool routing -------------


@pytest.mark.asyncio
async def test_read_list_with_filter_and_paging():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"associateCertifications": []}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        tool = next(t for t in tools if t.name == "get_associate_ksaoc_entries")
        await tool.ainvoke(
            {
                "kind": "certification",
                "associate_oid": "G3ABC",
                "$filter": "statusCode/codeValue eq 'A'",
                "$top": 50,
            },
        )

    assert client.request.called
    call_kwargs = client.request.call_args
    assert call_kwargs.kwargs.get("params") == {"$filter": "statusCode/codeValue eq 'A'", "$top": 50}


@pytest.mark.asyncio
async def test_read_detail_ignores_paging_params():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        tool = next(t for t in tools if t.name == "get_associate_ksaoc_entries")
        await tool.ainvoke(
            {
                "kind": "language",
                "associate_oid": "G3ABC",
                "item_id": "L-1",
                "$top": 50,
            },
        )

    # Detail path — no query params attached.
    call_kwargs = client.request.call_args
    assert "G3ABC/associate-languages/L-1" in call_kwargs.kwargs.get("url", "")
    assert call_kwargs.kwargs.get("params") is None


# ------------- manage tool gating + routing -------------


def test_build_tools_disabled_returns_only_read():
    tools = build_talent_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False)
    assert len(tools) == 1
    assert tools[0].name == "get_associate_ksaoc_entries"


def test_build_tools_enabled_returns_both():
    tools = build_talent_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
    assert {t.name for t in tools} == {"get_associate_ksaoc_entries", "manage_associate_ksaoc_entry"}


@pytest.mark.asyncio
async def test_manage_routes_add_for_certification():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {"requestID": "REQ-1"}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        await tool.ainvoke(
            {
                "kind": "certification",
                "action": "add",
                "associate_oid": "G3ABC",
                "fields": {"certificationNameCode": {"codeValue": "CPR"}},
            },
        )

    call_kwargs = client.request.call_args
    assert "/events/talent/v1/associate.ksaoc.certification.add" in call_kwargs.kwargs.get("url", "")
    body = call_kwargs.kwargs.get("json", {})
    assert body["events"][0]["data"]["transform"]["associateCertification"]["certificationNameCode"] == {
        "codeValue": "CPR",
    }


@pytest.mark.asyncio
async def test_manage_routes_remove_for_educational_degree():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        await tool.ainvoke(
            {
                "kind": "educational_degree",
                "action": "remove",
                "associate_oid": "G3ABC",
                "item_id": "DEG-1",
            },
        )

    call_kwargs = client.request.call_args
    assert "/events/talent/v1/associate.ksaoc.educational-degree.remove" in call_kwargs.kwargs.get("url", "")


@pytest.mark.asyncio
async def test_manage_remove_without_identifier_returns_validation_error():
    conn = _make_connection()
    client = MagicMock()
    client.request = AsyncMock()

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        result = await tool.ainvoke(
            {
                "kind": "license",
                "action": "remove",
                "associate_oid": "G3ABC",
            },
        )

    assert result["status_code"] == 422
    assert "item_id" in result["error"]
    client.request.assert_not_called()


@pytest.mark.asyncio
async def test_manage_recognition_add_uses_correct_entity_key():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_talent_tools.build_mtls_httpx_client", fake_client):
        tools = build_talent_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        await tool.ainvoke(
            {
                "kind": "recognition",
                "action": "add",
                "associate_oid": "G3ABC",
                "fields": {
                    "nameCode": {"codeValue": "Bravo"},
                    "issueDate": "2024-01-01",
                },
            },
        )

    body = client.request.call_args.kwargs.get("json", {})
    assert body["events"][0]["data"]["transform"].keys() == {"associateRecognition"}
