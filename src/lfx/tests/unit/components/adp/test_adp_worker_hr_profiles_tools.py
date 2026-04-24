"""Tests for ADPWorkerHrProfilesToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_hr_profiles_tools import (
    ADPWorkerHrProfilesToolsComponent,
    PATH_ADDITIONAL_REMUNERATIONS,
    PATH_CORPORATE_GROUPS,
    PATH_PRIMARY_ASSIGNMENT,
    PATH_REPORTABLE_BENEFITS,
    build_corporate_group_body,
    build_primary_assignment_body,
    build_reportable_benefit_body,
    extract_additional_remunerations,
    extract_reportable_benefits,
)

SAMPLE_ADDITIONAL_REMS = {
    "associateOID": "G3ABC",
    "workerID": {"idValue": "E12345"},
    "workAssignmentID": "WA-1",
    "additionalRemunerations": [
        {
            "remunerationID": "R-1",
            "nameCode": {"codeValue": "Bonus"},
            "remunerationTypeCode": {"codeValue": "Annual"},
            "intervalCode": {"codeValue": "Yearly"},
            "remunerationRate": {"rate": {"amount": 5000.00, "currencyCode": "USD"}},
            "effectiveDate": "2026-01-01",
            "inactiveIndicator": {"indicatorValue": False},
        },
    ],
}

SAMPLE_REPORTABLE_BENEFITS = {
    "associateOID": "G3ABC",
    "workerID": {"idValue": "E12345"},
    "workAssignmentID": "WA-1",
    "reportableBenefits": [
        {
            "earningID": "EB-1",
            "earningCode": {"codeValue": "GTL"},
            "earningAmount": {"amount": 120.0, "currencyCode": "USD"},
            "itemCategoryCode": {"codeValue": "Benefit"},
            "inactiveIndicator": {"indicatorValue": False},
            "effectiveDate": "2026-01-01",
        },
    ],
}


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerHrProfilesToolsComponent(connection=connection, enable_mutations=enable_mutations)


# ---------- extractors ----------


def test_extract_additional_remunerations():
    result = extract_additional_remunerations(SAMPLE_ADDITIONAL_REMS)
    assert result["associateOID"] == "G3ABC"
    assert result["workerID"] == "E12345"
    assert result["workAssignmentID"] == "WA-1"
    assert result["additionalRemunerations"] == [
        {
            "remunerationID": "R-1",
            "nameCode": "Bonus",
            "remunerationTypeCode": "Annual",
            "intervalCode": "Yearly",
            "rate": 5000.00,
            "currencyCode": "USD",
            "effectiveDate": "2026-01-01",
            "inactive": False,
        },
    ]


def test_extract_additional_remunerations_empty():
    assert extract_additional_remunerations({}) == {
        "associateOID": None,
        "workerID": None,
        "workAssignmentID": None,
        "additionalRemunerations": [],
    }


def test_extract_reportable_benefits():
    result = extract_reportable_benefits(SAMPLE_REPORTABLE_BENEFITS)
    assert result["reportableBenefits"] == [
        {
            "earningID": "EB-1",
            "earningCode": "GTL",
            "amount": 120.0,
            "currencyCode": "USD",
            "itemCategoryCode": "Benefit",
            "inactive": False,
            "effectiveDate": "2026-01-01",
        },
    ]


# ---------- body builders ----------


def test_build_corporate_group_body_full():
    body = build_corporate_group_body(
        home_location_name="HQ",
        department_name="Engineering",
        worker_group_type="Cost Center",
        worker_group_name="CC-1001",
        status_code="Active",
        effective_date="2026-05-01",
    )
    assert body["groupStatus"] == {
        "statusCode": {"codeValue": "Active"},
        "effectiveDateTime": "2026-05-01",
    }
    assert body["homeWorkLocation"] == {"nameCode": {"codeValue": "HQ"}}
    assert body["homeOrganizationalUnits"] == [
        {"typeCode": {"codeValue": "Department"}, "nameCode": {"codeValue": "Engineering"}},
    ]
    assert body["workerGroups"] == [
        {"nameCode": {"codeValue": "Cost Center"}, "groupCode": {"codeValue": "CC-1001"}},
    ]


def test_build_corporate_group_body_additional_fields_merged():
    body = build_corporate_group_body(
        home_location_name="HQ",
        additional_fields={
            "laborUnion": {"nameCode": {"codeValue": "UAW Local 100"}},
            "bargainingUnit": {"nameCode": {"codeValue": "Detroit"}},
        },
    )
    assert body["homeWorkLocation"] == {"nameCode": {"codeValue": "HQ"}}
    assert body["laborUnion"] == {"nameCode": {"codeValue": "UAW Local 100"}}
    assert body["bargainingUnit"] == {"nameCode": {"codeValue": "Detroit"}}


def test_build_primary_assignment_body():
    body = build_primary_assignment_body(work_assignment_id="WA-2", effective_date="2026-06-01")
    assert body == {
        "effectiveDate": "2026-06-01",
        "workAssignments": [
            {"workAssignmentID": "WA-2", "primaryIndicator": {"indicatorValue": True}},
        ],
    }


def test_build_reportable_benefit_body_create():
    body = build_reportable_benefit_body(
        earning_code="GTL", amount=120.0, item_category_code="Benefit", effective_date="2026-01-01",
    )
    entry = body["reportableBenefits"][0]
    assert entry["earningCode"] == {"codeValue": "GTL"}
    assert entry["earningAmount"] == {"amount": 120.0, "currencyCode": "USD"}
    assert entry["itemCategoryCode"] == {"codeValue": "Benefit"}
    assert entry["effectiveDate"] == "2026-01-01"
    assert "earningID" not in entry


def test_build_reportable_benefit_body_update_with_earning_id_and_inactive():
    body = build_reportable_benefit_body(
        earning_code="GTL", amount=150.0, earning_id="EB-1", inactive=True,
    )
    entry = body["reportableBenefits"][0]
    assert entry["earningID"] == "EB-1"
    assert entry["inactiveIndicator"] == {"indicatorValue": True}


# ---------- mutation gate / routing ----------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_reads_only(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "read_worker_additional_remunerations",
        "read_worker_reportable_benefits",
    }


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_all_six(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "read_worker_additional_remunerations",
        "read_worker_reportable_benefits",
        "create_worker_corporate_group",
        "set_worker_primary_assignment",
        "create_worker_reportable_benefit",
        "update_worker_reportable_benefit",
    }


@pytest.mark.asyncio
async def test_mutation_tools_route_to_correct_paths_and_methods(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    captured: list[dict] = []

    async def fake_call(_conn, *, method, path, body=None):
        captured.append({"method": method, "path": path, "body": body})
        return {"ok": True}

    with patch.object(c, "_call", new=fake_call):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["create_worker_corporate_group"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1", "home_location_name": "HQ",
        })
        await tools["set_worker_primary_assignment"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-2", "effective_date": "2026-06-01",
        })
        await tools["create_worker_reportable_benefit"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1",
            "earning_code": "GTL", "amount": 120.0,
        })
        await tools["update_worker_reportable_benefit"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1",
            "earning_id": "EB-1", "amount": 150.0,
        })

    def _expand(tpl: str) -> str:
        return tpl.format(aoid="G3ABC", assignment_id="WA-1")

    assert captured[0]["method"] == "POST"
    assert captured[0]["path"] == _expand(PATH_CORPORATE_GROUPS)
    assert captured[0]["body"]["homeWorkLocation"] == {"nameCode": {"codeValue": "HQ"}}

    assert captured[1]["method"] == "PUT"
    assert captured[1]["path"] == PATH_PRIMARY_ASSIGNMENT.format(aoid="G3ABC", assignment_id="WA-2")
    assert captured[1]["body"]["workAssignments"][0]["workAssignmentID"] == "WA-2"

    assert captured[2]["method"] == "POST"
    assert captured[2]["path"] == _expand(PATH_REPORTABLE_BENEFITS)
    assert captured[2]["body"]["reportableBenefits"][0]["earningCode"] == {"codeValue": "GTL"}

    assert captured[3]["method"] == "PUT"
    assert captured[3]["path"] == _expand(PATH_REPORTABLE_BENEFITS)
    update_entry = captured[3]["body"]["reportableBenefits"][0]
    assert update_entry["earningID"] == "EB-1"
    assert update_entry["earningAmount"] == {"amount": 150.0, "currencyCode": "USD"}
    # earning_code wasn't supplied — must not be in the PUT body
    assert "earningCode" not in update_entry


@pytest.mark.asyncio
async def test_update_reportable_benefit_omits_amount_when_unset(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    captured: list[dict] = []

    async def fake_call(_conn, *, method, path, body=None):  # noqa: ARG001
        captured.append({"method": method, "body": body})
        return {"ok": True}

    with patch.object(c, "_call", new=fake_call):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["update_worker_reportable_benefit"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1",
            "earning_id": "EB-1", "inactive": True,
        })

    entry = captured[0]["body"]["reportableBenefits"][0]
    assert entry["earningID"] == "EB-1"
    assert entry["inactiveIndicator"] == {"indicatorValue": True}
    assert "earningCode" not in entry
    assert "earningAmount" not in entry


# ---------- read-tool wiring ----------


@pytest.mark.asyncio
async def test_read_additional_remunerations_hits_correct_path_and_extracts(adp_connection):
    c = _make_component(adp_connection)
    fake_response = httpx.Response(200, json=SAMPLE_ADDITIONAL_REMS)
    mock_client = MagicMock()
    captured: dict = {}

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):
        yield mock_client

    async def fake_execute(_client, *, method, url, headers, json_body, timeout):  # noqa: ARG001
        captured["method"] = method
        captured["url"] = url
        return fake_response

    with patch(
        "lfx.components.adp.adp_worker_hr_profiles_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=fake_execute):
        tools = {t.name: t for t in await c.build_tools()}
        result = await tools["read_worker_additional_remunerations"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1",
        })

    assert captured["method"] == "GET"
    expected_path = PATH_ADDITIONAL_REMUNERATIONS.format(aoid="G3ABC", assignment_id="WA-1")
    assert captured["url"].endswith(expected_path)
    assert len(result["additionalRemunerations"]) == 1


@pytest.mark.asyncio
async def test_read_reportable_benefits_returns_error_dict_on_http_error(adp_connection):
    c = _make_component(adp_connection)
    fake_response = httpx.Response(404, json={"message": "not found"})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_hr_profiles_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        tools = {t.name: t for t in await c.build_tools()}
        result = await tools["read_worker_reportable_benefits"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_id": "WA-1",
        })

    assert result["status_code"] == 404
    assert result["error"] == {"message": "not found"}
