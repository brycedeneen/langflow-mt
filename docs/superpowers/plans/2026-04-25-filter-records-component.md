# FilterRecords + CombineRecords Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User standing rule (overrides skill defaults):** Pause and request explicit user approval before every `git commit` step in this plan. Stage explicit file paths only — never `git add -A` or `git add .`.

**Goal:** Ship two new Langflow processing components — `FilterRecords` (multi-condition predicate over Data/DataFrame with matched + unmatched outputs) and `CombineRecords` (append, union+dedupe, merge-by-key over Data/DataFrame).

**Architecture:** Two component classes in `src/lfx/src/lfx/components/processing/` share a private helper module `_record_ops.py` for predicate dispatch, dot-path field lookup, and `Data ↔ DataFrame` normalization. Both components branch internally on input shape; output type follows input type, except for CombineRecords with mixed inputs which coerces to DataFrame.

**Tech Stack:** Python 3.11+, pandas (already a Langflow dep), pytest + pytest-asyncio. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-25-filter-records-component-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/lfx/src/lfx/components/processing/_record_ops.py` | Create | Private helpers: 14-operator predicate table, `get_path` (dot/index field lookup), `detect_shape`, `to_record_list`, `from_record_list`. Single bare module (the helpers are small; no need for the `_data_mapper/` package pattern). |
| `src/lfx/src/lfx/components/processing/filter_records.py` | Create | `FilterRecordsComponent`. |
| `src/lfx/src/lfx/components/processing/combine_records.py` | Create | `CombineRecordsComponent`. |
| `src/lfx/src/lfx/components/processing/__init__.py` | Modify | Register both new components in three locations: `TYPE_CHECKING` block, `_dynamic_imports` dict, `__all__` list. Alphabetical. |
| `src/lfx/tests/unit/components/processing/test_record_ops.py` | Create | Helper unit tests. |
| `src/lfx/tests/unit/components/processing/test_filter_records.py` | Create | FilterRecordsComponent tests. |
| `src/lfx/tests/unit/components/processing/test_combine_records.py` | Create | CombineRecordsComponent tests. |

---

## Task 1: `get_path` field-path lookup

**Files:**
- Create: `src/lfx/src/lfx/components/processing/_record_ops.py`
- Test: `src/lfx/tests/unit/components/processing/test_record_ops.py`

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/components/processing/test_record_ops.py`:

```python
import pytest

from lfx.components.processing._record_ops import MISSING, get_path


@pytest.mark.parametrize(
    ("record", "path", "expected"),
    [
        ({"a": 1}, "a", 1),
        ({"a": {"b": 2}}, "a.b", 2),
        ({"a": {"b": {"c": 3}}}, "a.b.c", 3),
        ({"items": [{"sku": "x"}, {"sku": "y"}]}, "items[0].sku", "x"),
        ({"items": [{"sku": "x"}, {"sku": "y"}]}, "items[1].sku", "y"),
        ({"a": 1}, "missing", MISSING),
        ({"a": {"b": 2}}, "a.missing", MISSING),
        ({"items": []}, "items[0]", MISSING),
        ({"a": None}, "a.b", MISSING),
        ({}, "a", MISSING),
    ],
)
def test_get_path(record, path, expected):
    assert get_path(record, path) == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.components.processing._record_ops'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lfx/src/lfx/components/processing/_record_ops.py`:

```python
"""Shared helpers for FilterRecords and CombineRecords.

Private to the processing bundle. Not part of the public lfx API.
"""

from __future__ import annotations

import re
from typing import Any, Final

# Sentinel returned by get_path when a field is absent. Distinct from None
# (which is a legitimate stored value).
MISSING: Final = object()

_INDEX_RE = re.compile(r"^([^\[\]]+)\[(\d+)\]$")


def get_path(record: Any, path: str) -> Any:
    """Walk a dot-separated path, supporting `[N]` list indexing.

    Returns MISSING if any segment can't be resolved.
    """
    current: Any = record
    for raw_segment in path.split("."):
        if current is None:
            return MISSING
        match = _INDEX_RE.match(raw_segment)
        if match:
            key, index_str = match.group(1), match.group(2)
            if not isinstance(current, dict) or key not in current:
                return MISSING
            container = current[key]
            if not isinstance(container, list):
                return MISSING
            index = int(index_str)
            if index >= len(container):
                return MISSING
            current = container[index]
        else:
            if not isinstance(current, dict) or raw_segment not in current:
                return MISSING
            current = current[raw_segment]
    return current
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: PASS — 10 parametrized cases.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/_record_ops.py \
        src/lfx/tests/unit/components/processing/test_record_ops.py
git commit -m "feat(lfx/processing): add _record_ops.get_path helper

Dot-path lookup with [N] list indexing and MISSING sentinel for absent
paths. Shared by upcoming FilterRecords and CombineRecords components."
```

---

## Task 2: Predicate dispatch table (14 operators)

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/_record_ops.py`
- Test: `src/lfx/tests/unit/components/processing/test_record_ops.py`

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/components/processing/test_record_ops.py`:

