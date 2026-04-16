"""Tests for ADPWorkerToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_tools import ADPWorkerToolsComponent

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
