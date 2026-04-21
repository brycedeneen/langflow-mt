# Data Mapper Component — Design

**Status:** Draft
**Date:** 2026-04-21
**Owner:** bryced
**Target branch:** `platform-multi-tenant`

## Purpose

Deterministic, record-level field mapping as a Langflow component. Takes 1..N upstream inputs, left-joins them on declared keys, runs per-destination-field transforms, and emits `Data` / `DataFrame` / `Message` / `JSON` via one polymorphic output pin.

Solves the ETL-alignment use case (e.g. "ADP workers joined to a job-details lookup, reshaped into a Salesforce-shaped record") without forcing flow authors to write a Custom Component.

## Scope

### In scope (Phase 1)

- Multi-input handle (`HandleInput(is_list=True)`) accepting any number of upstream connections.
- Each input treated as `record | list[record]` (single record is a 1-element list internally).
- One designated **driver** input; other inputs are **lookups** with one or more join-key field pairs (composite `AND`-joined keys; no `OR`).
- **Left-join semantics only:** every driver row produces exactly one output row; unmatched lookup → destination fields using that lookup resolve to per-field defaults.
- **First-match-wins** on duplicate lookup keys; collision count logged as a warning.
- Six transform types: `direct`, `template` (Jinja2), `expression` (restricted single-line Python via `asteval`), `static`, `variable` (Langflow variable store), `array` (pack sources into a list). `array` corresponds to the "Inline mapping" box in the initial sketch.
- Per-destination-field `required` flag and `default` value. Missing + optional → per-field `default` (type-blank by default: `str→""`, `list→[]`, `dict→{}`, `bool→false`, numeric/date/datetime→`null`).
- **Schema sources** for field discovery: autodetect from connected upstream → paste-sample JSON fallback → JSON Schema upload fallback. UI in Phase 1b; backend accepts the resolved field list either way.
- Output type selector (`TabInput`): `Auto` / `Data` / `DataFrame` / `Message` / `JSON`. `Auto` = `DataFrame` when driver is a list, `Data` when single record. Pin filtering via `update_outputs`.

### Non-goals (deferred to Phase 2)

- Inner/right/outer/cross joins; `OR` in join conditions; arbitrary boolean gates.
- One-to-many aggregation on joins (only first-match-wins in v1).
- A second "complex transform editor" modal for multi-step per-field logic.
- Full Python function bodies in `expression` cells (restricted single-line only).
- OpenAPI / Swagger schema ingestion (JSON Schema only in v1).
- Value-to-value lookup-table transform (source value `US` → `Americas`, etc.); `static` + `expression` with `asteval`'s `dict.get` cover the narrow cases until real demand appears.
- Per-row upstream invocation ("for each worker, call the jobs API"); upstream must already be materialized.
- Streaming or chunked outputs; the mapper runs on fully-materialized inputs.

## Component anatomy

**Class:** `DataMapperComponent` at `src/lfx/src/lfx/components/processing/data_mapper.py`.

**Inputs on the node:**

| Name | Type | Notes |
|---|---|---|
| `inputs` | `HandleInput(is_list=True, input_types=["Data","DataFrame","Message","JSON"])` | N upstream connections |
| `mapping_config` | `CodeInput(language="json")` in Phase 1a; replaced by `MappingInput` in Phase 1b | stores the mapping-config JSON |
| `output_type` | `TabInput(options=["Auto","Data","DataFrame","Message","JSON"], value="Auto")` | drives `update_outputs` |

**Outputs:** four `Output` declarations (one per concrete type); `update_outputs` hides all but the selected pin. Same pattern as `TypeConverterComponent` in `src/lfx/src/lfx/components/processing/converter.py`.

**Node UX:** compact — two visible fields (mapping button + output-type tabs). All mapping complexity lives in the modal (Phase 1b) or the raw JSON (Phase 1a).

## Mapping config data model

Stored in `mapping_config` as JSON. Validated against Pydantic models in `_data_mapper/config_schema.py` on `update_build_config`.

