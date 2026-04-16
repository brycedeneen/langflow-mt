# ADP Worker Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Langflow component that outputs 5 StructuredTool instances for retrieving specific slices of employee data from the ADP `/hr/v2/workers/{associateOID}` API.

**Architecture:** A single component (`ADPWorkerToolsComponent`) takes an `ADPConnection` input and builds 5 tools at `build_tools()` time. Each tool accepts `associate_oid`, calls a shared `_fetch_worker()` method that handles mTLS + 401 retry, then extracts specific fields from the response.

**Tech Stack:** Python, httpx (mTLS), langchain_core.tools.StructuredTool, pydantic BaseModel, pytest + pytest-asyncio

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/lfx/src/lfx/components/adp/adp_worker_tools.py` (create) | Component class, 5 extraction functions, shared `_fetch_worker` |
| `src/lfx/src/lfx/components/adp/__init__.py` (modify) | Add `ADPWorkerToolsComponent` to exports |
| `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py` (create) | All unit tests |

---

### Task 1: Scaffold Component and `_fetch_worker` with Test

**Files:**
- Create: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`
- Create: `src/lfx/src/lfx/components/adp/adp_worker_tools.py`

- [ ] **Step 1: Write the failing test for `_fetch_worker` happy path**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py::test_fetch_worker_happy_path -v`
Expected: FAIL — module `adp_worker_tools` does not exist

- [ ] **Step 3: Write the component scaffold with `_fetch_worker`**

```python
"""ADPWorkerToolsComponent — focused employee data tools for Langflow Agents."""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import ADPConnection, build_mtls_httpx_client, fetch_token, validate_adp_url
from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output

HTTP_UNAUTHORIZED = 401


class WorkerToolInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID (unique employee identifier)")


class ADPWorkerToolsComponent(Component):
    display_name = "ADP Worker Tools"
    description = (
        "Exposes focused employee-data tools (name, address, contact, job, compensation) "
        "to a Langflow Agent. Each tool calls the ADP /hr/v2/workers API and returns "
        "only the relevant fields."
    )
    icon = "Users"
    name = "ADPWorkerTools"

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method="GET",
            url=url,
            headers=headers,
            timeout=timeout,
        )

    async def _fetch_worker(self, conn: ADPConnection, associate_oid: str) -> dict[str, Any]:
        url = f"{conn.api_base_url}/hr/v2/workers/{associate_oid}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(client, url=url, headers=headers, timeout=30.0)

            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(client, url=url, headers=headers, timeout=30.0)

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            return {"error": detail, "status_code": response.status_code}

        data = response.json()
        workers = data.get("workers", [])
        if not workers:
            return {"error": "No worker found", "status_code": 404}
        return workers[0]

    async def build_tools(self) -> list[Any]:
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py::test_fetch_worker_happy_path -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "feat(adp): scaffold ADPWorkerToolsComponent with _fetch_worker"
```

---

### Task 2: `_fetch_worker` 401 Retry and Error Handling Tests

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`

- [ ] **Step 1: Write failing tests for 401 retry and error cases**

Add to `test_adp_worker_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they pass** (implementation already handles these cases)

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -v`
Expected: PASS — all 4 tests

- [ ] **Step 3: Commit**

```bash
git add src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "test(adp): add _fetch_worker 401 retry and error handling tests"
```

---

### Task 3: Extraction Functions and Tests — Name, Addresses, Contact

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_tools.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`

- [ ] **Step 1: Write failing tests for the three extraction functions**

Add to `test_adp_worker_tools.py`:

```python
from lfx.components.adp.adp_worker_tools import extract_name, extract_addresses, extract_contact_information


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -k "extract_name or extract_address or extract_contact" -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement the three extraction functions**

Add to `adp_worker_tools.py` (module-level, before the class):

