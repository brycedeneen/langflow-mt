"""Tests for ADPTimeCardsToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_time_cards_tools import (
    ADPTimeCardsToolsComponent,
    PATH_MODIFY,
    build_time_entries_modify_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPTimeCardsToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_event_with_work_assignment():
    body = build_time_entries_modify_event(
        associate_oid="G3ABC",
        work_assignment_id="WA-1",
        time_entries=[
            {"entryTypeCode": {"codeValue": "hoursEntry"}, "entryDate": "2024-01-02", "timeDuration": "PT8H"},
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC", "workAssignmentID": "WA-1"}
    assert event["data"]["transform"]["timeEntries"][0]["timeDuration"] == "PT8H"


def test_build_event_without_work_assignment():
    body = build_time_entries_modify_event(associate_oid="G3ABC", time_entries=[])
    assert body["events"][0]["data"]["eventContext"] == {"associateOID": "G3ABC"}
    assert body["events"][0]["data"]["transform"]["timeEntries"] == []


@pytest.mark.asyncio
async def test_tools_disabled_empty(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_tool_routes_correct_path(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        await tools[0].ainvoke(
            {"associate_oid": "G3ABC", "work_assignment_id": "WA-1", "time_entries": []},
        )

    assert mock_post.call_args.kwargs["path"] == PATH_MODIFY


def test_path_constant():
    assert PATH_MODIFY == "/events/time/v2/time-entries.modify"