```yaml
driver_index: 0                  # which entry in `inputs` is the driver
inputs:
  - alias: workers
    schema_source: autodetect    # autodetect | sample | jsonschema
    schema:
      fields:
        - { name: user_id, type: str, required: true }
        - { name: job_id,  type: str, required: false }
    # no `join` block = this is the driver
  - alias: jobs
    schema_source: jsonschema
    jsonschema: { ... }          # populated only when schema_source != autodetect
    schema: { fields: [...] }
    join:
      on:                        # composite AND keys; no OR
        - { driver_field: job_id, lookup_field: id }
        - { driver_field: org_id, lookup_field: org_id }
destination_schema:
  - { name: External_ID, type: str,  required: true,  default: null }
  - { name: Name,        type: str,  required: false, default: "" }
  - { name: Region,      type: str,  required: false, default: "" }
  - { name: Invoices,    type: list, required: false, default: [] }
mappings:
  - { destination: External_ID, transform: direct,
      sources: [{ input: workers, field: user_id }] }
  - { destination: Name, transform: template,
      sources: [{ input: workers, field: first_name },
                { input: workers, field: last_name }],
      config: { template: "{{ first_name }} {{ last_name }}" } }
  - { destination: Region, transform: static,
      sources: [], config: { value: "EMEA" } }
  - { destination: Updated_At, transform: variable,
      sources: [], config: { variable: current_timestamp } }
  - { destination: Invoices, transform: array,
      sources: [{ input: workers, field: invoice_1 },
                { input: workers, field: invoice_2 },
                { input: workers, field: invoice_3 }],
      config: { skip_missing: true } }
```

## Execution engine

```
1. Materialize each input as list[dict].
   Single record -> 1-element list.

2. For each non-driver input, build a lookup index:
     key_tuple = tuple(row[k.lookup_field] for k in join.on)
     lookup_index[alias][key_tuple] = row     # first match wins; later duplicates counted
   Log one WARNING per alias with duplicates: "lookup <alias> had N duplicate key(s)".

3. For each driver_row in driver input:
     ctx = { driver_alias: driver_row }
     for each lookup alias:
        key_tuple = tuple(driver_row[k.driver_field] for k in join.on)
        ctx[alias] = lookup_index[alias].get(key_tuple)   # None if unmatched
     for each dest_field in destination_schema:
        raw = evaluate(mapping[dest_field], ctx)          # may return _MISSING
        value = resolve_missing(raw, dest_field)          # required/default logic
        value = coerce(value, dest_field.type)            # best-effort, warn on failure
        output_row[dest_field.name] = value
     emit output_row

4. Package output list per `output_type` tab selection (Auto inferred from driver shape).
```

### Missing vs null

`_MISSING` is a sentinel distinct from an explicit `None` from source data. This matters for `required`/`default` logic:

- `required: true` + `_MISSING` → logged row-level error; row still emitted with field set to `default` (or type-blank if `default` is null). Total error count surfaced on the node status.
- `required: false` + `_MISSING` → per-field `default`. Type-blank defaults: `str→""`, `list→[]`, `dict→{}`, `bool→false`, numeric/date/datetime→`null`.

### Expression / template context model

- Driver input fields are **top-level names** in the context: `first_name`, `last_name`.
- Lookup inputs are **namespaced** by alias, dot-accessible via `types.SimpleNamespace` wrapper: `jobs.title`, `jobs.salary * 1.1`.
- Unmatched lookups expose `None`; templates render as `""`, expressions see `None`.

### Transform catalog

| Type | `sources` | `config` | Evaluator |
|---|---|---|---|
| `direct` | 1 field | `{}` | `ctx[input][field]`; `_MISSING` if key absent |
| `template` | 0..N (documentary) | `{template: str}` | Jinja2 render with flattened ctx; undefined → `""` |
| `expression` | 0..N (documentary) | `{expression: str}` | `asteval.Interpreter` with flat ctx; no `import`, no `__dunder__`, no statements/defs; arithmetic, boolean, comparisons, comprehensions, literal containers allowed |
| `static` | 0 | `{value: any}` | returns verbatim |
| `variable` | 0 | `{variable: str}` | resolved via `VariableService`; covers both Langflow-global env vars and per-flow runtime variables; `_MISSING` if unknown |
| `array` | 0..N | `{skip_missing: bool}` | list comprehension; filters `_MISSING` if `skip_missing`, else substitutes the per-field blank |

`template` and `expression` are split types in the UI because they have different safety envelopes and different evaluators (Jinja vs `asteval`). The user picks one via the transform dropdown.

**Why `asteval`:** Python-expression subset, no AST rewriting, whitelist-based, actively maintained. Compiled once per mapping, reused per row.

## Phase 1a — backend slice

### Code layout

