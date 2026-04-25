# FilterRecords + CombineRecords — Design

**Date:** 2026-04-25
**Status:** Draft (pending implementation)
**Author:** bryced + Claude

## Problem

Langflow has no first-class iPaaS-style "filter records" component. The existing surface is fragmented:

- `FilterDataComponent`, `FilterDataValuesComponent`, `SelectDataComponent`, `MergeDataComponent` — all marked `legacy=True`, all point at `DataOperationsComponent` as their replacement.
- `DataOperationsComponent` (display name "JSON Operations") *does* expose `Filter Values` and `Combine` ops, but it's a 9-operation utility component that has no active use in any flow today, and its filter is single-condition only.
- `DataFrameOperationsComponent` (display name "Table Operations") has a full Filter op but only on `DataFrame` inputs.

Net effect: a user looking for "filter" in the sidebar finds two legacy entries and one tabular-only component — none of which match the iPaaS mental model of "stream of records, multi-condition predicate, kept vs excluded outputs". And there's no symmetric "combine two record streams" component to pair with it.

## Goals

1. Ship a discoverable `FilterRecords` component that:
   - Accepts both `Data` (or `list[Data]`) and `DataFrame` inputs without forcing the user to convert.
   - Supports multi-condition filtering (flat AND/OR) — the Zapier/Make default.
   - Exposes both kept and excluded outputs so users can wire dual paths in one node.
2. Ship a symmetric `CombineRecords` component for the three combine verbs that don't already exist as discoverable components: append, union+dedupe, merge-by-key.
3. Keep both components single-purpose. Resist the temptation to bundle them into a renamed `DataOperations`.

## Non-goals

- Renaming, repurposing, or cleaning up `DataOperationsComponent` itself. That is a separate effort.
- Deprecating the existing legacy filter/select/merge components (already legacy; nothing to do).
- Grouped AND/OR — `(A AND B) OR (C AND D)` — deferred. v1 is flat AND or flat OR only.
- Interleave/zip-by-index combine mode — deferred. Real use cases are rare and a custom Python step is cleaner.
- A visual condition-builder UI widget. v1 uses Langflow's existing `TableInput` for condition rows.
- Type inference from upstream data shape. v1 operators are type-agnostic with runtime coercion.

## Architecture

Two new components under `src/lfx/src/lfx/components/processing/`:

- `filter_records.py` → `FilterRecordsComponent`
- `combine_records.py` → `CombineRecordsComponent`

Plus one private helper module:

- `_record_ops.py` — predicate dispatch table, `Data ↔ DataFrame` normalization, dot-path field lookup. Both components import from here. Underscore prefix signals "private to the processing bundle, not a public API".

Both components accept `Data | list[Data] | DataFrame` and return the same shape they were given (no surprise type changes). Mixed-input cases for `CombineRecords` coerce to `DataFrame` because joins/dedupe are cleaner there; this is documented in the component description.

### Why two components, not one mega-operation

Filter and combine are different verbs (filter shrinks N→k; combine grows N+M→N+M). Bundling them behind a "mode" dropdown would make both components worse and would hurt discoverability — "Filter" is the single most-reached-for iPaaS verb and users search for it by name.

Bundling them into the existing `DataOperations` was also rejected: a 9-operation mega-component with the filter buried one click deep is the *current* state, and it's exactly what this spec is replacing.

## FilterRecords

### Inputs

| Field | Type | Notes |
|---|---|---|
| `records` | `HandleInput(input_types=["Data", "DataFrame"], is_list=True)` | Multiple `Data` connections merge into one stream. |
| `conditions` | `TableInput` | Three columns: `field` (str), `operator` (dropdown of 14), `value` (str). N rows, user adds/removes. |
| `combinator` | `DropdownInput(options=["AND", "OR"], value="AND")` | How to join the N condition rows. |
| `mode` | `DropdownInput(options=["Keep matching", "Exclude matching"], value="Keep matching")` | Inverts the predicate. See "Outputs" below. |

### Operators (14)

Type-agnostic. Any operator works on any field; coercion happens at evaluation time.

| Operator | Behavior |
|---|---|
| `equals` | `==` after attempted numeric coercion of both sides; falls back to string equality. |
| `not equals` | Inverse of `equals`. |
| `contains` | Substring for strings, membership for lists. |
| `does not contain` | Inverse of `contains`. |
| `starts with` | String prefix. |
| `ends with` | String suffix. |
| `matches regex` | `re.search` against the stringified field. Regex compiled once per condition row at build time; invalid regex raises at build time, not per-row. |
| `greater than` | Numeric if both coerce to float, otherwise lexicographic string comparison. |
| `less than` | As above. |
| `between` | Numeric only. `value` must comma-split into exactly two numbers; both endpoints inclusive. Validated at build time. |
| `in` | Comma-split `value` into a list, whitespace-trimmed; field must be in that list. |
| `not in` | Inverse of `in`. |
| `is empty` | True if field is `None`, `""`, `[]`, `{}`, or the field path is missing. |
| `is not empty` | Inverse of `is empty`. |