```python
def extract_name(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    legal = person.get("legalName")
    preferred = person.get("preferredName")
    return {
        "legalName": {
            "firstName": legal.get("givenName") if legal else None,
            "middleName": legal.get("middleName") if legal else None,
            "lastName": legal.get("familyName1") if legal else None,
        }
        if legal
        else None,
        "preferredName": {
            "firstName": preferred.get("givenName") if preferred else None,
            "lastName": preferred.get("familyName1") if preferred else None,
        }
        if preferred
        else None,
    }


def extract_addresses(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    addr = person.get("legalAddress")
    if not addr:
        return {"legalAddress": None}
    subdivision = addr.get("countrySubdivisionLevel1")
    return {
        "legalAddress": {
            "lineOne": addr.get("lineOne"),
            "lineTwo": addr.get("lineTwo"),
            "cityName": addr.get("cityName"),
            "countrySubdivisionLevel1": subdivision.get("codeValue") if isinstance(subdivision, dict) else subdivision,
            "postalCode": addr.get("postalCode"),
            "countryCode": addr.get("countryCode"),
        },
    }


def extract_contact_information(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    comm = person.get("communication", {})
    return {
        "emails": comm.get("emails", []),
        "landlines": comm.get("landlines", []),
        "mobiles": comm.get("mobiles", []),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -k "extract_name or extract_address or extract_contact" -v`
Expected: PASS — all 6 tests

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "feat(adp): add name, address, contact extraction functions"
```

---

### Task 4: Extraction Functions and Tests — Job, Compensation

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_tools.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`

- [ ] **Step 1: Write failing tests for job and compensation extraction**

Add to `test_adp_worker_tools.py`:

```python
from lfx.components.adp.adp_worker_tools import extract_job, extract_compensation


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -k "extract_job or extract_compensation" -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement the two extraction functions**

Add to `adp_worker_tools.py` (module-level, after the other extraction functions):

```python
def extract_job(worker: dict[str, Any]) -> dict[str, Any]:
    assignments = worker.get("workAssignments", [])
    status_obj = worker.get("workerStatus", {})
    worker_status = status_obj.get("statusCode", {}).get("codeValue") if status_obj else None

    if not assignments:
        return {
            "jobTitle": None,
            "departmentName": None,
            "locationName": None,
            "workerStatus": worker_status,
            "managementPosition": None,
            "reportsTo": None,
        }

    assignment = assignments[0]

    dept_name = None
    for unit in assignment.get("homeOrganizationalUnits", []):
        if unit.get("typeCode", {}).get("codeValue") == "Department":
            dept_name = unit.get("nameCode", {}).get("codeValue")
            break

    location = assignment.get("homeWorkLocation", {})
    location_name = location.get("nameCode", {}).get("codeValue") if location else None

    mgmt = assignment.get("managementPosition", {})
    mgmt_indicator = mgmt.get("indicatorCode", {}).get("codeValue") if mgmt else None
    mgmt_bool = mgmt_indicator.lower() == "true" if mgmt_indicator else None

    reports_list = assignment.get("reportsTo", [])
    reports_to = None
    if reports_list:
        r = reports_list[0]
        reports_to = {
            "associateOID": r.get("associateOID"),
            "workerName": r.get("reportsToWorkerName", {}).get("formattedName"),
        }

    return {
        "jobTitle": assignment.get("jobTitle"),
        "departmentName": dept_name,
        "locationName": location_name,
        "workerStatus": worker_status,
        "managementPosition": mgmt_bool,
        "reportsTo": reports_to,
    }


