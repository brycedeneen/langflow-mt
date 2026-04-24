"""Tests for ADPJobApplicantsToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_job_applicants_tools import (
    ADPJobApplicantsToolsComponent,
    PATH_ASSESSMENT_STATUS,
    PATH_PACKAGES_MODIFY,
    PATH_SCREENING_INITIATE,
    PATH_SCREENING_STATUS,
    build_applicant_screening_event,
    build_packages_modify_event,
)


def _make_component(connection, *, enable_mutations: bool = False) -> ADPJobApplicantsToolsComponent:
    return ADPJobApplicantsToolsComponent(connection=connection, enable_mutations=enable_mutations)


# ------------- applicant screening envelope builder -------------


def test_build_update_assessment_status_single():
    body = build_applicant_screening_event(
        action="update_assessment_status",
        agency_code="Agency1",
        applications=[
            {
                "application_id": "169744662286_1",
                "status_code": "Complete",
                "package_id": "Package3",
                "links": [{"href": "https://test-complete.com"}],
            },
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"agencyCode": {"codeValue": "Agency1"}}
    app = event["data"]["transform"]["jobApplications"][0]
    assert app["applicationID"] == "169744662286_1"
    assert app["externalAssessment"] == {
        "assessmentStatusCode": {"codeValue": "Complete"},
        "assessmentPackageID": "Package3",
        "links": [{"href": "https://test-complete.com"}],
    }


def test_build_update_assessment_status_multi():
    body = build_applicant_screening_event(
        action="update_assessment_status",
        agency_code="Agency1",
        applications=[
            {
                "application_id": "169744662286_1",
                "status_code": "In Progress",
                "package_id": "Package3",
                "links": [{"href": "https://test-complete.com"}],
            },
            {
                "application_id": "169744665423_1",
                "status_code": "In Progress",
                "package_id": "Package2",
                "links": [{"href": "https://test-complete.com"}],
            },
        ],
    )
    apps = body["events"][0]["data"]["transform"]["jobApplications"]
    assert len(apps) == 2
    assert apps[1]["externalAssessment"]["assessmentPackageID"] == "Package2"


def test_build_initiate_screening_with_screening_type_and_expiring_link():
    body = build_applicant_screening_event(
        action="initiate_screening",
        agency_code="Agency1",
        screening_type_code="ASSESSMENT",
        applications=[
            {
                "application_id": "169744662286_1",
                "package_id": "Package2",
                "links": [{"href": "http://mytests-test1.com", "link_expiration_date": "2020-07-22"}],
            },
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {
        "agencyCode": {"codeValue": "Agency1"},
        "screeningTypeCode": {"codeValue": "ASSESSMENT"},
    }
    app = event["data"]["transform"]["jobApplications"][0]
    assert app["externalBackgroundScreening"] == {
        "screeningPackageID": "Package2",
        "links": [{"href": "http://mytests-test1.com", "linkExpirationDate": "2020-07-22"}],
    }


def test_build_update_screening_status():
    body = build_applicant_screening_event(
        action="update_screening_status",
        agency_code="PartnerName",
        applications=[
            {
                "application_id": "169744662286_1",
                "status_code": "Complete",
                "links": [{"href": "http://tests.com"}],
            },
            {
                "application_id": "169744665423_1",
                "status_code": "NEW",
                "links": [{"href": "http://tests.com"}],
            },
        ],
    )
    apps = body["events"][0]["data"]["transform"]["jobApplications"]
    assert apps[0]["externalBackgroundScreening"] == {
        "screeningStatusCode": {"codeValue": "Complete"},
        "links": [{"href": "http://tests.com"}],
    }
    assert apps[1]["externalBackgroundScreening"]["screeningStatusCode"]["codeValue"] == "NEW"


# ------------- packages envelope builder -------------


def test_build_packages_single():
    body = build_packages_modify_event(
        agency_code="Agency1",
        screening_type_code="ASSESSMENT",
        packages=[
            {
                "screening_package_id": "Package3",
                "package_name": "PACKAGE THREE",
                "package_description": "Assessment3",
                "package_status_code": "Assessment",
                "package_amount": 100,
                "currency_code": "USD",
                "effective_date": "2020-03-01",
                "expiration_date": "2021-03-28",
            },
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {
        "screeningTypeCode": {"codeValue": "ASSESSMENT"},
        "agencyCode": {"codeValue": "Agency1"},
    }
    pkg = event["data"]["transform"]["externalScreeningPackages"][0]
    assert pkg == {
        "screeningPackageID": "Package3",
        "packageName": "PACKAGE THREE",
        "packageDescription": "Assessment3",
        "packageStatusCode": {"codeValue": "Assessment"},
        "packageAmount": {"amountValue": 100, "currencyCode": "USD"},
        "screeningLinkEffectiveDate": "2020-03-01",
        "screeningLinkExpirationDate": "2021-03-28",
    }


def test_build_packages_multi_with_empty_currency():
    body = build_packages_modify_event(
        agency_code="Agency1",
        screening_type_code="ASSESSMENT",
        packages=[
            {
                "screening_package_id": "Package1",
                "package_name": "PACKAGE ONE",
                "package_description": "Assessment1",
                "package_status_code": "TEST",
                "package_amount": 1006,
                "currency_code": "",
                "effective_date": "2020-03-01",
                "expiration_date": "2021-03-28",
            },
            {
                "screening_package_id": "Package2",
                "package_name": "PACKAGE TWO",
                "package_description": "Assessment1",
                "package_status_code": "TEST",
                "package_amount": 1006,
                "currency_code": "",
                "effective_date": "2020-03-01",
                "expiration_date": "2021-03-28",
            },
        ],
    )
    pkgs = body["events"][0]["data"]["transform"]["externalScreeningPackages"]
    assert len(pkgs) == 2
    # HAR sample has empty currencyCode — confirm we pass it through verbatim.
    assert pkgs[0]["packageAmount"] == {"amountValue": 1006, "currencyCode": ""}


def test_build_packages_amount_defaults_currency_to_usd_when_omitted():
    body = build_packages_modify_event(
        agency_code="Agency1",
        screening_type_code="ASSESSMENT",
        packages=[{"screening_package_id": "P1", "package_amount": 50}],
    )
    pkg = body["events"][0]["data"]["transform"]["externalScreeningPackages"][0]
    assert pkg["packageAmount"] == {"amountValue": 50, "currencyCode": "USD"}


# ------------- tool gating + routing -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_both(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"manage_applicant_screening", "publish_screening_packages"}


@pytest.mark.asyncio
async def test_manage_routes_update_assessment_status_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_applicant_screening")
        await tool.ainvoke(
            {
                "action": "update_assessment_status",
                "agency_code": "Agency1",
                "applications": [
                    {
                        "application_id": "APP-1",
                        "status_code": "Complete",
                        "package_id": "Package3",
                        "links": [{"href": "https://test.com"}],
                    },
                ],
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_ASSESSMENT_STATUS


@pytest.mark.asyncio
async def test_manage_routes_initiate_screening_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-2"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_applicant_screening")
        await tool.ainvoke(
            {
                "action": "initiate_screening",
                "agency_code": "Agency1",
                "screening_type_code": "ASSESSMENT",
                "applications": [{"application_id": "APP-1", "package_id": "Package2"}],
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_SCREENING_INITIATE


@pytest.mark.asyncio
async def test_manage_routes_update_screening_status_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-3"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_applicant_screening")
        await tool.ainvoke(
            {
                "action": "update_screening_status",
                "agency_code": "PartnerName",
                "applications": [
                    {"application_id": "APP-1", "status_code": "Complete", "links": [{"href": "http://t.com"}]},
                ],
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_SCREENING_STATUS


@pytest.mark.asyncio
async def test_publish_packages_routes_to_packages_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-4"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "publish_screening_packages")
        await tool.ainvoke(
            {
                "agency_code": "Agency1",
                "screening_type_code": "ASSESSMENT",
                "packages": [
                    {
                        "screening_package_id": "Package3",
                        "package_name": "PACKAGE THREE",
                        "package_amount": 100,
                        "effective_date": "2020-03-01",
                        "expiration_date": "2021-03-28",
                    },
                ],
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_PACKAGES_MODIFY
    body = mock_post.call_args.kwargs["body"]
    pkg = body["events"][0]["data"]["transform"]["externalScreeningPackages"][0]
    assert pkg["screeningPackageID"] == "Package3"


# ------------- POST helper -------------


@pytest.mark.asyncio
async def test_call_401_retries(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_job_applicants_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        await c._call(adp_connection, method="POST", path=PATH_SCREENING_INITIATE, body={"events": []})

    assert mock_exec.call_count == 2


def test_expected_path_constants():
    assert PATH_ASSESSMENT_STATUS == "/events/staffing/v1/job-applicant.external-assessment.status.change"
    assert PATH_SCREENING_INITIATE == "/events/staffing/v1/job-applicant.external-screening.initiate"
    assert PATH_SCREENING_STATUS == "/events/staffing/v1/job-applicant.external-screening.status.change"
    assert PATH_PACKAGES_MODIFY == "/events/staffing/v1/job-applicant.external-screening.packages.modify"