### Outputs

Two outputs, always present:

- `matched` — records where the (combined, mode-adjusted) predicate is True.
- `unmatched` — records where it's False.

`mode = "Exclude matching"` inverts the predicate before the matched/unmatched split. So with `mode = "Exclude matching"`, records that satisfy the user's conditions land in `unmatched`. Output names stay literal — `matched` always means "matched the effective predicate after mode". This invariant lets users wire either or both outputs without thinking about which "side" they configured.

### Field path

Dot notation. `address.city` walks nested dicts; `items[0].sku` indexes into a list. A missing path is treated as field-not-present (predicate returns False for all comparisons; `is empty` returns True). No exception is raised for missing fields — this is critical for streams where records have heterogeneous shapes.

### Type coercion at predicate time

The `value` column in `TableInput` is always string (TableInput's storage model). We coerce at evaluation:

- Numeric operators (`gt`, `lt`, `between`) — try `float()` on both sides; on `ValueError`, the row's predicate is False (don't blow up the stream).
- `in` / `not in` — comma-split, whitespace-trimmed.
- `between` — exactly two values after split.
- `regex` — compiled once at build time; reused per row.
- String operators — `str()` both sides.

### Build-time validation

Raised during `build()` (before any rows are evaluated):

- Invalid regex pattern.
- `between` with anything other than exactly 2 comma-separated values.
- `conditions` table empty *and* `mode = "Keep matching"` → emit a clear error ("Add at least one condition or switch to Exclude matching"). Empty conditions with `mode = "Exclude matching"` returns everything unmatched, which is meaningful.

## CombineRecords

### Inputs

| Field | Type | Notes |
|---|---|---|
| `mode` | `DropdownInput(options=["Append", "Union (dedupe)", "Merge by key"], value="Append", real_time_refresh=True)` | Drives `update_build_config`. |
| `left` | `HandleInput(input_types=["Data", "DataFrame"])` | First input. |
| `right` | `HandleInput(input_types=["Data", "DataFrame"])` | Second input. |
| `dedupe_keys` | `StrInput`, `dynamic=True, show=False` | Comma-separated field names. Visible only in `Union (dedupe)` mode. |
| `join_keys` | `StrInput`, `dynamic=True, show=False` | Comma-separated field names. Visible only in `Merge by key` mode. |
| `join_type` | `DropdownInput(options=["inner", "left", "right", "outer"], value="inner")`, `dynamic=True, show=False` | Visible only in `Merge by key` mode. |

`update_build_config` toggles the dynamic fields based on `mode`, following the `TextOperationsComponent` pattern.

### Modes

- **Append** — concatenate `left` then `right`. No key matching. Preserves order. No dedupe.
- **Union (dedupe)** — concatenate, then drop duplicates. If `dedupe_keys` is empty, dedupe by full-record equality. If `dedupe_keys` is set, dedupe by the tuple of those field values (first occurrence wins).
- **Merge by key** — relational join on `join_keys`. `join_type` selects inner/left/right/outer. Empty `join_keys` raises at build time. Column-conflict resolution: when both sides have a non-key field with the same name and different values, suffix with `_left` / `_right` (matches pandas default).

### Output

Single `combined` output. Type follows inputs:

- Both `DataFrame` → `DataFrame` out.
- Both `Data` (or `list[Data]`) → `Data` (or `list[Data]`) out.
- Mixed → coerce to `DataFrame` and emit `DataFrame`. The class docstring/description spells this out.

### Build-time validation

- `Merge by key` with empty `join_keys` → raise.
- `Union (dedupe)` with `dedupe_keys` referencing a field that exists on neither input → raise.

## Shared helper module

`_record_ops.py` contains:

```python
# Predicate dispatch — operator name → callable(field_value, raw_value) -> bool
PREDICATES: dict[str, Callable[[Any, str], bool]] = {...}

# Field path lookup — supports "a.b.c" and "a[0].b"
def get_path(record: dict, path: str) -> Any: ...

# Normalization
def to_record_list(x: Data | list[Data] | DataFrame) -> list[dict]: ...
def from_record_list(records: list[dict], shape_hint: type) -> Data | list[Data] | DataFrame: ...

# Type detection for the input type
class InputShape(Enum):
    DATA_SINGLE = "data_single"
    DATA_LIST = "data_list"
    DATAFRAME = "dataframe"

def detect_shape(x: Any) -> InputShape: ...
```

