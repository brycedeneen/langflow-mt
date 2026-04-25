"""CombineRecords — append, union+dedupe, or merge-by-key over Data/DataFrame."""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd

from lfx.custom import Component
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema import Data, DataFrame


def _hashable(value: Any) -> Any:
    """Return a hashable form of `value` for use in dedupe signatures."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    return str(value)


class CombineRecordsComponent(Component):
    display_name = "Combine Records"
    description = (
        "Combine two record streams (Data or DataFrame). "
        "Modes: Append (concat), Union (concat + dedupe), Merge by key (relational join)."
    )
    icon = "merge"
    name = "CombineRecords"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(version=1, changes="Initial release."),
    ]
    metadata: ClassVar[dict[str, Any]] = {
        "keywords": [
            "combine", "merge", "join", "union",
            "concatenate", "append", "dedupe",
        ],
    }

    _MODE_FIELDS: ClassVar[dict[str, list[str]]] = {
        "Append": [],
        "Union (dedupe)": ["dedupe_keys"],
        "Merge by key": ["join_keys", "join_type"],
    }
    _ALL_DYNAMIC_FIELDS: ClassVar[list[str]] = ["dedupe_keys", "join_keys", "join_type"]

    inputs = [
        DropdownInput(
            name="mode",
            display_name="Mode",
            info="How to combine left and right.",
            options=["Append", "Union (dedupe)", "Merge by key"],
            value="Append",
            real_time_refresh=True,
        ),
        HandleInput(
            name="left",
            display_name="Left",
            info="First record stream.",
            input_types=["Data", "DataFrame"],
            required=True,
        ),
        HandleInput(
            name="right",
            display_name="Right",
            info="Second record stream.",
            input_types=["Data", "DataFrame"],
            required=True,
        ),
        StrInput(
            name="dedupe_keys",
            display_name="Dedupe Keys",
            info=(
                "Comma-separated field names to dedupe by (first occurrence wins). "
                "Leave blank to dedupe by full-record equality."
            ),
            value="",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="join_keys",
            display_name="Join Keys",
            info="Comma-separated field name(s) to join on. Required for Merge by key.",
            value="",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="join_type",
            display_name="Join Type",
            info="Relational join type.",
            options=["inner", "left", "right", "outer"],
            value="inner",
            dynamic=True,
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="Combined", name="combined", method="build_combined"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "mode":
            visible = set(self._MODE_FIELDS.get(field_value, []))
            for field in self._ALL_DYNAMIC_FIELDS:
                if field in build_config:
                    build_config[field]["show"] = field in visible
        return build_config

    async def build_combined(self) -> Data | list[Data] | DataFrame:
        msg = "CombineRecordsComponent.build_combined is not implemented yet."
        raise NotImplementedError(msg)
