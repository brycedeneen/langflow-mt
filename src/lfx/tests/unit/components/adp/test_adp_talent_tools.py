"""Tests for ADPTalentToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_talent_tools import (
    ADPTalentToolsComponent,
    SERVICE_CATEGORY_CODE,
    build_ksaoc_event,
    event_path,
    read_path,
)


def _make_component(connection, *, enable_mutations: bool = False) -> ADPTalentToolsComponent:
    return ADPTalentToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
async def test_read_list_with_filter_and_paging(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={"associateCertifications": []})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "get_associate_ksaoc_entries")
        await tool.ainvoke(
            {
                "kind": "certification",
                "associate_oid": "G3ABC",
                "$filter": "statusCode/codeValue eq 'A'",
                "$top": 50,
            },
        )

    assert mock_call.call_args.kwargs["method"] == "GET"
    assert mock_call.call_args.kwargs["path"] == "/talent/v2/associates/G3ABC/associate-certifications"
    assert mock_call.call_args.kwargs["params"] == {
        "$filter": "statusCode/codeValue eq 'A'",
        "$top": 50,
    }


@pytest.mark.asyncio
async def test_read_detail_ignores_paging_params(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
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
    assert mock_call.call_args.kwargs["path"] == "/talent/v2/associates/G3ABC/associate-languages/L-1"
    assert mock_call.call_args.kwargs["params"] is None


# ------------- manage tool gating + routing -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_only_read(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert len(tools) == 1
    assert tools[0].name == "get_associate_ksaoc_entries"


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_both(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"get_associate_ksaoc_entries", "manage_associate_ksaoc_entry"}


@pytest.mark.asyncio
async def test_manage_routes_add_for_certification(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        await tool.ainvoke(
            {
                "kind": "certification",
                "action": "add",
                "associate_oid": "G3ABC",
                "fields": {"certificationNameCode": {"codeValue": "CPR"}},
            },
        )

    assert mock_post.call_args.kwargs["path"] == "/events/talent/v1/associate.ksaoc.certification.add"
    body = mock_post.call_args.kwargs["body"]
    assert body["events"][0]["data"]["transform"]["associateCertification"]["certificationNameCode"] == {
        "codeValue": "CPR",
    }


@pytest.mark.asyncio
async def test_manage_routes_remove_for_educational_degree(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_associate_ksaoc_entry")
        await tool.ainvoke(
            {
                "kind": "educational_degree",
                "action": "remove",
                "associate_oid": "G3ABC",
                "item_id": "DEG-1",
            },
        )

    assert mock_post.call_args.kwargs["path"] == "/events/talent/v1/associate.ksaoc.educational-degree.remove"


@pytest.mark.asyncio
async def test_manage_remove_without_identifier_returns_validation_error(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock()

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
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
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_manage_recognition_add_uses_correct_entity_key(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
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

    body = mock_post.call_args.kwargs["body"]
    assert body["events"][0]["data"]["transform"].keys() == {"associateRecognition"}
