"""Tests for ADPWorkSchedulesToolsComponent.

Shapes asserted below are grounded in the HAR-sampled ADP request payloads
under docs/adp-api-specs/time/work-schedules/v1/har-samples.json.
"""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_work_schedules_tools import (
    ADPWorkSchedulesToolsComponent,
    PATH_LIST_WORKER,
    build_work_schedule_event,
    event_path,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkSchedulesToolsComponent(connection=connection, enable_mutations=enable_mutations)


# ------------- event_path -------------


def test_event_path_supported_combos():
    assert event_path("schedule", "add") == "/events/time/v1/work-schedule.add"
    assert event_path("schedule", "copy") == "/events/time/v1/work-schedule.copy"
    assert event_path("schedule_day", "remove") == "/events/time/v1/work-schedule-day.remove"
    assert event_path("schedule_entry", "change") == "/events/time/v1/work-schedule-entry.change"


def test_event_path_unsupported_combos():
    for bad in [("schedule_entry", "add"), ("schedule_entry", "copy"), ("schedule_entry", "remove")]:
        with pytest.raises(ValueError, match="Unsupported"):
            event_path(*bad)


# ------------- builder: add -------------


def test_build_schedule_add_matches_har_shape():
    # HAR sample: Specifies_the_API_used_to_add_a_work_schedule_Provide_Example_workSchedule.add_request_3871.json
    # ctx: {associateOID}; transform: {workSchedule: {schedulePeriod, scheduleDays}}
    body = build_work_schedule_event(
        scope="schedule",
        action="add",
        associate_oid="G3ABC",
        fields={
            "schedulePeriod": {"startDate": "2024-06-01", "endDate": "2024-06-07"},
            "scheduleDays": [],
        },
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC"}
    assert event["data"]["transform"]["workSchedule"]["schedulePeriod"]["startDate"] == "2024-06-01"


def test_build_schedule_day_add_with_schedule_period_pin():
    # HAR sample: workScheduleDay.add request — ctx has associateOID + schedulePeriod.
    body = build_work_schedule_event(
        scope="schedule_day",
        action="add",
        associate_oid="G3ABC",
        context_pin_fields={
            "schedulePeriod": {"startDate": "2024-06-01", "endDate": "2024-06-07"},
        },
        fields={
            "daySequenceNumber": 1,
            "scheduleDayDate": "2024-06-02",
            "scheduleEntries": [],
        },
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx == {
        "associateOID": "G3ABC",
        "schedulePeriod": {"startDate": "2024-06-01", "endDate": "2024-06-07"},
    }
    day = body["events"][0]["data"]["transform"]["scheduleDay"]
    assert day["daySequenceNumber"] == 1
    assert day["scheduleDayDate"] == "2024-06-02"


# ------------- builder: change -------------


def test_build_schedule_entry_change_matches_har_pins():
    # HAR sample ctx keys: associateOID, schedulePeriod, scheduleDayDate, scheduleEntryID.
    # transform: eventStatusCode + scheduleEntry.
    body = build_work_schedule_event(
        scope="schedule_entry",
        action="change",
        associate_oid="G3ABC",
        context_pin_fields={
            "schedulePeriod": {"startDate": "2024-06-01", "endDate": "2024-06-07"},
            "scheduleDayDate": "2024-06-03",
            "scheduleEntryID": "ENT-1",
        },
        additional_transform_fields={"eventStatusCode": {"codeValue": "Complete"}},
        fields={
            "categoryTypeCode": {"codeValue": "Work"},
            "shiftTypeCode": {"codeValue": "Regular"},
            "dateTimePeriod": {"startDateTime": "2024-06-03T09:00:00-04:00"},
        },
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx["associateOID"] == "G3ABC"
    assert ctx["scheduleEntryID"] == "ENT-1"
    assert ctx["scheduleDayDate"] == "2024-06-03"
    assert "schedulePeriod" in ctx
    transform = body["events"][0]["data"]["transform"]
    assert transform["eventStatusCode"] == {"codeValue": "Complete"}
    assert transform["scheduleEntry"]["categoryTypeCode"] == {"codeValue": "Work"}


# ------------- builder: copy -------------


def test_build_schedule_copy_uses_transform_copy_fields():
    # HAR sample: workSchedule.copy — transform has workerCopyTo, startDateCopyTo, workSchedule.
    body = build_work_schedule_event(
        scope="schedule",
        action="copy",
        associate_oid="G3ABC",
        additional_transform_fields={
            "workerCopyTo": {"associateOID": "G3XYZ"},
            "startDateCopyTo": "2024-06-08",
        },
        fields={"scheduleDays": []},
    )
    transform = body["events"][0]["data"]["transform"]
    assert transform["workerCopyTo"] == {"associateOID": "G3XYZ"}
    assert transform["startDateCopyTo"] == "2024-06-08"
    assert transform["workSchedule"] == {"scheduleDays": []}


def test_build_schedule_day_copy_has_start_date_copy_to():
    body = build_work_schedule_event(
        scope="schedule_day",
        action="copy",
        associate_oid="G3ABC",
        additional_transform_fields={"startDateCopyTo": "2024-06-10"},
        fields={
            "scheduleDayDate": "2024-06-02",
            "scheduleEntries": [],
        },
    )
    transform = body["events"][0]["data"]["transform"]
    assert transform["startDateCopyTo"] == "2024-06-10"
    assert transform["scheduleDay"]["scheduleDayDate"] == "2024-06-02"


# ------------- builder: remove -------------


def test_build_schedule_remove_uses_schedule_id_pin():
    # HAR sample: workSchedule.remove ctx = {associateOID, scheduleID}. transform empty.
    body = build_work_schedule_event(
        scope="schedule",
        action="remove",
        associate_oid="G3ABC",
        context_pin_fields={"scheduleID": "SCH-1"},
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx == {"associateOID": "G3ABC", "scheduleID": "SCH-1"}
    transform = body["events"][0]["data"]["transform"]
    # No workSchedule entity key on remove.
    assert "workSchedule" not in transform


def test_build_schedule_day_remove_uses_day_date_pin():
    # HAR sample: workScheduleDay.remove ctx = {associateOID, scheduleDayDate}.
    body = build_work_schedule_event(
        scope="schedule_day",
        action="remove",
        associate_oid="G3ABC",
        context_pin_fields={"scheduleDayDate": "2024-06-02"},
        additional_transform_fields={"eventStatusCode": {"codeValue": "Complete"}},
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx == {"associateOID": "G3ABC", "scheduleDayDate": "2024-06-02"}
    assert body["events"][0]["data"]["transform"]["eventStatusCode"] == {"codeValue": "Complete"}


def test_build_remove_without_pin_raises():
    with pytest.raises(ValueError, match="requires context_pin_fields"):
        build_work_schedule_event(
            scope="schedule", action="remove", associate_oid="G3ABC",
        )


def test_build_change_without_pin_raises():
    with pytest.raises(ValueError, match="requires context_pin_fields"):
        build_work_schedule_event(
            scope="schedule_entry", action="change", associate_oid="G3ABC",
            fields={"categoryTypeCode": {"codeValue": "Work"}},
        )


def test_build_unsupported_combo_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        build_work_schedule_event(
            scope="schedule_entry", action="add", associate_oid="G3ABC", fields={},
        )


# ------------- tool wiring -------------


@pytest.mark.asyncio
async def test_read_tool_path_and_params(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await tools[0].ainvoke({"associate_oid": "G3ABC", "$top": 10})
    assert mock_call.call_args.kwargs["path"] == PATH_LIST_WORKER.format(aoid="G3ABC")
    assert mock_call.call_args.kwargs["params"] == {"$top": 10}


@pytest.mark.asyncio
async def test_build_tools_disabled_only_read(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert [t.name for t in tools] == ["get_worker_work_schedules"]


@pytest.mark.asyncio
async def test_build_tools_enabled_has_manage(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"get_worker_work_schedules", "manage_work_schedule"}


@pytest.mark.asyncio
async def test_manage_routes_schedule_day_copy(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={})
    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "manage_work_schedule").ainvoke(
            {
                "scope": "schedule_day",
                "action": "copy",
                "associate_oid": "G3ABC",
                "additional_transform_fields": {"startDateCopyTo": "2024-06-08"},
                "fields": {"scheduleDayDate": "2024-06-01"},
            },
        )
    assert mock_post.call_args.kwargs["path"] == "/events/time/v1/work-schedule-day.copy"


@pytest.mark.asyncio
async def test_manage_unsupported_combo_returns_422(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock()
    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        result = await next(t for t in tools if t.name == "manage_work_schedule").ainvoke(
            {"scope": "schedule_entry", "action": "add", "associate_oid": "G3ABC"},
        )
    assert result["status_code"] == 422
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_manage_missing_pin_returns_422(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock()
    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        result = await next(t for t in tools if t.name == "manage_work_schedule").ainvoke(
            {"scope": "schedule", "action": "remove", "associate_oid": "G3ABC"},
        )
    assert result["status_code"] == 422
    assert "context_pin_fields" in result["error"]
    mock_post.assert_not_called()
