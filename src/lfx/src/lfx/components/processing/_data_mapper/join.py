"""Composite-key lookup-index builder for DataMapperComponent.

First-match-wins semantics: building an index from a list of rows preserves
only the earliest row per composite key; subsequent duplicates are counted
and returned so the engine can emit one aggregate warning per lookup.
"""

from __future__ import annotations

from typing import Any

from lfx.components.processing._data_mapper.config_schema import JoinDef


def build_index(
    rows: list[dict[str, Any]],
    join: JoinDef,
) -> tuple[dict[tuple, dict[str, Any]], int]:
    """Build a lookup index keyed by the tuple of lookup-side join fields.

    Returns:
        (index, collision_count) where collision_count is the number of rows
        that were shadowed by an earlier row with the same key.
    """
    index: dict[tuple, dict[str, Any]] = {}
    collisions = 0
    for row in rows:
        key = tuple(row.get(k.lookup_field) for k in join.on)
        if key in index:
            collisions += 1
            continue  # first-match-wins
        index[key] = row
    return index, collisions


def lookup(
    index: dict[tuple, dict[str, Any]],
    driver_row: dict[str, Any],
    join: JoinDef,
) -> dict[str, Any] | None:
    """Look up the row matching this driver_row's join keys, or None."""
    key = tuple(driver_row.get(k.driver_field) for k in join.on)
    return index.get(key)