```python
from lfx.components.processing._record_ops import OPERATORS, evaluate


@pytest.mark.parametrize(
    ("operator", "field_value", "raw_value", "expected"),
    [
        # equals / not equals — string and numeric coercion
        ("equals", "5", "5", True),
        ("equals", 5, "5", True),
        ("equals", "abc", "xyz", False),
        ("not equals", "abc", "xyz", True),
        ("not equals", 5, "5", False),
        # contains / does not contain
        ("contains", "hello world", "world", True),
        ("contains", ["a", "b", "c"], "b", True),
        ("contains", "hello", "xyz", False),
        ("does not contain", "hello", "xyz", True),
        # starts with / ends with
        ("starts with", "hello", "he", True),
        ("starts with", "hello", "lo", False),
        ("ends with", "hello", "lo", True),
        ("ends with", "hello", "he", False),
        # matches regex
        ("matches regex", "user-123", r"user-\d+", True),
        ("matches regex", "abc", r"^\d+$", False),
        # greater than / less than (numeric)
        ("greater than", 10, "5", True),
        ("greater than", "10", "5", True),
        ("less than", 5, "10", True),
        # greater than / less than (lexicographic fallback)
        ("greater than", "banana", "apple", True),
        ("less than", "apple", "banana", True),
        # between (inclusive)
        ("between", 5, "1,10", True),
        ("between", 1, "1,10", True),
        ("between", 10, "1,10", True),
        ("between", 11, "1,10", False),
        ("between", "abc", "1,10", False),
        # in / not in
        ("in", "x", "a, b, x", True),
        ("in", "z", "a, b, x", False),
        ("not in", "z", "a, b, x", True),
        # is empty / is not empty
        ("is empty", None, "", True),
        ("is empty", "", "", True),
        ("is empty", [], "", True),
        ("is empty", {}, "", True),
        ("is empty", "x", "", False),
        ("is empty", 0, "", False),  # 0 is NOT empty
        ("is not empty", "x", "", True),
        ("is not empty", None, "", False),
    ],
)
def test_evaluate_operators(operator, field_value, raw_value, expected):
    assert evaluate(operator, field_value, raw_value) is expected


def test_evaluate_unknown_operator_raises():
    with pytest.raises(KeyError):
        evaluate("does not exist", "x", "y")


def test_missing_field_all_comparisons_false_except_is_empty():
    assert evaluate("equals", MISSING, "x") is False
    assert evaluate("contains", MISSING, "x") is False
    assert evaluate("greater than", MISSING, "5") is False
    assert evaluate("is empty", MISSING, "") is True
    assert evaluate("is not empty", MISSING, "") is False


def test_operators_dict_lists_all_14():
    assert set(OPERATORS) == {
        "equals", "not equals",
        "contains", "does not contain",
        "starts with", "ends with",
        "matches regex",
        "greater than", "less than",
        "between",
        "in", "not in",
        "is empty", "is not empty",
    }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: FAIL — `ImportError: cannot import name 'OPERATORS'`.

- [ ] **Step 3: Implement the dispatch table**

Append to `src/lfx/src/lfx/components/processing/_record_ops.py`:

```python
def _coerce_float(value: Any) -> float | None:
    """Try to coerce to float. Return None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_empty(value: Any) -> bool:
    """True for None, "", [], {}, MISSING. Note: 0 and False are NOT empty."""
    if value is MISSING or value is None:
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) == 0
    return False


def _op_equals(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num == b_num
    return str(a) == str(b)


def _op_contains(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    if isinstance(a, list):
        # Membership in a list: try numeric coercion of b for numeric lists.
        b_num = _coerce_float(b)
        for item in a:
            if str(item) == b:
                return True
            if b_num is not None and _coerce_float(item) == b_num:
                return True
        return False
    return b in str(a)


def _op_starts_with(a: Any, b: str) -> bool:
    return False if a is MISSING else str(a).startswith(b)


def _op_ends_with(a: Any, b: str) -> bool:
    return False if a is MISSING else str(a).endswith(b)


def _op_regex(a: Any, b: str) -> bool:
    return False if a is MISSING else re.search(b, str(a)) is not None


def _op_gt(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num > b_num
    try:
        return str(a) > str(b)
    except TypeError:
        return False


def _op_lt(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num < b_num
    try:
        return str(a) < str(b)
    except TypeError:
        return False


def _op_between(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    parts = [p.strip() for p in b.split(",")]
    if len(parts) != 2:
        return False
    lo, hi = _coerce_float(parts[0]), _coerce_float(parts[1])
    a_num = _coerce_float(a)
    if lo is None or hi is None or a_num is None:
        return False
    return lo <= a_num <= hi


def _op_in(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    options = [p.strip() for p in b.split(",")]
    a_str = str(a)
    if a_str in options:
        return True
    a_num = _coerce_float(a)
    if a_num is not None:
        for opt in options:
            opt_num = _coerce_float(opt)
            if opt_num is not None and a_num == opt_num:
                return True
    return False


OPERATORS: Final[dict[str, Any]] = {
    "equals": _op_equals,
    "not equals": lambda a, b: not _op_equals(a, b) if a is not MISSING else False,
    "contains": _op_contains,
    "does not contain": lambda a, b: not _op_contains(a, b) if a is not MISSING else False,
    "starts with": _op_starts_with,
    "ends with": _op_ends_with,
    "matches regex": _op_regex,
    "greater than": _op_gt,
    "less than": _op_lt,
    "between": _op_between,
    "in": _op_in,
    "not in": lambda a, b: not _op_in(a, b) if a is not MISSING else False,
    "is empty": lambda a, _b: _is_empty(a),
    "is not empty": lambda a, _b: not _is_empty(a),
}


def evaluate(operator: str, field_value: Any, raw_value: str) -> bool:
    """Evaluate one operator against a field value and a raw user value.

    Raises KeyError if `operator` is not a recognized operator name.
    """
    return OPERATORS[operator](field_value, raw_value)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: PASS — all parametrized cases plus 4 standalone tests.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/_record_ops.py \
        src/lfx/tests/unit/components/processing/test_record_ops.py
git commit -m "feat(lfx/processing): add _record_ops predicate dispatch (14 operators)

Type-agnostic operator table with numeric coercion fallback to string
comparison. Missing fields (MISSING sentinel) cause comparison ops to
return False; only 'is empty' returns True for missing."
```

---

## Task 3: Shape detection + record-list normalization

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/_record_ops.py`
- Test: `src/lfx/tests/unit/components/processing/test_record_ops.py`

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/components/processing/test_record_ops.py`:

```python
import pandas as pd

from lfx.components.processing._record_ops import (
    InputShape,
    detect_shape,
    from_record_list,
    to_record_list,
)
from lfx.schema import Data, DataFrame


def test_detect_shape_data_single():
    assert detect_shape(Data(data={"a": 1})) is InputShape.DATA_SINGLE


def test_detect_shape_data_list():
    assert detect_shape([Data(data={"a": 1}), Data(data={"a": 2})]) is InputShape.DATA_LIST


def test_detect_shape_dataframe():
    df = DataFrame(pd.DataFrame([{"a": 1}, {"a": 2}]))
    assert detect_shape(df) is InputShape.DATAFRAME


def test_to_record_list_data_single():
    assert to_record_list(Data(data={"a": 1})) == [{"a": 1}]


def test_to_record_list_data_list():
    items = [Data(data={"a": 1}), Data(data={"a": 2})]
    assert to_record_list(items) == [{"a": 1}, {"a": 2}]


def test_to_record_list_dataframe():
    df = DataFrame(pd.DataFrame([{"a": 1}, {"a": 2}]))
    assert to_record_list(df) == [{"a": 1}, {"a": 2}]


def test_from_record_list_data_single():
    result = from_record_list([{"a": 1}], InputShape.DATA_SINGLE)
    assert isinstance(result, Data)
    assert result.data == {"a": 1}


def test_from_record_list_data_single_empty_returns_empty_data():
    result = from_record_list([], InputShape.DATA_SINGLE)
    assert isinstance(result, Data)
    assert result.data == {}


def test_from_record_list_data_list():
    result = from_record_list([{"a": 1}, {"a": 2}], InputShape.DATA_LIST)
    assert isinstance(result, list)
    assert all(isinstance(d, Data) for d in result)
    assert [d.data for d in result] == [{"a": 1}, {"a": 2}]


def test_from_record_list_dataframe():
    result = from_record_list([{"a": 1}, {"a": 2}], InputShape.DATAFRAME)
    assert isinstance(result, DataFrame)
    assert result.to_dict(orient="records") == [{"a": 1}, {"a": 2}]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: FAIL — `ImportError: cannot import name 'InputShape'`.

- [ ] **Step 3: Implement shape detection + normalization**

Add three imports to the top of `src/lfx/src/lfx/components/processing/_record_ops.py`, sorted alphabetically with the existing imports. The full import block at the top of the file should now read:

```python
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Final

import pandas as pd

from lfx.schema import Data, DataFrame
```

Then append the new symbols at the bottom of the file:

```python
class InputShape(Enum):
    DATA_SINGLE = "data_single"
    DATA_LIST = "data_list"
    DATAFRAME = "dataframe"


def detect_shape(value: Any) -> InputShape:
    """Detect the shape of a records-bearing input.

    Raises TypeError on anything that isn't Data, list[Data], or DataFrame.
    """
    if isinstance(value, DataFrame):
        return InputShape.DATAFRAME
    if isinstance(value, Data):
        return InputShape.DATA_SINGLE
    if isinstance(value, list) and all(isinstance(v, Data) for v in value):
        return InputShape.DATA_LIST
    msg = f"Unsupported input type: {type(value).__name__}. Expected Data, list[Data], or DataFrame."
    raise TypeError(msg)


def to_record_list(value: Any) -> list[dict]:
    """Normalize any supported input shape to a list of plain dicts."""
    shape = detect_shape(value)
    if shape is InputShape.DATA_SINGLE:
        return [dict(value.data)]
    if shape is InputShape.DATA_LIST:
        return [dict(item.data) for item in value]
    # DATAFRAME
    return value.to_dict(orient="records")


def from_record_list(records: list[dict], shape: InputShape) -> Any:
    """Convert a list of dicts back to the requested output shape."""
    if shape is InputShape.DATAFRAME:
        return DataFrame(pd.DataFrame(records))
    if shape is InputShape.DATA_LIST:
        return [Data(data=r) for r in records]
    # DATA_SINGLE — return first record (or empty Data if no records)
    return Data(data=records[0]) if records else Data(data={})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_record_ops.py -v
```

Expected: PASS — all 10 new tests + previous tests still passing.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/_record_ops.py \
        src/lfx/tests/unit/components/processing/test_record_ops.py
git commit -m "feat(lfx/processing): add InputShape detection + record-list normalize

Shared normalization layer for Data | list[Data] | DataFrame inputs.
Both upcoming FilterRecords and CombineRecords detect shape, normalize
to list[dict], operate, then de-normalize back to the input shape."
```

---

## Task 4: FilterRecordsComponent scaffold

**Files:**
- Create: `src/lfx/src/lfx/components/processing/filter_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_filter_records.py`

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/components/processing/test_filter_records.py`:

```python
from lfx.components.processing.filter_records import FilterRecordsComponent


def test_component_metadata():
    assert FilterRecordsComponent.display_name == "Filter Records"
    assert FilterRecordsComponent.name == "FilterRecords"
    assert FilterRecordsComponent.icon == "filter"
    assert FilterRecordsComponent.version == 1
    assert len(FilterRecordsComponent.changelog) == 1
    assert FilterRecordsComponent.changelog[0].version == 1


def test_component_declares_expected_inputs():
    input_names = [i.name for i in FilterRecordsComponent.inputs]
    assert input_names == ["records", "conditions", "combinator", "mode"]


def test_component_declares_two_outputs():
    output_names = [o.name for o in FilterRecordsComponent.outputs]
    assert output_names == ["matched", "unmatched"]


def test_component_keywords_include_filter():
    assert "filter" in FilterRecordsComponent.metadata["keywords"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.components.processing.filter_records'`.

- [ ] **Step 3: Create the component scaffold**

Create `src/lfx/src/lfx/components/processing/filter_records.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: PASS — 4 metadata/declaration tests.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/filter_records.py \
        src/lfx/tests/unit/components/processing/test_filter_records.py
git commit -m "feat(lfx/processing): scaffold FilterRecordsComponent

Class structure with inputs (records, conditions, combinator, mode),
two outputs (matched, unmatched), metadata, and changelog v1.
_partition() raises NotImplementedError; filter logic lands next."
```

---

## Task 5: FilterRecords filter logic (Data + DataFrame paths)

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/filter_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_filter_records.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/lfx/tests/unit/components/processing/test_filter_records.py`:

```python
import pandas as pd
import pytest

from lfx.schema import Data, DataFrame


def _records():
    return [
        Data(data={"name": "Alice", "age": 30, "country": "US"}),
        Data(data={"name": "Bob", "age": 25, "country": "UK"}),
        Data(data={"name": "Charlie", "age": 35, "country": "US"}),
    ]


def _df():
    return DataFrame(pd.DataFrame([
        {"name": "Alice", "age": 30, "country": "US"},
        {"name": "Bob", "age": 25, "country": "UK"},
        {"name": "Charlie", "age": 35, "country": "US"},
    ]))


def _new(records, conditions, combinator="AND", mode="Keep matching"):
    cmp = FilterRecordsComponent()
    cmp.records = records if isinstance(records, list) else [records]
    cmp.conditions = conditions
    cmp.combinator = combinator
    cmp.mode = mode
    return cmp


@pytest.mark.asyncio
async def test_filter_data_list_single_condition_keep():
    cmp = _new(_records(), [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert isinstance(matched, list)
    assert [d.data["name"] for d in matched] == ["Alice", "Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_single_condition_unmatched_complements():
    cmp = _new(_records(), [{"field": "country", "operator": "equals", "value": "US"}])
    unmatched = await cmp.build_unmatched()
    assert [d.data["name"] for d in unmatched] == ["Bob"]


@pytest.mark.asyncio
async def test_filter_data_list_and_combinator():
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "US"},
            {"field": "age", "operator": "greater than", "value": "31"},
        ],
        combinator="AND",
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_or_combinator():
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "UK"},
            {"field": "age", "operator": "greater than", "value": "31"},
        ],
        combinator="OR",
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Bob", "Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_exclude_mode_inverts():
    cmp = _new(
        _records(),
        [{"field": "country", "operator": "equals", "value": "US"}],
        mode="Exclude matching",
    )
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    # In Exclude mode, US records should land in 'unmatched'
    assert [d.data["name"] for d in matched] == ["Bob"]
    assert [d.data["name"] for d in unmatched] == ["Alice", "Charlie"]


@pytest.mark.asyncio
async def test_filter_dataframe_single_condition():
    cmp = _new(_df(), [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert isinstance(matched, DataFrame)
    assert matched.to_dict(orient="records") == [
        {"name": "Alice", "age": 30, "country": "US"},
        {"name": "Charlie", "age": 35, "country": "US"},
    ]


@pytest.mark.asyncio
async def test_filter_dataframe_or_combinator():
    cmp = _new(
        _df(),
        [
            {"field": "country", "operator": "equals", "value": "UK"},
            {"field": "age", "operator": "less than", "value": "31"},
        ],
        combinator="OR",
    )
    matched = await cmp.build_matched()
    assert sorted(d["name"] for d in matched.to_dict(orient="records")) == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_filter_single_data_returns_list_of_one():
    """is_list=True wraps single Data → list[Data] of one record out.

    Output shape rule: list[Data] unless ALL inputs are DataFrames.
    """
    cmp = _new(
        Data(data={"name": "Alice", "country": "US"}),
        [{"field": "country", "operator": "equals", "value": "US"}],
    )
    matched = await cmp.build_matched()
    assert isinstance(matched, list)
    assert len(matched) == 1
    assert matched[0].data == {"name": "Alice", "country": "US"}


@pytest.mark.asyncio
async def test_filter_missing_field_treated_as_not_matching():
    records = [
        Data(data={"name": "Alice", "country": "US"}),
        Data(data={"name": "Bob"}),  # no 'country' key
    ]
    cmp = _new(records, [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Alice"]


@pytest.mark.asyncio
async def test_filter_empty_input_empty_output():
    cmp = _new([], [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    assert matched == []
    assert unmatched == []


@pytest.mark.asyncio
async def test_filter_is_list_handle_input_framework_shape():
    """is_list=True means the framework delivers self.records as a list.
    Verify the component handles the framework's wrapping correctly.
    """
    cmp = FilterRecordsComponent()
    # When the user wires a single Data, framework delivers [Data(...)].
    cmp.records = [Data(data={"name": "Alice", "country": "US"})]
    cmp.conditions = [{"field": "country", "operator": "equals", "value": "US"}]
    cmp.combinator = "AND"
    cmp.mode = "Keep matching"
    matched = await cmp.build_matched()
    # Output rule: list[Data] unless all inputs are DataFrames.
    assert isinstance(matched, list)
    assert len(matched) == 1
    assert matched[0].data == {"name": "Alice", "country": "US"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: FAIL — `NotImplementedError: FilterRecordsComponent._partition is not implemented yet.` for the 11 new tests.

- [ ] **Step 3: Implement the filter logic**

Replace the `_partition` method (and add `_normalize_records` helper) in `src/lfx/src/lfx/components/processing/filter_records.py`:

```python
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

    def _row_predicate(self, record: dict) -> bool:
        """Evaluate the conditions table against one record dict."""
        from lfx.components.processing._record_ops import evaluate, get_path

        rows = self.conditions or []
        if not rows:
            # Empty conditions: vacuously True for AND, vacuously False for OR.
            # Build-time validation rejects this with Keep mode, so OR with
            # empty conditions only reaches us in Exclude mode.
            return True if self.combinator == "AND" else False

        def one(row: dict) -> bool:
            field = row.get("field", "")
            operator = row.get("operator", "equals")
            value = row.get("value", "") or ""
            field_value = get_path(record, field) if field else None
            return evaluate(operator, field_value, value)

        if self.combinator == "OR":
            return any(one(r) for r in rows)
        return all(one(r) for r in rows)

    def _partition(self) -> tuple[Any, Any]:
        from lfx.components.processing._record_ops import from_record_list

        records, shape = self._normalize_records()
        invert = self.mode == "Exclude matching"

        matched_records: list[dict] = []
        unmatched_records: list[dict] = []
        for record in records:
            predicate = self._row_predicate(record)
            if invert:
                predicate = not predicate
            (matched_records if predicate else unmatched_records).append(record)

        return (
            from_record_list(matched_records, shape),
            from_record_list(unmatched_records, shape),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: PASS — all 15 tests (4 from Task 4 + 11 new).

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/filter_records.py \
        src/lfx/tests/unit/components/processing/test_filter_records.py
git commit -m "feat(lfx/processing): implement FilterRecords filter logic

Data and DataFrame paths share the same predicate evaluator (per-row
Python evaluation through _record_ops). Mode toggle inverts predicate
before matched/unmatched split, so output names stay literal."
```

---

## Task 6: FilterRecords build-time validation

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/filter_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_filter_records.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/lfx/tests/unit/components/processing/test_filter_records.py`:

```python
@pytest.mark.asyncio
async def test_validation_invalid_regex_raises():
    cmp = _new(
        _records(),
        [{"field": "name", "operator": "matches regex", "value": "[unclosed"}],
    )
    with pytest.raises(ValueError, match="Invalid regex"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_between_wrong_value_count_raises():
    cmp = _new(
        _records(),
        [{"field": "age", "operator": "between", "value": "10"}],
    )
    with pytest.raises(ValueError, match="between"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_empty_conditions_with_keep_mode_raises():
    cmp = _new(_records(), [], mode="Keep matching")
    with pytest.raises(ValueError, match="at least one condition"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_empty_conditions_with_exclude_mode_returns_all_unmatched():
    cmp = _new(_records(), [], mode="Exclude matching")
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    # Empty conditions are vacuously True; Exclude inverts to False;
    # so all records land in unmatched.
    assert [d.data["name"] for d in matched] == []
    assert [d.data["name"] for d in unmatched] == ["Alice", "Bob", "Charlie"]


@pytest.mark.asyncio
async def test_validation_skips_blank_rows():
    """User adds a row, doesn't fill it in. Should be ignored, not raise."""
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "US"},
            {"field": "", "operator": "equals", "value": ""},
        ],
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Alice", "Charlie"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: FAIL — none of the validation behaviors exist yet.