The two components delegate to these helpers. There are two execution paths per component (Data path vs DataFrame path). The DataFrame path uses pandas-native operations (`df.query`, `df.merge`, `df.drop_duplicates`) for performance. The Data path applies the predicate row-by-row in Python.

## Data flow (per component)

1. Detect input shape (`InputShape` enum).
2. Normalize to working representation (Data path: `list[dict]`. DataFrame path: keep as DataFrame).
3. Apply operation.
4. De-normalize back to the input shape.

## Error handling summary

| Condition | Behavior |
|---|---|
| Empty input(s) | Empty output, no error. |
| Field path missing on a record | Treated as null/missing. `is empty` is True; all comparisons False. |
| Invalid regex | Raise at build time. |
| `between` malformed | Raise at build time. |
| `Merge by key` without `join_keys` | Raise at build time. |
| Per-row type coercion failure (e.g., `gt` on a non-numeric field) | That row's predicate is False; the stream continues. |
| Mixed input types in CombineRecords | Coerce to DataFrame, emit DataFrame. |

## Component metadata

Both components:

- `version: int = 1`
- `changelog: ClassVar[list[ChangelogEntry]] = [ChangelogEntry(version=1, changes="Initial release.")]`
- `metadata = {"keywords": [...]}` for sidebar search:
  - FilterRecords keywords: `["filter", "records", "where", "conditions", "exclude", "include", "match", "predicate"]`
  - CombineRecords keywords: `["combine", "merge", "join", "union", "concatenate", "append", "dedupe"]`
- Neither carries `legacy=True` or `beta=True`.
- Icons: FilterRecords `icon = "filter"`; CombineRecords `icon = "git-merge"` (verify against the available icon set during implementation; fall back to `"merge"` or `"combine"` if unavailable).

## Testing

Under `src/lfx/tests/unit/components/processing/`:

### `test_filter_records.py`

Coverage matrix:

- Every operator × Data path × DataFrame path (14 × 2 = 28 happy-path cases at minimum).
- AND vs OR combinator with multiple conditions.
- `mode = "Keep matching"` and `mode = "Exclude matching"` — verify that matched/unmatched are correctly inverted.
- Missing field path → `is empty` True, comparisons False.
- Empty input → empty matched and unmatched.
- Empty conditions table:
  - With `Keep matching` → build-time error.
  - With `Exclude matching` → all records in `unmatched`.
- Type coercion edge cases: numeric op on a string field, regex on a non-string, `in` with whitespace.
- Build-time validation: invalid regex, malformed `between`.

### `test_combine_records.py`

Coverage matrix:

- Every mode × every input combination (Data+Data, DataFrame+DataFrame, Data+DataFrame, DataFrame+Data) — 3 × 4 = 12 cases at minimum.
- `Union (dedupe)`: with and without `dedupe_keys`; verify first-occurrence-wins.
- `Merge by key`: each `join_type` (inner/left/right/outer); single-key and multi-key joins; column-conflict suffix behavior.
- Empty inputs (left empty, right empty, both empty).
- Build-time validation: missing `join_keys`, nonexistent `dedupe_keys`.

### Standard tests

`tests/unit/custom/test_component_changelog.py` validates the version/changelog discipline. No special wiring needed — both components participate automatically.

## Out of scope (explicit)

- Renaming `DataOperationsComponent` to "Data Operations" or restructuring its operations.
- Deprecating `FilterDataComponent`, `FilterDataValuesComponent`, `SelectDataComponent`, `MergeDataComponent` — already legacy.
- Visual condition-builder UI (custom React component for nested AND/OR, drag-to-reorder).
- Grouped AND/OR.
- Interleave/zip combine mode.
- "Stop processing" / pipeline-halt semantics (Zapier-style "filter halts execution"). Langflow's model is data-flow, not workflow-halt; users wire the `unmatched` output to nothing if they want to drop those records.

## Open questions

- **Icon names** — `"git-merge"` may not exist in Langflow's icon set. Verify during implementation; pick the closest available.
- **`TableInput` operator dropdown column** — confirm `TableInput` supports a per-column dropdown type (vs free-text). If not, fall back to `StrInput` for `operator` and validate at build time. *(Implementation plan should resolve this before coding.)*
- **`HandleInput` with mixed `input_types` and `is_list`** — `DataOperationsComponent` uses `DataInput(is_list=True)`. We need `HandleInput(input_types=["Data", "DataFrame"], is_list=True)` to accept both shapes from one or many upstream connections. Verify this combination is supported by the connection-validation layer; if not, fall back to two separate inputs (one Data, one DataFrame) or drop `is_list` and require a pre-merged single input. *(Implementation plan should resolve this before coding.)*