def extract_compensation(worker: dict[str, Any]) -> dict[str, Any]:
    assignments = worker.get("workAssignments", [])
    if not assignments:
        return {"baseRemuneration": None, "additionalRemunerations": []}

    assignment = assignments[0]
    base = assignment.get("baseRemuneration")

    base_result = None
    if base:
        pay_period = base.get("payPeriodRateAmount", {})
        annual = base.get("annualRateAmount", {})
        base_result = {
            "payPeriodAmount": pay_period.get("amountValue"),
            "annualAmount": annual.get("amountValue"),
            "currencyCode": annual.get("currencyCode") or pay_period.get("currencyCode"),
            "effectiveDate": base.get("effectiveDate"),
        }

    additional = []
    for rem in assignment.get("additionalRemunerations", []):
        rate = rem.get("rate", {}).get("rateAmount", {})
        additional.append({
            "nameCode": rem.get("nameCode", {}).get("codeValue"),
            "amount": rate.get("amountValue"),
            "currencyCode": rate.get("currencyCode"),
        })

    return {
        "baseRemuneration": base_result,
        "additionalRemunerations": additional,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -k "extract_job or extract_compensation" -v`
Expected: PASS — all 4 tests

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "feat(adp): add job and compensation extraction functions"
```

---

### Task 5: Wire Up `build_tools` and Integration Test

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_tools.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`

- [ ] **Step 1: Write failing test for `build_tools`**

Add to `test_adp_worker_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -k "build_tools or tool_invocation" -v`
Expected: FAIL — `build_tools` returns empty list

- [ ] **Step 3: Implement `build_tools`**

Replace the `build_tools` method in `ADPWorkerToolsComponent`:

```python
    async def build_tools(self) -> list[Any]:
        conn: ADPConnection = self.connection
        component = self

        async def _get_employee_name(associate_oid: str) -> dict[str, Any]:
            worker = await component._fetch_worker(conn, associate_oid)
            if "error" in worker:
                return worker
            return extract_name(worker)

        async def _get_employee_addresses(associate_oid: str) -> dict[str, Any]:
            worker = await component._fetch_worker(conn, associate_oid)
            if "error" in worker:
                return worker
            return extract_addresses(worker)

        async def _get_employee_contact_information(associate_oid: str) -> dict[str, Any]:
            worker = await component._fetch_worker(conn, associate_oid)
            if "error" in worker:
                return worker
            return extract_contact_information(worker)

        async def _get_employee_job(associate_oid: str) -> dict[str, Any]:
            worker = await component._fetch_worker(conn, associate_oid)
            if "error" in worker:
                return worker
            return extract_job(worker)

        async def _get_employee_compensation(associate_oid: str) -> dict[str, Any]:
            worker = await component._fetch_worker(conn, associate_oid)
            if "error" in worker:
                return worker
            return extract_compensation(worker)

        tools = [
            StructuredTool.from_function(
                name="get_employee_name",
                description="Get an employee's legal and preferred name by their ADP associate OID.",
                coroutine=_get_employee_name,
                args_schema=WorkerToolInput,
            ),
            StructuredTool.from_function(
                name="get_employee_addresses",
                description="Get an employee's legal address by their ADP associate OID.",
                coroutine=_get_employee_addresses,
                args_schema=WorkerToolInput,
            ),
            StructuredTool.from_function(
                name="get_employee_contact_information",
                description="Get an employee's contact information (emails, phone numbers) by their ADP associate OID.",
                coroutine=_get_employee_contact_information,
                args_schema=WorkerToolInput,
            ),
            StructuredTool.from_function(
                name="get_employee_job",
                description="Get an employee's job details (title, department, location, manager) by their ADP associate OID.",
                coroutine=_get_employee_job,
                args_schema=WorkerToolInput,
            ),
            StructuredTool.from_function(
                name="get_employee_compensation",
                description="Get an employee's compensation details (base pay, additional remunerations) by their ADP associate OID.",
                coroutine=_get_employee_compensation,
                args_schema=WorkerToolInput,
            ),
        ]

        return tools
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -v`
Expected: PASS — all tests

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "feat(adp): wire up build_tools with 5 StructuredTool instances"
```

---

### Task 6: Register Component and Run Full Test Suite

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/__init__.py`

- [ ] **Step 1: Update `__init__.py` to export the new component**

Replace the contents of `src/lfx/src/lfx/components/adp/__init__.py`:

```python
"""ADP connector bundle: Auth, API Request, MCP, Worker Tools."""

from .adp_api_request import ADPAPIRequestComponent
from .adp_auth import ADPAuthComponent
from .adp_mcp import ADPMCPComponent
from .adp_worker_tools import ADPWorkerToolsComponent

__all__ = [
    "ADPAPIRequestComponent",
    "ADPAuthComponent",
    "ADPMCPComponent",
    "ADPWorkerToolsComponent",
]
```

- [ ] **Step 2: Run the full ADP test suite**

Run: `cd /Users/brycedeneen/dev/langflow && python -m pytest src/lfx/tests/unit/components/adp/ -v`
Expected: PASS — all ADP tests including new ones

- [ ] **Step 3: Commit**

```bash
git add src/lfx/src/lfx/components/adp/__init__.py
git commit -m "feat(adp): register ADPWorkerToolsComponent in __init__.py"
```
