"""Tests for adp_job_applicants_tools — envelope builders and build_job_applicants_tools."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_job_applicants_tools import (
    PATH_ASSESSMENT_STATUS,
    PATH_PACKAGES_MODIFY,
    PATH_SCREENING_INITIATE,
    PATH_SCREENING_STATUS,
    build_applicant_screening_event,
    build_job_applicants_tools,
    build_packages_modify_event,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


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


def test_build_tools_disabled_returns_empty():
    tools = build_job_applicants_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False,
    )
    assert tools == []


def test_build_tools_enabled_returns_both():
    tools = build_job_applicants_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    assert {t.name for t in tools} == {"manage_applicant_screening", "publish_screening_packages"}


@pytest.mark.asyncio
async def test_manage_routes_update_assessment_status_path():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {"requestID": "REQ-1"}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_applicants_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
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

    assert PATH_ASSESSMENT_STATUS in client.request.call_args.kwargs.get("url", "")


@pytest.mark.asyncio
async def test_manage_routes_initiate_screening_path():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {"requestID": "REQ-2"}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_applicants_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_applicant_screening")
        await tool.ainvoke(
            {
                "action": "initiate_screening",
                "agency_code": "Agency1",
                "screening_type_code": "ASSESSMENT",
                "applications": [{"application_id": "APP-1", "package_id": "Package2"}],
            },
        )

    assert PATH_SCREENING_INITIATE in client.request.call_args.kwargs.get("url", "")


@pytest.mark.asyncio
async def test_manage_routes_update_screening_status_path():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {"requestID": "REQ-3"}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_applicants_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
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

    assert PATH_SCREENING_STATUS in client.request.call_args.kwargs.get("url", "")


@pytest.mark.asyncio
async def test_publish_packages_routes_to_packages_path():
    conn = _make_connection()
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"confirmMessage": {"requestID": "REQ-4"}}
    client.request = AsyncMock(return_value=mock_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client", fake_client):
        tools = build_job_applicants_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
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

    assert PATH_PACKAGES_MODIFY in client.request.call_args.kwargs.get("url", "")
    body = client.request.call_args.kwargs.get("json", {})
    pkg = body["events"][0]["data"]["transform"]["externalScreeningPackages"][0]
    assert pkg["screeningPackageID"] == "Package3"


# ------------- POST helper — 401 retry -------------


@pytest.mark.asyncio
async def test_post_event_401_retries():
    conn = _make_connection()
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_client = MagicMock()
    mock_client.request = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_job_applicants_tools.build_mtls_httpx_client",
        new=fake_client,
    ), patch(
        "lfx.components.adp.adp_job_applicants_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        tools = build_job_applicants_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
        tool = next(t for t in tools if t.name == "manage_applicant_screening")
        await tool.ainvoke(
            {
                "action": "initiate_screening",
                "agency_code": "Agency1",
                "applications": [{"application_id": "APP-1"}],
            },
        )

    assert mock_client.request.call_count == 2


def test_expected_path_constants():
    assert PATH_ASSESSMENT_STATUS == "/events/staffing/v1/job-applicant.external-assessment.status.change"
    assert PATH_SCREENING_INITIATE == "/events/staffing/v1/job-applicant.external-screening.initiate"
    assert PATH_SCREENING_STATUS == "/events/staffing/v1/job-applicant.external-screening.status.change"
    assert PATH_PACKAGES_MODIFY == "/events/staffing/v1/job-applicant.external-screening.packages.modify"
