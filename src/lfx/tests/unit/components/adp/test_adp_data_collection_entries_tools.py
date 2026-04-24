"""Tests for ADPDataCollectionEntriesToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_data_collection_entries_tools import (
    ADPDataCollectionEntriesToolsComponent,
    PATH_PROCESS,
    PATH_RESULT,
)


def _make(connection, *, enable_mutations=False):
    return ADPDataCollectionEntriesToolsComponent(connection=connection, enable_mutations=enable_mutations)


@pytest.mark.asyncio
async def test_get_result_routes_with_event_id(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "get_data_collection_event_result").ainvoke({"event_id": "EV-1"})
    assert mock_call.call_args.kwargs["path"] == PATH_RESULT.format(event_id="EV-1")


@pytest.mark.asyncio
async def test_process_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"get_data_collection_event_result"}

    c = _make(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert "process_data_collection_entries" in {t.name for t in tools}


@pytest.mark.asyncio
async def test_process_posts_event_body(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "process_data_collection_entries").ainvoke(
            {"event_body": {"events": [{"data": {}}]}},
        )
    assert mock_call.call_args.kwargs["path"] == PATH_PROCESS
    assert mock_call.call_args.kwargs["method"] == "POST"
