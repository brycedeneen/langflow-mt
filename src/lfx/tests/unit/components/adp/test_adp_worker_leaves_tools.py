"""Tests for ADPWorkerLeavesToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_leaves_tools import (
    ADPWorkerLeavesToolsComponent,
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


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPWorkerLeavesToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
    # Absence.request must NOT carry leaveID in eventContext
    assert "leaveID" not in event["data"]["eventContext"]


def test_build_request_leave_absence_event_minimal():
    body = build_request_leave_absence_event(associate_oid="G3ABC", start_date="2026-05-01")
    tf = body["events"][0]["data"]["transform"]
    # Effective date defaults to start_date
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
    # Only eventContext + effectiveDateTime — workerLeave should be absent when nothing to patch
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
    # leaveReturn lives directly under transform (not under workerLeave)
    assert "workerLeave" not in tf


# ---------- mutation gate / tool routing ----------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_reads_only(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"list_worker_leaves", "get_worker_leave_event_meta"}


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_all_six(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {
        "list_worker_leaves",
        "get_worker_leave_event_meta",
        "request_worker_leave_absence",
        "change_worker_leave",
        "cancel_worker_leave",
        "request_worker_leave_return",
    }


@pytest.mark.asyncio
async def test_mutation_tools_route_to_correct_paths(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "R-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
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

    paths = [call.kwargs["path"] for call in mock_post.call_args_list]
    assert paths == [
        PATH_ABSENCE_REQUEST,
        PATH_LEAVE_CHANGE,
        PATH_LEAVE_CANCEL,
        PATH_LEAVE_RETURN_REQUEST,
    ]


# ---------- read-tool routing (list + meta) ----------


@pytest.mark.asyncio
async def test_list_worker_leaves_forwards_filter_and_extracts(adp_connection):
    c = _make_component(adp_connection)
    fake_response = httpx.Response(200, json=SAMPLE_LEAVES_RESPONSE)
    mock_client = MagicMock()
    captured: dict = {}

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):
        yield mock_client

    async def fake_execute(_client, *, method, url, headers, params, json_body, timeout):  # noqa: ARG001
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        return fake_response

    with patch(
        "lfx.components.adp.adp_worker_leaves_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=fake_execute):
        tools = {t.name: t for t in await c.build_tools()}
        result = await tools["list_worker_leaves"].ainvoke({
            "associate_oid": "G3ABC",
            "filter": "leaveAbsence/leaveStatus/statusCode/codeValue eq 'Active'",
        })

    assert captured["method"] == "GET"
    assert captured["url"].endswith(PATH_LIST_LEAVES.format(aoid="G3ABC"))
    assert captured["params"] == {
        "$filter": "leaveAbsence/leaveStatus/statusCode/codeValue eq 'Active'",
    }
    assert len(result["leaves"]) == 2


@pytest.mark.asyncio
async def test_get_worker_leave_event_meta_routes_per_operation(adp_connection):
    c = _make_component(adp_connection)
    captured_paths: list[str] = []

    async def fake_call(_conn, *, method, path, params=None, body=None):  # noqa: ARG001
        captured_paths.append(path)
        return {"meta": path}

    with patch.object(c, "_call", new=fake_call):
        tools = {t.name: t for t in await c.build_tools()}
        meta_tool = tools["get_worker_leave_event_meta"]
        for op in ("absence_request", "cancel", "change", "return_request"):
            await meta_tool.ainvoke({"operation": op})

    assert captured_paths == [
        PATH_ABSENCE_REQUEST_META,
        PATH_LEAVE_CANCEL_META,
        PATH_LEAVE_CHANGE_META,
        PATH_LEAVE_RETURN_REQUEST_META,
    ]
