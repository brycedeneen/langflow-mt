"""Tests for adp_worker_tools — extract_* helpers and build_worker_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_tools import (
    build_worker_tools,
    extract_addresses,
    extract_business_communication,
    extract_compensation,
    extract_contact_information,
    extract_dates,
    extract_ids,
    extract_job,
    extract_name,
    extract_status,
)

SAMPLE_WORKER_RESPONSE = {
    "workers": [
        {
            "associateOID": "G3ABC",
            "workerID": {"idValue": "E12345", "schemeCode": {"codeValue": "Employee ID"}},
            "alternateIDs": [
                {"idValue": "X-999", "schemeCode": {"codeValue": "Badge"}},
            ],
            "workerDates": {
                "firstHireDate": "2019-05-01",
                "originalHireDate": "2019-05-01",
                "rehireDate": None,
                "terminationDate": None,
                "retirementDate": None,
            },
            "businessCommunication": {
                "emails": [{"emailUri": "jane.work@example.com", "nameCode": {"codeValue": "Work"}}],
                "landlines": [{"formattedNumber": "555-2000", "nameCode": {"codeValue": "Work"}}],
                "mobiles": [],
            },
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
            "workerStatus": {
                "statusCode": {"codeValue": "Active"},
                "reasonCode": {"codeValue": "New Hire"},
                "effectiveDate": "2019-05-01",
            },
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


def _make_connection(*, access_token="T1", api_base_url="https://api.adp.com"):
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ---------------------------------------------------------------------------
# extract_* pure function tests
# ---------------------------------------------------------------------------


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


def test_extract_ids(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_ids(worker)
    assert result == {
        "associateOID": "G3ABC",
        "workerID": {"idValue": "E12345", "schemeCode": "Employee ID"},
        "alternateIDs": [{"idValue": "X-999", "schemeCode": "Badge"}],
    }


def test_extract_ids_missing(adp_connection):
    worker = {"associateOID": "G3ABC"}
    result = extract_ids(worker)
    assert result == {
        "associateOID": "G3ABC",
        "workerID": None,
        "alternateIDs": [],
    }


def test_extract_dates(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_dates(worker)
    assert result["firstHireDate"] == "2019-05-01"
    assert result["originalHireDate"] == "2019-05-01"
    assert result["terminationDate"] is None
    # All expected lifecycle fields present, even if None
    assert "rehireDate" in result
    assert "retirementDate" in result
    assert "leaveOfAbsenceReturnDate" in result


def test_extract_dates_missing(adp_connection):
    worker = {}
    result = extract_dates(worker)
    assert result["firstHireDate"] is None
    assert result["terminationDate"] is None


def test_extract_status(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_status(worker)
    assert result == {
        "statusCode": "Active",
        "reasonCode": "New Hire",
        "effectiveDate": "2019-05-01",
    }


def test_extract_status_missing(adp_connection):
    worker = {}
    result = extract_status(worker)
    assert result == {"statusCode": None, "reasonCode": None, "effectiveDate": None}


def test_extract_business_communication(adp_connection):
    worker = SAMPLE_WORKER_RESPONSE["workers"][0]
    result = extract_business_communication(worker)
    assert result == {
        "emails": [{"emailUri": "jane.work@example.com", "nameCode": {"codeValue": "Work"}}],
        "landlines": [{"formattedNumber": "555-2000", "nameCode": {"codeValue": "Work"}}],
        "mobiles": [],
    }


def test_extract_business_communication_missing(adp_connection):
    worker = {}
    result = extract_business_communication(worker)
    assert result == {"emails": [], "landlines": [], "mobiles": []}


# ---------------------------------------------------------------------------
# build_worker_tools builder tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_worker_tools_returns_nine_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)

    names = [t.name for t in tools]
    assert names == [
        "get_employee_name",
        "get_employee_addresses",
        "get_employee_contact_information",
        "get_employee_job",
        "get_employee_compensation",
        "get_employee_ids",
        "get_employee_dates",
        "get_employee_status",
        "get_employee_business_communication",
    ]


@pytest.mark.asyncio
async def test_get_employee_name_returns_expected_shape():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        result = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert result == {
        "legalName": {"firstName": "Jane", "middleName": "Marie", "lastName": "Doe"},
        "preferredName": {"firstName": "Janie", "lastName": "Doe"},
    }


@pytest.mark.asyncio
async def test_two_tools_same_oid_share_cache():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")
    get_compensation = next(t for t in tools if t.name == "get_employee_compensation")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await get_name.ainvoke({"associate_oid": "G3ABC"})
        await get_compensation.ainvoke({"associate_oid": "G3ABC"})

    # Cache: 1 GET to /hr/v2/workers/G3ABC, served from cache on second tool call.
    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"message": "unauthorized"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_tools.fetch_token", AsyncMock()) as fetch_token_mock:
        result = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert "legalName" in result
    fetch_token_mock.assert_awaited_once()
    assert client.request.await_count == 2


@pytest.mark.asyncio
async def test_error_response_not_cached():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    error = MagicMock(spec=httpx.Response)
    error.status_code = 500
    error.json.return_value = {"message": "boom"}
    error.text = ""

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [error, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        first = await get_name.ainvoke({"associate_oid": "G3ABC"})
        second = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert first.get("status_code") == 500
    assert "legalName" in second  # not served from cache; refetched
    assert client.request.await_count == 2
