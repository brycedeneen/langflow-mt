"""FilterRecords — multi-condition record filter for Data and DataFrame."""

from __future__ import annotations

from typing import Any, ClassVar

from lfx.custom import Component
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.io import DropdownInput, HandleInput, Output, TableInput
from lfx.schema import Data, DataFrame


class FilterRecordsComponent(Component):
    display_name = "Filter Records"
    description = (
        "Filter a list of records (Data or DataFrame) by one or more conditions. "
        "Outputs both matched and unmatched records."
    )
    icon = "filter"
    name = "FilterRecords"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(version=1, changes="Initial release."),
    ]
    metadata: ClassVar[dict[str, Any]] = {
        "keywords": [
            "filter", "records", "where", "conditions",
            "exclude", "include", "match", "predicate",
        ],
    }

    inputs = [
        HandleInput(
            name="records",
            display_name="Records",
            info="A Data, list of Data, or DataFrame to filter.",
            input_types=["Data", "DataFrame"],
            is_list=True,
            required=True,
        ),
        TableInput(
            name="conditions",
            display_name="Conditions",
            info=(
                "Each row is one condition. 'Field' uses dot notation "
                "(e.g. 'address.city' or 'items[0].sku'). "
                "All rows are joined by the chosen Combinator."
            ),
            table_schema=[
                {"name": "field", "display_name": "Field", "type": "str"},
                {
                    "name": "operator",
                    "display_name": "Operator",
                    "type": "str",
                    "options": [
                        "equals", "not equals",
                        "contains", "does not contain",
                        "starts with", "ends with",
                        "matches regex",
                        "greater than", "less than",
                        "between",
                        "in", "not in",
                        "is empty", "is not empty",
                    ],
                    "value": "equals",
                },
                {"name": "value", "display_name": "Value", "type": "str"},
            ],
            value=[],
        ),
        DropdownInput(
            name="combinator",
            display_name="Combinator",
            info="How to combine multiple conditions.",
            options=["AND", "OR"],
            value="AND",
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            info=(
                "Keep matching: records satisfying the conditions go to 'matched'. "
                "Exclude matching: records satisfying the conditions go to 'unmatched'."
            ),
            options=["Keep matching", "Exclude matching"],
            value="Keep matching",
        ),
    ]

    outputs = [
        Output(display_name="Matched", name="matched", method="build_matched"),
        Output(display_name="Unmatched", name="unmatched", method="build_unmatched"),
    ]

    async def build_matched(self) -> Data | list[Data] | DataFrame:
        matched, _ = self._partition()
        return matched

    async def build_unmatched(self) -> Data | list[Data] | DataFrame:
        _, unmatched = self._partition()
        return unmatched

    def _normalize_records(self) -> tuple[list[dict], Any]:
        """Resolve self.records into a (record_dicts, output_shape) tuple.

        Rule: with `is_list=True`, the framework always wraps inputs into a
        list. We treat `self.records` as that list and merge all items into
        one record stream. Output shape follows a single predictable rule:

        - All items are DataFrame → DataFrame out (DATAFRAME)
        - Otherwise → list[Data] out (DATA_LIST)
        - Empty / no items → empty DATA_LIST

        Bare inputs (Data or DataFrame, used in tests that bypass framework
        wrapping) are silently wrapped in a list so the rule still applies.
        """
        from lfx.components.processing._record_ops import (
            InputShape,
            detect_shape,
            to_record_list,
        )
        from lfx.schema import Data, DataFrame

        raw = self.records

        # Defensive: tests sometimes assign bare Data/DataFrame; wrap.
        if isinstance(raw, (Data, DataFrame)):
            raw = [raw]
        elif raw is None:
            return [], InputShape.DATA_LIST

        if not isinstance(raw, list):
            msg = f"FilterRecords: unsupported records type: {type(raw).__name__}"
            raise TypeError(msg)

        if len(raw) == 0:
            return [], InputShape.DATA_LIST

        item_shapes = [detect_shape(item) for item in raw]
        merged: list[dict] = []
        for item in raw:
            merged.extend(to_record_list(item))
        out_shape = (
            InputShape.DATAFRAME
            if all(s is InputShape.DATAFRAME for s in item_shapes)
            else InputShape.DATA_LIST
        )
        return merged, out_shape

    def _validate(self) -> list[dict]:
        """Validate the conditions table. Returns the cleaned list of rows
        (blank rows stripped). Raises ValueError on user-facing errors.
        """
        import re as _re

        rows = self.conditions or []
        # Strip blank rows (no field set).
        cleaned = [r for r in rows if (r.get("field") or "").strip()]

        if not cleaned and self.mode == "Keep matching":
            msg = (
                "FilterRecords: add at least one condition, or switch Mode to "
                "'Exclude matching' to pass all records through unmatched."
            )
            raise ValueError(msg)

        for row in cleaned:
            operator = row.get("operator", "equals")
            value = row.get("value", "") or ""
            if operator == "matches regex":
                try:
                    _re.compile(value)
                except _re.error as exc:
                    msg = f"FilterRecords: Invalid regex '{value}': {exc}"
                    raise ValueError(msg) from exc
            elif operator == "between":
                parts = [p.strip() for p in value.split(",")]
                if len(parts) != 2 or not all(parts):
                    msg = (
                        f"FilterRecords: 'between' value must be exactly two "
                        f"comma-separated numbers (got '{value}')."
                    )
                    raise ValueError(msg)

        return cleaned

    def _row_predicate_for(self, record: dict, rows: list[dict]) -> bool:
        """Evaluate the cleaned conditions list against one record dict."""
        from lfx.components.processing._record_ops import evaluate, get_path

        if not rows:
            # Empty conditions reach here only with Exclude mode (Keep mode
            # was already rejected by _validate). Vacuously True.
            return True

        def one(row: dict) -> bool:
            field = row["field"]
            operator = row.get("operator", "equals")
            value = row.get("value", "") or ""
            field_value = get_path(record, field)
            return evaluate(operator, field_value, value)

        if self.combinator == "OR":
            return any(one(r) for r in rows)
        return all(one(r) for r in rows)

    def _partition(self) -> tuple[Any, Any]:
        from lfx.components.processing._record_ops import from_record_list

        cleaned_rows = self._validate()
        records, shape = self._normalize_records()
        invert = self.mode == "Exclude matching"

        matched_records: list[dict] = []
        unmatched_records: list[dict] = []
        for record in records:
            predicate = self._row_predicate_for(record, cleaned_rows)
            if invert:
                predicate = not predicate
            (matched_records if predicate else unmatched_records).append(record)

        return (
            from_record_list(matched_records, shape),
            from_record_list(unmatched_records, shape),
        )
