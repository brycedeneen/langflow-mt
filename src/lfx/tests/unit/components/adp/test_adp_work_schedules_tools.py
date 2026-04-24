"""Tests for ADPWorkSchedulesToolsComponent."""

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
    # schedule_entry supports only change
    for bad in [("schedule_entry", "add"), ("schedule_entry", "copy"), ("schedule_entry", "remove")]:
        with pytest.raises(ValueError, match="Unsupported"):
            event_path(*bad)


# ------------- builder -------------


def test_build_schedule_add():
    body = build_work_schedule_event(
        scope="schedule",
        action="add",
        associate_oid="G3ABC",
        fields={
            "scheduleStartDate": "2024-06-01",
            "scheduleEndDate": "2024-06-07",
        },
        effective_date="2024-06-01",
        event_reason_code="NEW_SCHEDULE",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC"}
    transform = event["data"]["transform"]
    assert transform["effectiveDateTime"] == "2024-06-01"
    assert transform["eventReasonCode"] == {"codeValue": "NEW_SCHEDULE"}
    assert transform["workSchedule"]["scheduleStartDate"] == "2024-06-01"


def test_build_schedule_day_change_pins_item():
    body = build_work_schedule_event(
        scope="schedule_day",
        action="change",
        associate_oid="G3ABC",
        item_id="DAY-1",
        fields={"scheduleDate": "2024-06-02"},
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {
        "associateOID": "G3ABC",
        "scheduleDay": {"itemID": "DAY-1"},
    }
    assert event["data"]["transform"]["scheduleDay"]["scheduleDate"] == "2024-06-02"


def test_build_schedule_remove_omits_transform_entity_key():
    body = build_work_schedule_event(
        scope="schedule",
        action="remove",
        associate_oid="G3ABC",
        item_id="SCH-1",
    )
    transform = body["events"][0]["data"]["transform"]
    assert "workSchedule" not in transform


def test_build_schedule_entry_change_uses_schedule_entry_key():
    body = build_work_schedule_event(
        scope="schedule_entry",
        action="change",
        associate_oid="G3ABC",
        item_id="ENT-1",
        fields={"positionID": "POS-42"},
    )
    assert "scheduleEntry" in body["events"][0]["data"]["transform"]
    assert body["events"][0]["data"]["eventContext"]["scheduleEntry"] == {"itemID": "ENT-1"}


def test_build_remove_without_identifier_raises():
    with pytest.raises(ValueError, match="requires item_id"):
        build_work_schedule_event(
            scope="schedule", action="remove", associate_oid="G3ABC",
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
                "item_id": "DAY-1",
                "fields": {"scheduleDate": "2024-06-08"},
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
