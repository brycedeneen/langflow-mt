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

    def _partition(self) -> tuple[Any, Any]:
        msg = "FilterRecordsComponent._partition is not implemented yet."
        raise NotImplementedError(msg)
