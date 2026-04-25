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
        from lfx.components.processing._record_ops import (
            InputShape,
            detect_shape,
            from_record_list,
            to_record_list,
        )

        left_shape = detect_shape(self.left)
        right_shape = detect_shape(self.right)
        out_shape = self._output_shape(left_shape, right_shape)

        left_records = to_record_list(self.left)
        right_records = to_record_list(self.right)

        if self.mode == "Append":
            combined = left_records + right_records
        elif self.mode == "Union (dedupe)":
            combined = self._union_dedupe(left_records, right_records)
        elif self.mode == "Merge by key":
            combined = self._merge_by_key(left_records, right_records)
        else:
            msg = f"Unknown mode: {self.mode}"
            raise ValueError(msg)

        return from_record_list(combined, out_shape)

    def _output_shape(self, left_shape, right_shape):
        from lfx.components.processing._record_ops import InputShape

        # Mixed input → DataFrame.
        if left_shape != right_shape and InputShape.DATAFRAME in (left_shape, right_shape):
            return InputShape.DATAFRAME
        if left_shape == InputShape.DATAFRAME:
            return InputShape.DATAFRAME
        # Both Data-flavored: prefer DATA_LIST since combination is N+M ≥ 1.
        return InputShape.DATA_LIST

    def _union_dedupe(self, left: list[dict], right: list[dict]) -> list[dict]:
        keys_str = (self.dedupe_keys or "").strip()
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        seen: set = set()
        out: list[dict] = []

        def signature(record: dict) -> tuple:
            if keys:
                return tuple(record.get(k) for k in keys)
            # Full-record equality: tuple of sorted items, with values converted
            # to a hashable representation (str fallback for nested structures).
            return tuple(sorted((k, _hashable(v)) for k, v in record.items()))

        for record in left + right:
            sig = signature(record)
            if sig not in seen:
                seen.add(sig)
                out.append(record)
        return out

    def _merge_by_key(self, left: list[dict], right: list[dict]) -> list[dict]:
        msg = "Merge by key not implemented yet."
        raise NotImplementedError(msg)