- `src/lfx/src/lfx/components/processing/data_mapper.py` — `DataMapperComponent` shell.
- `src/lfx/src/lfx/components/processing/_data_mapper/__init__.py` — re-exports.
- `src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py` — Pydantic models for the mapping-config JSON.
- `src/lfx/src/lfx/components/processing/_data_mapper/engine.py` — `run(config: dict, inputs: list) -> list[dict]`.
- `src/lfx/src/lfx/components/processing/_data_mapper/transforms.py` — the six evaluators behind a dispatch function.
- `src/lfx/src/lfx/components/processing/_data_mapper/join.py` — composite-key index builder; collision counter.
- Version `1.0.0`; new entry appended to the `processing` changelog per the `langflow-component-authoring` ritual.

### Phase 1a config surface

Users edit the mapping via a raw JSON `CodeInput(language="json")` field. `update_build_config` runs the JSON through `config_schema`'s Pydantic validator and surfaces typed errors. Paste-sample and JSON-Schema upload surfaces are UI-layer constructs deferred to 1b; they produce the same config JSON at the boundary.

## Phase 1b — UI

### Backend additions

- `GET /api/v1/flows/{flow_id}/nodes/{node_id}/input-shapes` — returns `{alias: {fields: [...]} | null}` per connected upstream, derived from the cached execution trace. `null` means "no recent run"; the modal prompts the user to run upstream once or fall back to paste-sample / JSON-Schema.
- `POST /api/v1/utils/infer-schema` — stateless: takes a JSON sample, returns a `{fields: [...]}` list using a simple type-inference walk.
- JSON-Schema uploads route through existing `lfx.schema.json_schema.create_input_schema_from_json_schema`; `.model_fields` is walked to produce the same `{fields: [...]}` shape.

### Frontend

- New input type: `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`. Renders as `Edit mapping · N fields` button + summary chip; clicking opens the modal.
- New modal: `src/frontend/src/modals/dataMapperModal/`. Option B (row-per-destination table) from the brainstorm mockup:
  - Top bar — per-input: alias label, schema-source tab (Autodetect / Paste sample / JSON Schema), join-key editor (only for non-driver inputs).
  - Main region — destination table: one row per destination field (name, type, required, transform dropdown, inline config cell). Unmapped destinations highlighted.
  - Inline validation (Jinja parse, expression AST check, missing join keys, unresolved sources); Save disabled until resolved.
- Jest tests (not Vitest; project uses Jest per the frontend-test-stack memo).

## Testing

**Backend (Phase 1a):**

- `src/lfx/tests/unit/components/processing/test_data_mapper_engine.py` — pure engine tests against JSON fixtures. Parametrized across each transform type, composite-key join, first-match-wins, single-record driver, missing-field (required/optional × every default type), type-coercion edge cases.
- `src/lfx/tests/unit/components/processing/test_data_mapper_component.py` — component-level: build lifecycle, output polymorphism via `update_outputs`, `update_build_config` validation error surfacing.

**Backend (Phase 1b):**

- `src/backend/tests/unit/test_data_mapper_autodetect.py` — `input-shapes` endpoint + `infer-schema` utility.

**Frontend (Phase 1b):**

- Jest tests for the modal: table rendering, transform picker state, validation surfacing, save flow, schema-source tab switching.

**End-to-end sanity:** the existing `ADP Worker Sync to SFTP` starter flow is an ideal real-world test bed once 1b lands.

## Dependencies and risk

- **New dep:** `asteval` in `src/lfx/pyproject.toml`. Check for transitive presence first; if absent, add as a direct runtime dep. Actively maintained; widely used in scientific Python data pipelines.
- **No DB migration.** Config is embedded in the flow JSON like any other component field.
- **No breaking changes.** Net-new component only.
- **Risk — autodetect correctness.** Mitigated by paste-sample and JSON-Schema fallbacks; autodetect is best-effort, never the only option.
- **Risk — per-row performance.** 10k rows × 10 destination fields × compiled-once evaluators should be comfortably fast; profile during Phase 1a unit tests and document a ceiling.
- **Risk — `asteval` expressiveness mismatch.** If real users need constructs `asteval` doesn't support (e.g. `.strftime()` on datetimes), extend the whitelist rather than swap engines.

## Open questions

None blocking the plan. Small implementation-time calls acknowledged here so they're not surprises:

- Exact `asteval` whitelist: start with the library default; extend only when a real user case demands it.
- Numeric-type blank default is `null` (not `0`); revisit only on user feedback.
