"""Tests for ADPToolsComponent — multi-select dispatcher over tile builders."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from lfx.components.adp.adp_tools import TILE_BUILDERS, ADPToolsComponent


def _make_connection():
    conn = MagicMock()
    conn.access_token = "fake-token"  # noqa: S105
    conn.api_base_url = "https://api.adp.com"
    return conn


@pytest.mark.asyncio
async def test_no_selection_returns_empty_list():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = []

    tools = await component.build_tools()

    assert tools == []
    assert "0 ADP tools" in component.status or "No tile" in component.status


@pytest.mark.asyncio
async def test_single_tile_dispatch_worker():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()

    names = {t.name for t in tools}
    assert names == {
        "get_employee_name",
        "get_employee_addresses",
        "get_employee_contact_information",
        "get_employee_job",
        "get_employee_compensation",
        "get_employee_ids",
        "get_employee_dates",
        "get_employee_status",
        "get_employee_business_communication",
    }


@pytest.mark.asyncio
async def test_multiple_tile_dispatch_concatenates_no_duplicates():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker", "Worker Demographic"]

    tools = await component.build_tools()

    # Worker (9 tools) + Demographic (3 tools) = 12 distinct tools
    assert len({t.name for t in tools}) == len(tools)
    assert len(tools) >= 9  # at least the worker tools should be present
    # Demographic adds at least one tool
    assert len(tools) > 9


@pytest.mark.asyncio
async def test_unknown_label_skipped_silently():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker", "GhostTile"]

    tools = await component.build_tools()

    # Worker only; GhostTile silently dropped, no exception.
    assert len(tools) == 9


def test_tile_labels_in_multiselect_options():
    options = next(i for i in ADPToolsComponent.inputs if i.name == "tiles").options
    for label in TILE_BUILDERS:
        assert label in options
    assert len(options) == len(TILE_BUILDERS)


def test_registry_covers_all_29_tiles():
    """Task 8 expansion: full ADP tool surface, one entry per legacy tile component."""
    assert len(TILE_BUILDERS) == 29
    options = next(i for i in ADPToolsComponent.inputs if i.name == "tiles").options
    assert set(options) == set(TILE_BUILDERS.keys())
