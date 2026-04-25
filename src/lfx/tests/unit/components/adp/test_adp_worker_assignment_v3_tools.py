"""Tests for adp_worker_assignment_v3_tools — build_worker_assignment_v3_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_assignment_v3_tools import (
    WORK_ASSIGNMENT_PATH_TEMPLATE,
    build_add_work_assignment_body,
    build_worker_assignment_v3_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_add_work_assignment_body_minimum():
    body = build_add_work_assignment_body(hire_date="2026-05-01")
    assert body == {"workAssignment": {"hireDate": "2026-05-01"}}


def test_build_add_work_assignment_body_full():
    body = build_add_work_assignment_body(
        hire_date="2026-05-01",
        primary_indicator=True,
        job_code="SWE-2",
        job_title="Senior Engineer",
        worker_type_code="Regular",
        position_id="P-123",
        position_title="Senior Software Engineer",
        reports_to_associate_oid="G3MGR",
        department_name="Engineering",
        work_location_name="Remote",
        annual_base_pay=150000.0,
    )
    wa = body["workAssignment"]
    assert wa["hireDate"] == "2026-05-01"
    assert wa["primaryIndicator"] is True
    assert wa["job"] == {"jobCode": {"code": "SWE-2"}, "jobTitle": "Senior Engineer"}
    assert wa["workerTypeCode"] == {"code": "Regular"}
    assert wa["positionID"] == "P-123"
    assert wa["positionTitle"] == "Senior Software Engineer"
    assert wa["reportsTo"] == [{"associateOID": "G3MGR"}]
    assert wa["organizationalUnits"][0]["unitName"] == "Engineering"
    assert wa["organizationalUnits"][0]["unitTypeCode"] == {"code": "Department"}
    assert wa["workLocations"][0]["locationName"] == "Remote"
    assert wa["directFinancialCompensation"]["compensationRates"][0]["rate"] == 150000.0


def test_build_add_work_assignment_body_additional_fields_deep_merge():
    body = build_add_work_assignment_body(
        hire_date="2026-05-01",
        job_title="Engineer",
        additional_fields={"job": {"jobFamilies": [{"jobFamilyCode": {"code": "SWE"}}]}},
    )
    wa = body["workAssignment"]
    assert wa["job"]["jobTitle"] == "Engineer"
    assert wa["job"]["jobFamilies"][0]["jobFamilyCode"] == {"code": "SWE"}


def test_work_assignment_path_template():
    assert WORK_ASSIGNMENT_PATH_TEMPLATE.format(aoid="G3ABC") == "/hr/v3/workers/G3ABC/work-assignments"


@pytest.mark.asyncio
async def test_build_tools_returns_one_tool():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_assignment_v3_tools(conn, cache)
    assert len(tools) == 1
    assert tools[0].name == "add_employee_work_assignment"


@pytest.mark.asyncio
async def test_tool_invocation_posts_to_correct_url():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_assignment_v3_tools(conn, cache)
    tool = tools[0]

    response = MagicMock(spec=httpx.Response)
    response.status_code = 201
    response.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_assignment_v3_tools.build_mtls_httpx_client", fake_client):
        result = await tool.ainvoke({"associate_oid": "G3ABC", "hire_date": "2026-05-01"})

    assert result == {"ok": True}
    call = client.request.call_args
    assert "G3ABC/work-assignments" in (call.kwargs.get("url") or call.args[1])


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_assignment_v3_tools(conn, cache)
    tool = tools[0]

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"message": "unauthorized"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 201
    success.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_assignment_v3_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_assignment_v3_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke({"associate_oid": "G3ABC", "hire_date": "2026-05-01"})

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
