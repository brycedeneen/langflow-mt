"""Tests for adp_worker_leaves_tools — build_worker_leaves_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_leaves_tools import (
    PATH_ABSENCE_REQUEST,
    PATH_ABSENCE_REQUEST_META,
    PATH_LEAVE_CANCEL,
    PATH_LEAVE_CANCEL_META,
    PATH_LEAVE_CHANGE,
    PATH_LEAVE_CHANGE_META,
    PATH_LEAVE_RETURN_REQUEST,
    PATH_LEAVE_RETURN_REQUEST_META,
    PATH_LIST_LEAVES,
    build_cancel_leave_event,
    build_change_leave_event,
    build_request_leave_absence_event,
    build_request_leave_return_event,
    build_worker_leaves_tools,
    extract_worker_leaves,
)

SAMPLE_LEAVES_RESPONSE = {
    "workerLeaves": [
        {
            "associateOID": "G3ABC",
            "workerID": {"idValue": "E12345"},
            "workAssignmentID": "WA-1",
            "leaves": [
                {
                    "itemID": "L-100",
                    "effectiveDateTime": "2026-05-01",
                    "leaveAbsence": {
                        "leaveTypeCode": {"codeValue": "FMLA"},
                        "leaveSubTypeCode": {"codeValue": "Parental"},
                        "startDateTime": "2026-05-01",
                        "expectedEndDateTime": "2026-07-01",
                        "leaveDuration": {"quantityValue": 60},
                        "paymentStatusCode": {"codeValue": "Paid"},
                        "statutoryFilingIndicator": {"indicatorValue": True},
                        "statutoryTypeCode": {"codeValue": "FMLA"},
                        "leaveStatus": {"statusCode": {"codeValue": "Active"}},
                    },
                    "leaveReturn": None,
                },
                {
                    "itemID": "L-101",
                    "effectiveDateTime": "2025-02-01",
                    "leaveAbsence": {
                        "leaveTypeCode": {"codeValue": "Personal"},
                        "startDateTime": "2025-02-01",
                        "expectedEndDateTime": "2025-02-15",
                    },
                    "leaveReturn": {
                        "returnDateTime": "2025-02-15",
                        "returnToWorkIndicator": {"indicatorValue": True},
                        "returnStatus": {"statusCode": {"codeValue": "Confirmed"}},
                    },
                },
            ],
        },
    ],
}


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ---------- extractor ----------


def test_extract_worker_leaves_flattens_rows():
    result = extract_worker_leaves(SAMPLE_LEAVES_RESPONSE["workerLeaves"])
    rows = result["leaves"]
    assert len(rows) == 2

    active = rows[0]
    assert active["associateOID"] == "G3ABC"
    assert active["workerID"] == "E12345"
    assert active["workAssignmentID"] == "WA-1"
    assert active["itemID"] == "L-100"
    assert active["leaveAbsence"] == {
        "leaveTypeCode": "FMLA",
        "leaveSubTypeCode": "Parental",
        "startDateTime": "2026-05-01",
        "expectedEndDateTime": "2026-07-01",
        "leaveDuration": 60,
        "paymentStatusCode": "Paid",
        "statutoryFilingIndicator": True,
        "statutoryTypeCode": "FMLA",
        "leaveStatus": "Active",
    }
    assert active["leaveReturn"] is None

    returned = rows[1]
    assert returned["itemID"] == "L-101"
    assert returned["leaveReturn"] == {
        "returnDateTime": "2025-02-15",
        "notificationReceivedDateTime": None,
        "returnToWorkIndicator": True,
        "returnStatus": "Confirmed",
    }


def test_extract_worker_leaves_empty():
    assert extract_worker_leaves([]) == {"leaves": []}
    assert extract_worker_leaves([{"associateOID": "G3ABC", "leaves": []}]) == {"leaves": []}


# ---------- envelope builders ----------


def test_build_request_leave_absence_event():
    body = build_request_leave_absence_event(
        associate_oid="G3ABC",
        start_date="2026-05-01",
        expected_end_date="2026-07-01",
        leave_type_code="FMLA",
        leave_sub_type_code="Parental",
        payment_status_code="Paid",
        statutory_filing_indicator=True,
        statutory_type_code="FMLA",
        leave_duration=60.0,
        comment="Bonding leave",
        work_assignment_id="WA-1",
        reason_code="New Child",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "workAssignmentID": "WA-1"}
    tf = event["data"]["transform"]
    assert tf["effectiveDateTime"] == "2026-05-01"
    assert tf["eventReasonCode"] == {"codeValue": "New Child"}
    abs_ = tf["workerLeave"]["leaveAbsence"]
    assert abs_["startDateTime"] == "2026-05-01"
    assert abs_["expectedEndDateTime"] == "2026-07-01"
    assert abs_["leaveTypeCode"] == {"codeValue": "FMLA"}
    assert abs_["leaveSubTypeCode"] == {"codeValue": "Parental"}
    assert abs_["paymentStatusCode"] == {"codeValue": "Paid"}
    assert abs_["statutoryFilingIndicator"] == {"indicatorValue": True}
    assert abs_["statutoryTypeCode"] == {"codeValue": "FMLA"}
    assert abs_["leaveDuration"] == {"quantityValue": 60.0}
    assert abs_["comment"] == {"noteText": "Bonding leave"}
    assert "leaveID" not in event["data"]["eventContext"]


def test_build_request_leave_absence_event_minimal():
    body = build_request_leave_absence_event(associate_oid="G3ABC", start_date="2026-05-01")
    tf = body["events"][0]["data"]["transform"]
    assert tf["effectiveDateTime"] == "2026-05-01"
    assert tf["workerLeave"]["leaveAbsence"] == {"startDateTime": "2026-05-01"}
    assert "eventReasonCode" not in tf


def test_build_change_leave_event_absence_and_return():
    body = build_change_leave_event(
        associate_oid="G3ABC",
        leave_id="L-100",
        effective_date="2026-06-01",
        expected_end_date="2026-08-01",
        return_date="2026-08-01",
        return_to_work_indicator=True,
        reason_code="Extension",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "leaveID": "L-100"}
    tf = event["data"]["transform"]
    assert tf["effectiveDateTime"] == "2026-06-01"
    assert tf["eventReasonCode"] == {"codeValue": "Extension"}
    wl = tf["workerLeave"]
    assert wl["leaveAbsence"] == {"expectedEndDateTime": "2026-08-01"}
    assert wl["leaveReturn"] == {
        "returnDateTime": "2026-08-01",
        "returnToWorkIndicator": {"indicatorValue": True},
    }


def test_build_change_leave_event_no_payload_fields():
    body = build_change_leave_event(
        associate_oid="G3ABC", leave_id="L-100", effective_date="2026-06-01",
    )
    tf = body["events"][0]["data"]["transform"]
    assert "workerLeave" not in tf


def test_build_cancel_leave_event():
    body = build_cancel_leave_event(
        associate_oid="G3ABC",
        leave_id="L-100",
        effective_date="2026-05-10",
        reason_code="Cancellation Requested",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "leaveID": "L-100"}
    tf = event["data"]["transform"]
    assert tf == {
        "effectiveDateTime": "2026-05-10",
        "eventReasonCode": {"codeValue": "Cancellation Requested"},
    }


def test_build_request_leave_return_event():
    body = build_request_leave_return_event(
        associate_oid="G3ABC",
        leave_id="L-100",
        return_date="2026-07-01",
        notification_received_date="2026-06-20",
        comment="Returning on schedule",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "leaveID": "L-100"}
    tf = event["data"]["transform"]
    assert tf["effectiveDateTime"] == "2026-07-01"
    lr = tf["leaveReturn"]
    assert lr["returnDateTime"] == "2026-07-01"
    assert lr["returnToWorkIndicator"] == {"indicatorValue": True}
    assert lr["notificationReceivedDateTime"] == "2026-06-20"
    assert lr["comment"] == {"noteText": "Returning on schedule"}
    assert "workerLeave" not in tf


# ---------- builder tests ----------


@pytest.mark.asyncio
async def test_build_tools_returns_six_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_leaves_tools(conn, cache)
    assert {t.name for t in tools} == {
        "list_worker_leaves",
        "get_worker_leave_event_meta",
        "request_worker_leave_absence",
        "change_worker_leave",
        "cancel_worker_leave",
        "request_worker_leave_return",
    }


@pytest.mark.asyncio
async def test_mutation_tools_route_to_correct_paths():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "R-1"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_leaves_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_leaves_tools.build_mtls_httpx_client", fake_client):
        await tools["request_worker_leave_absence"].ainvoke({
            "associate_oid": "G3ABC", "start_date": "2026-05-01",
        })
        await tools["change_worker_leave"].ainvoke({
            "associate_oid": "G3ABC", "leave_id": "L-100", "effective_date": "2026-06-01",
        })
        await tools["cancel_worker_leave"].ainvoke({
            "associate_oid": "G3ABC", "leave_id": "L-100", "effective_date": "2026-05-10",
        })
        await tools["request_worker_leave_return"].ainvoke({
            "associate_oid": "G3ABC", "leave_id": "L-100", "return_date": "2026-07-01",
        })

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_ABSENCE_REQUEST in u for u in posted_urls)
    assert any(PATH_LEAVE_CHANGE in u for u in posted_urls)
    assert any(PATH_LEAVE_CANCEL in u for u in posted_urls)
    assert any(PATH_LEAVE_RETURN_REQUEST in u for u in posted_urls)


@pytest.mark.asyncio
async def test_list_worker_leaves_forwards_filter_and_extracts():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_LEAVES_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_leaves_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_leaves_tools.build_mtls_httpx_client", fake_client):
        result = await tools["list_worker_leaves"].ainvoke({
            "associate_oid": "G3ABC",
            "filter": "leaveAbsence/leaveStatus/statusCode/codeValue eq 'Active'",
        })

    call = client.request.call_args
    called_url = call.kwargs.get("url") or call.args[1]
    assert called_url.endswith(PATH_LIST_LEAVES.format(aoid="G3ABC"))
    called_params = call.kwargs.get("params")
    assert called_params == {"$filter": "leaveAbsence/leaveStatus/statusCode/codeValue eq 'Active'"}
    assert len(result["leaves"]) == 2


@pytest.mark.asyncio
async def test_get_worker_leave_event_meta_routes_per_operation():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"meta": "ok"}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_leaves_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_leaves_tools.build_mtls_httpx_client", fake_client):
        for op in ("absence_request", "cancel", "change", "return_request"):
            await tools["get_worker_leave_event_meta"].ainvoke({"operation": op})

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_ABSENCE_REQUEST_META in u for u in posted_urls)
    assert any(PATH_LEAVE_CANCEL_META in u for u in posted_urls)
    assert any(PATH_LEAVE_CHANGE_META in u for u in posted_urls)
    assert any(PATH_LEAVE_RETURN_REQUEST_META in u for u in posted_urls)