- [ ] **Step 3: Add validation**

In `src/lfx/src/lfx/components/processing/filter_records.py`, add a `_validate` method and call it from `_partition` (and update `_row_predicate` to skip blank rows):

```python
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
```

Then update `_partition` to use validated rows:

```python
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
```

And rename `_row_predicate` to `_row_predicate_for(self, record, rows)` (taking the cleaned rows as a parameter). Replace the existing method body:

```python
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
```

(Delete the old `_row_predicate` method entirely — it's replaced by `_row_predicate_for`.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: PASS — all 20 tests (15 from before + 5 new).

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/filter_records.py \
        src/lfx/tests/unit/components/processing/test_filter_records.py
git commit -m "feat(lfx/processing): FilterRecords build-time validation

Validates regex compiles, between has two numbers, and empty conditions
under Keep mode is a hard error. Blank rows in the conditions table are
silently stripped (user added a row, didn't fill it in)."
```

---

## Task 7: Register FilterRecords in the processing bundle

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/__init__.py`
- Test: `src/lfx/tests/unit/components/processing/test_filter_records.py`

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/components/processing/test_filter_records.py`:

```python
def test_component_is_registered_in_bundle():
    from lfx.components import processing

    assert "FilterRecordsComponent" in processing.__all__
    assert processing.FilterRecordsComponent is FilterRecordsComponent
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py::test_component_is_registered_in_bundle -v
```

Expected: FAIL — `'FilterRecordsComponent' is not in __all__`.

- [ ] **Step 3: Register the component**

Edit `src/lfx/src/lfx/components/processing/__init__.py`. Three insertions, alphabetical by module name (which matches the file's existing ordering convention).

(1) In the `TYPE_CHECKING` block, add between `dataframe_operations` and `json_cleaner`:

```python
    from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
    from lfx.components.processing.filter_records import FilterRecordsComponent
    from lfx.components.processing.json_cleaner import JSONCleaner
```

(2) In `_dynamic_imports`, add after `"DataFrameOperationsComponent"`:

```python
    "DataFrameOperationsComponent": "dataframe_operations",
    "FilterRecordsComponent": "filter_records",
    "JSONCleaner": "json_cleaner",
```

(3) In `__all__`, add after `"DataOperationsComponent"`:

```python
    "DataOperationsComponent",
    "FilterRecordsComponent",
    "JSONCleaner",
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_filter_records.py -v
```

Expected: PASS — all 21 tests.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/__init__.py \
        src/lfx/tests/unit/components/processing/test_filter_records.py
git commit -m "feat(lfx/processing): register FilterRecordsComponent in bundle"
```

---

## Task 8: CombineRecordsComponent scaffold + dynamic field switching

**Files:**
- Create: `src/lfx/src/lfx/components/processing/combine_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_combine_records.py`

- [ ] **Step 1: Write the failing tests**

Create `src/lfx/tests/unit/components/processing/test_combine_records.py`:

```python
import pytest

from lfx.components.processing.combine_records import CombineRecordsComponent


def test_component_metadata():
    assert CombineRecordsComponent.display_name == "Combine Records"
    assert CombineRecordsComponent.name == "CombineRecords"
    assert CombineRecordsComponent.icon == "merge"
    assert CombineRecordsComponent.version == 1
    assert len(CombineRecordsComponent.changelog) == 1


def test_component_declares_expected_inputs():
    input_names = [i.name for i in CombineRecordsComponent.inputs]
    assert input_names == ["mode", "left", "right", "dedupe_keys", "join_keys", "join_type"]


def test_component_declares_one_output():
    output_names = [o.name for o in CombineRecordsComponent.outputs]
    assert output_names == ["combined"]


def test_dynamic_fields_hidden_in_append_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": True},
        "join_keys": {"show": True},
        "join_type": {"show": True},
    }
    result = cmp.update_build_config(build_config, "Append", "mode")
    assert result["dedupe_keys"]["show"] is False
    assert result["join_keys"]["show"] is False
    assert result["join_type"]["show"] is False


def test_dynamic_fields_dedupe_visible_in_union_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": False},
        "join_keys": {"show": True},
        "join_type": {"show": True},
    }
    result = cmp.update_build_config(build_config, "Union (dedupe)", "mode")
    assert result["dedupe_keys"]["show"] is True
    assert result["join_keys"]["show"] is False
    assert result["join_type"]["show"] is False


def test_dynamic_fields_join_visible_in_merge_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": True},
        "join_keys": {"show": False},
        "join_type": {"show": False},
    }
    result = cmp.update_build_config(build_config, "Merge by key", "mode")
    assert result["dedupe_keys"]["show"] is False
    assert result["join_keys"]["show"] is True
    assert result["join_type"]["show"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.components.processing.combine_records'`.

- [ ] **Step 3: Create the component scaffold**

Create `src/lfx/src/lfx/components/processing/combine_records.py`:

```python
"""CombineRecords — append, union+dedupe, or merge-by-key over Data/DataFrame."""

from __future__ import annotations

from typing import Any, ClassVar

from lfx.custom import Component
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema import Data, DataFrame


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: PASS — 6 metadata/declaration/dynamic-field tests.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/combine_records.py \
        src/lfx/tests/unit/components/processing/test_combine_records.py
git commit -m "feat(lfx/processing): scaffold CombineRecordsComponent

Class structure with mode dropdown driving dynamic visibility of
dedupe_keys / join_keys / join_type. build_combined() raises
NotImplementedError; mode logic lands in subsequent tasks."
```

---

## Task 9: CombineRecords Append + Union (dedupe) modes

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/combine_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_combine_records.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/lfx/tests/unit/components/processing/test_combine_records.py`:

```python
import pandas as pd

from lfx.schema import Data, DataFrame


def _data_list(records):
    return [Data(data=r) for r in records]


def _df(records):
    return DataFrame(pd.DataFrame(records))


def _new_combine(left, right, mode="Append", dedupe_keys="", join_keys="", join_type="inner"):
    cmp = CombineRecordsComponent()
    cmp.left = left
    cmp.right = right
    cmp.mode = mode
    cmp.dedupe_keys = dedupe_keys
    cmp.join_keys = join_keys
    cmp.join_type = join_type
    return cmp


@pytest.mark.asyncio
async def test_append_data_lists_preserves_order():
    left = _data_list([{"id": 1}, {"id": 2}])
    right = _data_list([{"id": 3}, {"id": 4}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, list)
    assert [d.data["id"] for d in result] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_append_dataframes_preserves_order():
    left = _df([{"id": 1}, {"id": 2}])
    right = _df([{"id": 3}, {"id": 4}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert [r["id"] for r in result.to_dict(orient="records")] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_append_does_not_dedupe():
    left = _data_list([{"id": 1}, {"id": 2}])
    right = _data_list([{"id": 1}, {"id": 3}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1, 2, 1, 3]


@pytest.mark.asyncio
async def test_union_dedupe_by_full_equality():
    left = _data_list([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    right = _data_list([{"id": 1, "name": "A"}, {"id": 3, "name": "C"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1, 2, 3]


@pytest.mark.asyncio
async def test_union_dedupe_by_single_key_first_occurrence_wins():
    """If two records share the dedupe key, the LEFT one survives."""
    left = _data_list([{"id": 1, "name": "Alice-L"}])
    right = _data_list([{"id": 1, "name": "Alice-R"}, {"id": 2, "name": "Bob"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="id")
    result = await cmp.build_combined()
    assert [(d.data["id"], d.data["name"]) for d in result] == [
        (1, "Alice-L"), (2, "Bob"),
    ]


@pytest.mark.asyncio
async def test_union_dedupe_by_multiple_keys():
    left = _data_list([
        {"a": 1, "b": "x", "v": "L1"},
        {"a": 1, "b": "y", "v": "L2"},
    ])
    right = _data_list([
        {"a": 1, "b": "x", "v": "R1"},  # dup of left[0] by (a, b)
        {"a": 2, "b": "x", "v": "R2"},
    ])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="a, b")
    result = await cmp.build_combined()
    assert [d.data["v"] for d in result] == ["L1", "L2", "R2"]


@pytest.mark.asyncio
async def test_union_dedupe_dataframe():
    left = _df([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    right = _df([{"id": 1, "name": "A"}, {"id": 3, "name": "C"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="id")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert [r["id"] for r in result.to_dict(orient="records")] == [1, 2, 3]


@pytest.mark.asyncio
async def test_empty_left_returns_right():
    left = _data_list([])
    right = _data_list([{"id": 1}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1]


@pytest.mark.asyncio
async def test_empty_both_returns_empty():
    cmp = _new_combine(_data_list([]), _data_list([]), mode="Append")
    result = await cmp.build_combined()
    assert result == [] or (isinstance(result, list) and len(result) == 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement Append + Union modes**

In `src/lfx/src/lfx/components/processing/combine_records.py`, replace `build_combined`:

```python
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
```

Add `_hashable` helper at module level (above the class):

```python
def _hashable(value: Any) -> Any:
    """Return a hashable form of `value` for use in dedupe signatures."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    return str(value)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: PASS — Append + Union tests pass; Merge tests don't exist yet (Task 10).

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/combine_records.py \
        src/lfx/tests/unit/components/processing/test_combine_records.py
git commit -m "feat(lfx/processing): CombineRecords Append + Union (dedupe) modes

Append concatenates without dedupe; Union dedupes by full-record
equality (default) or by user-specified keys, first occurrence wins.
Merge by key still raises NotImplementedError."
```

---

## Task 10: CombineRecords Merge by key mode

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/combine_records.py`
- Test: `src/lfx/tests/unit/components/processing/test_combine_records.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/lfx/tests/unit/components/processing/test_combine_records.py`:

```python
@pytest.mark.asyncio
async def test_merge_by_key_inner_join():
    left = _data_list([
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ])
    right = _data_list([
        {"id": 1, "country": "US"},
        {"id": 2, "country": "UK"},
        {"id": 4, "country": "CA"},
    ])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    rows = [d.data for d in result]
    assert sorted(r["id"] for r in rows) == [1, 2]
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["name"] == "Alice" and by_id[1]["country"] == "US"
    assert by_id[2]["name"] == "Bob" and by_id[2]["country"] == "UK"


@pytest.mark.asyncio
async def test_merge_by_key_left_join():
    left = _data_list([{"id": 1, "n": "A"}, {"id": 2, "n": "B"}])
    right = _data_list([{"id": 1, "c": "US"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="left")
    result = await cmp.build_combined()
    rows = sorted([d.data for d in result], key=lambda r: r["id"])
    assert rows[0]["id"] == 1 and rows[0]["c"] == "US"
    assert rows[1]["id"] == 2 and (rows[1].get("c") is None or pd.isna(rows[1]["c"]))


@pytest.mark.asyncio
async def test_merge_by_key_right_join():
    left = _data_list([{"id": 1, "n": "A"}])
    right = _data_list([{"id": 1, "c": "US"}, {"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="right")
    result = await cmp.build_combined()
    rows = sorted([d.data for d in result], key=lambda r: r["id"])
    assert len(rows) == 2
    assert rows[1]["id"] == 2


@pytest.mark.asyncio
async def test_merge_by_key_outer_join():
    left = _data_list([{"id": 1, "n": "A"}])
    right = _data_list([{"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="outer")
    result = await cmp.build_combined()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_merge_by_key_multi_key():
    left = _data_list([
        {"a": 1, "b": "x", "n": "L1"},
        {"a": 1, "b": "y", "n": "L2"},
    ])
    right = _data_list([
        {"a": 1, "b": "x", "c": "R1"},
    ])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="a, b", join_type="inner")
    result = await cmp.build_combined()
    rows = [d.data for d in result]
    assert len(rows) == 1
    assert rows[0]["n"] == "L1" and rows[0]["c"] == "R1"


@pytest.mark.asyncio
async def test_merge_by_key_dataframe():
    left = _df([{"id": 1, "n": "A"}, {"id": 2, "n": "B"}])
    right = _df([{"id": 1, "c": "US"}, {"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    rows = sorted(result.to_dict(orient="records"), key=lambda r: r["id"])
    assert rows[0]["n"] == "A" and rows[0]["c"] == "US"


@pytest.mark.asyncio
async def test_merge_by_key_validation_missing_join_keys_raises():
    cmp = _new_combine(
        _data_list([{"id": 1}]),
        _data_list([{"id": 1}]),
        mode="Merge by key",
        join_keys="",
    )
    with pytest.raises(ValueError, match="join_keys"):
        await cmp.build_combined()


@pytest.mark.asyncio
async def test_merge_by_key_column_conflict_suffixes():
    """When both sides have a non-key column with the same name, pandas
    suffixes them with _left / _right (we use those suffixes explicitly)."""
    left = _data_list([{"id": 1, "name": "L"}])
    right = _data_list([{"id": 1, "name": "R"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    row = result[0].data
    assert row["name_left"] == "L"
    assert row["name_right"] == "R"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: FAIL — `NotImplementedError: Merge by key not implemented yet.`

- [ ] **Step 3: Implement Merge by key**

In `src/lfx/src/lfx/components/processing/combine_records.py`, replace `_merge_by_key` and add an import at the top of the file:

```python
import pandas as pd
```

Then replace `_merge_by_key`:

```python
    def _merge_by_key(self, left: list[dict], right: list[dict]) -> list[dict]:
        keys_str = (self.join_keys or "").strip()
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not keys:
            msg = "CombineRecords: 'Merge by key' requires at least one join_keys value."
            raise ValueError(msg)

        join_type = self.join_type or "inner"
        if join_type not in ("inner", "left", "right", "outer"):
            msg = f"CombineRecords: unknown join_type '{join_type}'."
            raise ValueError(msg)

        left_df = pd.DataFrame(left) if left else pd.DataFrame(columns=keys)
        right_df = pd.DataFrame(right) if right else pd.DataFrame(columns=keys)

        merged = left_df.merge(
            right_df,
            on=keys,
            how=join_type,
            suffixes=("_left", "_right"),
        )
        # Replace pandas NaN with None for cleaner JSON-ish records.
        merged = merged.where(pd.notna(merged), None)
        return merged.to_dict(orient="records")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: PASS — all combine tests now pass.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/combine_records.py \
        src/lfx/tests/unit/components/processing/test_combine_records.py
git commit -m "feat(lfx/processing): CombineRecords Merge by key (relational join)

Uses pandas merge for all four join types. Single or multi-key joins;
column conflicts get _left / _right suffixes; NaN converted to None
for clean Data round-tripping. Validates join_keys is non-empty."
```

---

## Task 11: CombineRecords mixed-input coercion + bundle registration

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/__init__.py`
- Test: `src/lfx/tests/unit/components/processing/test_combine_records.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/lfx/tests/unit/components/processing/test_combine_records.py`:

```python
@pytest.mark.asyncio
async def test_mixed_inputs_coerce_to_dataframe():
    """Data + DataFrame in → DataFrame out (per spec)."""
    left = _data_list([{"id": 1, "name": "A"}])
    right = _df([{"id": 2, "name": "B"}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert sorted(r["id"] for r in result.to_dict(orient="records")) == [1, 2]


@pytest.mark.asyncio
async def test_mixed_inputs_dataframe_left():
    left = _df([{"id": 1, "name": "A"}])
    right = _data_list([{"id": 2, "name": "B"}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)


def test_component_is_registered_in_bundle():
    from lfx.components import processing

    assert "CombineRecordsComponent" in processing.__all__
    assert processing.CombineRecordsComponent is CombineRecordsComponent
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: The mixed-input tests should already PASS (the existing `_output_shape` logic handles this). The registration test should FAIL — `'CombineRecordsComponent' is not in __all__`.

(If the mixed-input tests fail, fix the implementation before continuing — but the existing logic in Task 9 was written to handle this.)

- [ ] **Step 3: Register CombineRecordsComponent**

Edit `src/lfx/src/lfx/components/processing/__init__.py`. Three insertions, alphabetical (`combine_records` sorts before `combine_text`).

(1) `TYPE_CHECKING` block — add before the existing `CombineTextComponent` line:

```python
    from lfx.components.processing.combine_records import CombineRecordsComponent
    from lfx.components.processing.combine_text import CombineTextComponent
    from lfx.components.processing.converter import TypeConverterComponent
```

(2) `_dynamic_imports` — add before the existing `"CombineTextComponent"` entry:

```python
    "CombineRecordsComponent": "combine_records",
    "CombineTextComponent": "combine_text",
    "TypeConverterComponent": "converter",
```

(3) `__all__` — add at the start, before `"CombineTextComponent"`:

```python
__all__ = [
    "CombineRecordsComponent",
    "CombineTextComponent",
    "CreateListComponent",
    ...
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/test_combine_records.py -v
```

Expected: PASS — all combine tests pass, including registration.

- [ ] **Step 5: Commit (request approval first)**

```bash
git add src/lfx/src/lfx/components/processing/__init__.py \
        src/lfx/tests/unit/components/processing/test_combine_records.py
git commit -m "feat(lfx/processing): register CombineRecordsComponent in bundle"
```

---

## Task 12: End-to-end validation

**Files:** No code changes — verification only.

- [ ] **Step 1: Run the changelog/version test suite**

Per the langflow-component-authoring skill:

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v
```

Expected: PASS. Both new components have `version=1` and a single `ChangelogEntry(version=1, ...)`, so they should satisfy the changelog discipline test.

- [ ] **Step 2: Run the full processing-component test suite**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/components/processing/ -v
```

Expected: PASS — including all pre-existing processing tests (no regressions) and the three new test files (`test_record_ops.py`, `test_filter_records.py`, `test_combine_records.py`).

- [ ] **Step 3: Smoke test via Python import**

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run python -c "
from lfx.components.processing import FilterRecordsComponent, CombineRecordsComponent
print('FilterRecords:', FilterRecordsComponent.display_name, 'v', FilterRecordsComponent.version)
print('CombineRecords:', CombineRecordsComponent.display_name, 'v', CombineRecordsComponent.version)
print('Filter inputs:', [i.name for i in FilterRecordsComponent.inputs])
print('Combine inputs:', [i.name for i in CombineRecordsComponent.inputs])
"
```

Expected output:

```
FilterRecords: Filter Records v 1
CombineRecords: Combine Records v 1
Filter inputs: ['records', 'conditions', 'combinator', 'mode']
Combine inputs: ['mode', 'left', 'right', 'dedupe_keys', 'join_keys', 'join_type']
```

- [ ] **Step 4: Manual UI verification (operator and reporter checklist)**

Start the Langflow dev server and verify in the browser:

1. Both `FilterRecords` and `CombineRecords` appear in the sidebar under "Processing".
2. Drag `FilterRecords` onto the canvas:
   - The conditions table renders with three columns.
   - The operator column is a dropdown with all 14 operators.
   - Adding a row works; removing a row works.
   - Both `matched` and `unmatched` output handles are visible.
3. Drag `CombineRecords` onto the canvas:
   - Switching the `mode` dropdown to `Union (dedupe)` reveals only `dedupe_keys`.
   - Switching to `Merge by key` reveals `join_keys` and `join_type`, hides `dedupe_keys`.
   - Switching back to `Append` hides all three.
4. Wire a simple flow: a Data source → FilterRecords → output. Run it. Verify matched output is correct for at least one operator.

If any of these fail, file a follow-up bug — do not silently fix; the component-discovery and dynamic-field-switching surface area is fragile and the failure mode tells us something about the loader.

- [ ] **Step 5: Final commit (no code changes; only if there were follow-up fixes from manual verification)**

If manual verification surfaced any fixes, commit them with explicit file paths:

```bash
git add <specific files>
git commit -m "fix(lfx/processing): <specific issue from manual verification>"
```

If no fixes were needed, skip this step. Both components are shippable as-is.

---

## Out of scope (per spec)

- DataOperationsComponent rename / cleanup.
- Deprecating existing legacy filter/select/merge components (already legacy).
- Visual condition builder UI.
- Grouped AND/OR (nested condition trees).
- Interleave/zip combine mode.
