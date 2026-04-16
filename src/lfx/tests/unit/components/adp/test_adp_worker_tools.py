"""Tests for ADPWorkerToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_tools import ADPWorkerToolsComponent, extract_name, extract_addresses, extract_contact_information, extract_job, extract_compensation

SAMPLE_WORKER_RESPONSE = {
    "workers": [
        {
            "associateOID": "G3ABC",
            "person": {
                "legalName": {
                    "givenName": "Jane",
                    "middleName": "Marie",
                    "familyName1": "Doe",
                },
                "preferredName": {
                    "givenName": "Janie",
                    "familyName1": "Doe",
                },
                "legalAddress": {
                    "lineOne": "123 Main St",
                    "lineTwo": "Apt 4",
                    "cityName": "Springfield",
                    "countrySubdivisionLevel1": {"codeValue": "IL"},
                    "postalCode": "62704",
                    "countryCode": "US",
                },
                "communication": {
                    "emails": [
                        {"emailUri": "jane@example.com", "nameCode": {"codeValue": "Work"}},
                    ],
                    "landlines": [
                        {"formattedNumber": "555-0100", "nameCode": {"codeValue": "Work"}},
                    ],
                    "mobiles": [
                        {"formattedNumber": "555-0199", "nameCode": {"codeValue": "Personal"}},
                    ],
                },
            },
            "workerStatus": {"statusCode": {"codeValue": "Active"}},
            "workAssignments": [
                {
                    "jobTitle": "Software Engineer",
                    "homeOrganizationalUnits": [
                        {"typeCode": {"codeValue": "Department"}, "nameCode": {"codeValue": "Engineering"}},
                    ],
                    "homeWorkLocation": {"nameCode": {"codeValue": "Remote"}},
                    "managementPosition": {"indicatorCode": {"codeValue": "false"}},
                    "reportsTo": [
                        {
                            "associateOID": "G3XYZ",
                            "reportsToWorkerName": {"formattedName": "Bob Smith"},
                        },
                    ],
                    "baseRemuneration": {
                        "payPeriodRateAmount": {"amountValue": 5000.00, "currencyCode": "USD"},
                        "annualRateAmount": {"amountValue": 120000.00, "currencyCode": "USD"},
                        "effectiveDate": "2025-01-01",
                    },
                    "additionalRemunerations": [
                        {
                            "nameCode": {"codeValue": "Bonus"},
                            "rate": {"rateAmount": {"amountValue": 10000.00, "currencyCode": "USD"}},
                        },
                    ],
                },
            ],
        }
    ]
}


def _make_component(connection, **overrides) -> ADPWorkerToolsComponent:
    defaults = {
        "connection": connection,
    }
    defaults.update(overrides)
    return ADPWorkerToolsComponent(**defaults)


def test_extract_name(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_name(worker)
    assert result == {
        "legalName": {"firstName": "Jane", "middleName": "Marie", "lastName": "Doe"},
        "preferredName": {"firstName": "Janie", "lastName": "Doe"},
    }


def test_extract_name_missing_preferred(adp_connection):
    worker = {
        "person": {
            "legalName": {"givenName": "Jane", "familyName1": "Doe"},
        },
    }
    result = extract_name(worker)
    assert result == {
        "legalName": {"firstName": "Jane", "middleName": None, "lastName": "Doe"},
        "preferredName": None,
    }


def test_extract_addresses(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_addresses(worker)
    assert result == {
        "legalAddress": {
            "lineOne": "123 Main St",
            "lineTwo": "Apt 4",
            "cityName": "Springfield",
            "countrySubdivisionLevel1": "IL",
            "postalCode": "62704",
            "countryCode": "US",
        },
    }


def test_extract_addresses_missing(adp_connection):
    worker = {"person": {}}
    result = extract_addresses(worker)
    assert result == {"legalAddress": None}


def test_extract_contact_information(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_contact_information(worker)
    assert result == {
        "emails": [{"emailUri": "jane@example.com", "nameCode": {"codeValue": "Work"}}],
        "landlines": [{"formattedNumber": "555-0100", "nameCode": {"codeValue": "Work"}}],
        "mobiles": [{"formattedNumber": "555-0199", "nameCode": {"codeValue": "Personal"}}],
    }


def test_extract_contact_information_missing(adp_connection):
    worker = {"person": {}}
    result = extract_contact_information(worker)
    assert result == {"emails": [], "landlines": [], "mobiles": []}


def test_extract_job(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_job(worker)
    assert result == {
        "jobTitle": "Software Engineer",
        "departmentName": "Engineering",
        "locationName": "Remote",
        "workerStatus": "Active",
        "managementPosition": False,
        "reportsTo": {"associateOID": "G3XYZ", "workerName": "Bob Smith"},
    }


def test_extract_job_missing_assignment(adp_connection):
    worker = {"workAssignments": [], "workerStatus": {"statusCode": {"codeValue": "Active"}}}
    result = extract_job(worker)
    assert result == {
        "jobTitle": None,
        "departmentName": None,
        "locationName": None,
        "workerStatus": "Active",
        "managementPosition": None,
        "reportsTo": None,
    }


def test_extract_compensation(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_compensation(worker)
    assert result == {
        "baseRemuneration": {
            "payPeriodAmount": 5000.00,
            "annualAmount": 120000.00,
            "currencyCode": "USD",
            "effectiveDate": "2025-01-01",
        },
        "additionalRemunerations": [
            {"nameCode": "Bonus", "amount": 10000.00, "currencyCode": "USD"},
        ],
    }


def test_extract_compensation_missing_assignment(adp_connection):
    worker = {"workAssignments": []}
    result = extract_compensation(worker)
    assert result == {
        "baseRemuneration": None,
        "additionalRemunerations": [],
    }


@pytest.mark.asyncio
async def test_fetch_worker_happy_path(adp_connection):
    c = _make_component(adp_connection)

    fake_response = httpx.Response(200, json=SAMPLE_WORKER_RESPONSE)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._fetch_worker(adp_connection, "G3ABC")

    assert result["associateOID"] == "G3ABC"
    assert result["person"]["legalName"]["givenName"] == "Jane"


@pytest.mark.asyncio
async def test_fetch_worker_401_retries_with_fresh_token(adp_connection):
    c = _make_component(adp_connection)

    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json=SAMPLE_WORKER_RESPONSE),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "new-token"

    with patch(
        "lfx.components.adp.adp_worker_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_worker_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        result = await c._fetch_worker(adp_connection, "G3ABC")

    assert result["associateOID"] == "G3ABC"
    assert mock_exec.call_count == 2
    second_headers = mock_exec.call_args_list[1].kwargs["headers"]
    assert second_headers["Authorization"] == "Bearer new-token"


@pytest.mark.asyncio
async def test_fetch_worker_http_error_returns_error_dict(adp_connection):
    c = _make_component(adp_connection)

    fake_response = httpx.Response(500, json={"error": "internal"})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._fetch_worker(adp_connection, "G3ABC")

    assert result["error"] == {"error": "internal"}
    assert result["status_code"] == 500


@pytest.mark.asyncio
async def test_fetch_worker_empty_workers_returns_not_found(adp_connection):
    c = _make_component(adp_connection)

    fake_response = httpx.Response(200, json={"workers": []})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._fetch_worker(adp_connection, "NONEXISTENT")

    assert result["error"] == "No worker found"
    assert result["status_code"] == 404


@pytest.mark.asyncio
async def test_build_tools_returns_five_tools(adp_connection):
    c = _make_component(adp_connection)
    tools = await c.build_tools()

    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "get_employee_name",
        "get_employee_addresses",
        "get_employee_contact_information",
        "get_employee_job",
        "get_employee_compensation",
    }
    for tool in tools:
        assert tool.description
        assert tool.args_schema is not None


@pytest.mark.asyncio
async def test_tool_invocation_calls_fetch_and_extracts(adp_connection):
    c = _make_component(adp_connection)
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]

    with patch.object(c, "_fetch_worker", new=AsyncMock(return_value=worker)):
        tools = await c.build_tools()
        name_tool = next(t for t in tools if t.name == "get_employee_name")
        result = await name_tool.ainvoke({"associate_oid": "G3ABC"})

    assert result["legalName"]["firstName"] == "Jane"


@pytest.mark.asyncio
async def test_tool_invocation_propagates_error_dict(adp_connection):
    c = _make_component(adp_connection)
    error_result = {"error": "internal", "status_code": 500}

    with patch.object(c, "_fetch_worker", new=AsyncMock(return_value=error_result)):
        tools = await c.build_tools()
        name_tool = next(t for t in tools if t.name == "get_employee_name")
        result = await name_tool.ainvoke({"associate_oid": "BAD"})

    assert result["error"] == "internal"
    assert result["status_code"] == 500
