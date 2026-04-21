# Data Mapper — Phase 1b (UI Modal) Design

**Status:** Draft
**Date:** 2026-04-21
**Owner:** bryced
**Target branch:** `platform-multi-tenant`
**Supersedes:** the "Phase 1b — UI" section of `2026-04-21-data-mapper-component-design.md` (this doc is the authoritative spec for 1b)

## Purpose

Replace Phase 1a's raw-JSON `mapping_config` surface with a visual modal editor so flow authors who don't hand-write JSON can configure a Data Mapper. The engine, config schema, and component shell from Phase 1a stay unchanged — this is pure config-surface work: a new Langflow input type (`MappingInput`) renders a button-plus-summary on the node; clicking opens a row-per-destination table editor that reads/writes the same `MapperConfig` JSON.

## Scope

### In scope (Phase 1b)

- **New backend input type** `MappingInput` in `lfx.io`. Stores a JSON string (the same shape Phase 1a used); no value schema change.
- **New frontend input component** `MappingComponent` that renders as `Edit mapping · N fields` button + summary chip; opens the modal on click.
- **New modal** `DataMapperModal`: Option-B row-per-destination table (approved in brainstorm).
- **Schema source resolution** per input:
  - **Autodetect** (default): read the flow's cached vertex builds via existing `GET /api/v1/monitor/builds?flow_id={uuid}`; parse the upstream vertex's latest output `data` to produce `{fields: [...]}`. If no recent build exists, fall back to **static** introspection (the upstream component's declared `Output.types` and any known shape hints).
  - **Paste sample**: user pastes a representative JSON payload; fields are inferred client-side via a type-walk.
  - **JSON Schema**: user pastes a JSON Schema document; the single new backend endpoint parses it via the existing `lfx.schema.json_schema.create_input_schema_from_json_schema` utility and returns `{fields: [...]}`.
- **Join-key editor** for non-driver inputs: two dropdowns per key (`driver_field` / `lookup_field`), "Add another key" button for composite AND (no OR, no other operators).
- **Destination schema editor**: the target-shape side. Same three schema sources (autodetect from a downstream consumer, paste sample, JSON Schema). Manual row add/remove is available as an always-present affordance.
- **Row-per-destination mapping table** with columns: `Destination field`, `Type`, `Required`, `Transform` (dropdown: direct/template/expression/static/variable/array), `Source / Config` (inline editor that adapts to transform choice), `Default`.
- **Hard-gated save**: clicking Save calls the component backend's existing `update_build_config` / `_resolve_mapping_config` path via a lightweight validation endpoint; Pydantic errors are surfaced inline and block Save until clean. (May relax later per user direction.)
- **Extension slot for Phase 1c auto-mapping**: a single named `<ModalHeaderSlot id="suggestions" />` region in the modal header that renders nothing in 1b but exists for the assistant team to inject a "Suggest mappings" action.
- **Migration**: bump `DataMapperComponent.version` to `2`; replace the `CodeInput(name="mapping_config", language=...)` field with `MappingInput(name="mapping_config")`. The stored JSON string is unchanged, so existing Phase 1a flows keep working — only the renderer differs. Append a `ChangelogEntry` with `notes` explaining the UI upgrade.

### Non-goals (deferred)

- **Auto-mapping** (heuristic or LLM) — Phase 1c, lives in the component-assistant tool surface, not in this modal. Modal exposes only the extension slot.
- **OpenAPI / Swagger ingestion** — still deferred to Phase 2. (JSON Schema only in 1b.)
- **Inner / right / outer joins, OR conditions** — Phase 2 (join-type switcher).
- **One-to-many aggregation on join** — Phase 2.
- **`lookup` value-to-value transform** — Phase 2.
- **Soft-save** (allow save with errors + runtime warning) — can relax later if demand appears.
- **Live type-coercion preview** against an actual row of data — nice-to-have, out of scope for 1b.
- **Custom schema editing beyond add/remove rows** — users who want exotic nested shapes use paste-sample or JSON Schema.

## Architecture

```
┌─────────────────────────────┐         ┌──────────────────────────┐
│  Flow Builder canvas         │         │  Phase 1a engine         │
│  ┌──────────────────────┐    │         │  (unchanged)             │
│  │ DataMapperComponent   │    │         │                          │
│  │  ┌───────────────┐   │    │         │  _data_mapper/           │
│  │  │ MappingInput  │───┼────┼─opens──►│    config_schema.py      │
│  │  │ (button+chip) │   │    │         │    engine.py             │
│  │  └───────────────┘   │    │         │    join.py               │
│  └──────────────────────┘    │         │    transforms.py         │
└──────┬──────────────────────┘         └──────────────────────────┘
       │
       │ click
       ▼
┌─────────────────────────────┐         ┌──────────────────────────┐
│  DataMapperModal             │◄──fetch─│  GET /api/v1/monitor/    │
│  ┌────────────────────────┐  │         │      builds?flow_id=…    │
│  │ Per-input tabs:         │  │         │    (EXISTING endpoint;   │
│  │ [Autodetect|Sample|JSON]│  │         │     no change)           │
│  │ Join-key editor         │  │         └──────────────────────────┘
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │         ┌──────────────────────────┐
│  │ Destination table       │  │         │  POST /api/v1/utils/      │
│  │ per row: dest / type /  │  │◄──fetch─│    jsonschema-to-fields  │
│  │   req / transform /     │  │         │    (NEW endpoint)        │
│  │   inline config / default│  │         └──────────────────────────┘
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │         ┌──────────────────────────┐
│  │ Save button             │──POST───►│  POST /api/v1/utils/      │
│  └────────────────────────┘  │         │    validate-mapping-config│
└─────────────────────────────┘          │    (NEW, thin wrapper     │
                                          │     around MapperConfig   │
                                          │     Pydantic validator)   │
                                          └──────────────────────────┘
```

### Principle: modal is a view over the same data

The modal's internal state is a JSON object that conforms to `MapperConfig`. No new data model. Opening the modal reads the current string from the component's `mapping_config` field (JSON-parsing or starting from a blank template); closing with Save writes a stringified JSON back. The modal has no privileged path into the backend other than the two endpoints above.

## Backend changes

### 1. `MappingInput` input type

- New class in `src/lfx/src/lfx/inputs/inputs.py`, mirroring the `CodeInput` skeleton (inherits `BaseInputMixin` + `ListableInputMixin`; no `InputTraceMixin` since the mapping config is authoring-only, not a live trace value):

  ```python
  class MappingInput(BaseInputMixin, ListableInputMixin):
      field_type: SerializableFieldTypes = FieldTypes.MAPPING
  ```

- Add one enum entry `MAPPING = "mapping"` to the `FieldTypes` enum at `src/lfx/src/lfx/inputs/input_mixin.py:18`. (No separate `SerializableFieldTypes` enum exists — it's an `Annotated[FieldTypes, ...]` alias on line 44, so it picks up the new entry automatically.)
- Re-export `MappingInput` from `lfx.io` so components can write `from lfx.io import MappingInput`.
- **No** bespoke backend validation beyond what's already in Phase 1a — `DataMapperComponent._resolve_mapping_config` already runs the JSON through `MapperConfig.model_validate`.

### 2. Component migration

- `src/lfx/src/lfx/components/processing/data_mapper.py`:
  - Swap `CodeInput(name="mapping_config", ...)` → `MappingInput(name="mapping_config", ...)`.
  - Bump `version: int = 1` → `version: int = 2`.
  - Append a second `ChangelogEntry(version=2, changes="Config surface upgraded from raw JSON editor to visual modal.", notes="No action needed; existing saved configurations continue to parse.")`.

### 3. Validation endpoint

- New `POST /api/v1/utils/validate-mapping-config`:
  - Body: the MapperConfig JSON.
  - Calls `MapperConfig.model_validate(body)`.
  - Response always shaped `{errors: [...]}`. On success: `200 {errors: []}`. On `ValidationError`: `422 {errors: [{path: ["mappings", 3, "sources", 0, "input"], message: "unknown input 'jobs'"}, ...]}` — `path` is the Pydantic loc tuple as a list; `message` is the human-readable Pydantic message. This lets the modal attach errors to specific rows/fields without sniffing HTTP status.
- **Route location:** colocate with the existing `/api/v1/validate/code` handler. Confirm the concrete file at plan time (likely `src/backend/base/langflow/api/v1/validate.py` or `api/v1/endpoints.py`).
- Auth: requires authenticated user, no special permissions.

### 4. JSON-Schema-to-fields endpoint

- New `POST /api/v1/utils/jsonschema-to-fields`:
  - Body: a JSON Schema document (dict).
  - Uses `lfx.schema.json_schema.create_input_schema_from_json_schema(body)` to build a Pydantic model; walks `model_fields` to produce `{fields: [{name, type, required}, ...]}`.
  - Returns `200 {fields: [...]}`; `400` with a friendly error message on malformed schema.
- **Type mapping** (JSON Schema primitive → our `FieldType` enum): `string → str`, `integer → int`, `number → float`, `boolean → bool`, `array → list`, `object → dict`, `string + format:date → date`, `string + format:date-time → datetime`. Unknown types default to `str`.
- Route: same file as validate-mapping-config.

## Frontend changes

### 1. New input renderer

- **File:** `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`
- Renders:
  - A button: `Edit mapping · {count} field(s)` where count = number of destination rows in the current config (or `Configure mapping` if empty).
  - A chip beneath showing the selected driver input alias (or empty-state hint).
  - On click: dispatches a local state open event that mounts `DataMapperModal`.
- Dispatch wiring: add a new case `"MappingInput":` in the switch in `src/frontend/src/components/core/parameterRenderComponent/index.tsx` that returns `<MappingComponent {...baseInputProps} />`.

### 2. Modal

- **Directory:** `src/frontend/src/modals/dataMapperModal/`
- **Files:**
  - `index.tsx` — top-level component. Props: `open: boolean, value: string (JSON), onChange(newValue: string), onClose(), nodeId: string, flowId: string`.
  - `components/InputsPanel.tsx` — top bar: per-upstream-input (driver + lookups) tabs showing `Alias`, `Schema source` selector (Autodetect / Paste sample / JSON Schema), join-key editor.
  - `components/DestinationTable.tsx` — the main row-per-destination table.
  - `components/TransformCell.tsx` — renders the adaptive config editor in the `Source / Config` column based on the row's transform choice (direct = field picker, template = Jinja textarea, expression = code line, static = value input, variable = variable name, array = multi-source picker).
  - `components/JoinKeyEditor.tsx` — the compound-AND two-dropdown list.
  - `components/SchemaSourceTabs.tsx` — the three-mode selector + its per-mode content (paste JSON box, JSON Schema box, "run flow once" hint).
  - `hooks/useVertexBuildShapes.ts` — wraps the `/monitor/builds` query and extracts `{fields: [...]}` from the most recent build of each upstream vertex.
  - `hooks/useValidateMappingConfig.ts` — wraps the validate endpoint.
  - `hooks/useJsonSchemaToFields.ts` — wraps the jsonschema-to-fields endpoint.
  - `hooks/useInferSampleFields.ts` — **client-side only**; walks a JSON value and returns inferred `{fields: [...]}`. Not a network call.
  - `util/configBuilder.ts` — pure functions for mutating a `MapperConfig` draft (addRow, removeRow, setTransform, setSource, etc.) — kept pure so it's Jest-unit-testable.
- **State:** `useState<MapperConfigDraft>` at the modal root; subcomponents receive slices + dispatchers. A `react-query` hook wires validation — on Save click, call `validateMutation.mutateAsync(draft)`, block if errors, otherwise stringify and call `onChange`, then `onClose`.

### 3. Query hooks (React Query v5)

- **Files under** `src/frontend/src/controllers/API/queries/`:
  - `vertex/use-get-monitor-builds.ts` — if a hook for `GET /monitor/builds` doesn't already exist, add one (check first; it may be named `useGetTraces` or similar).
  - `utils/use-post-validate-mapping-config.ts`
  - `utils/use-post-jsonschema-to-fields.ts`
- **Note:** all hooks use React Query v5's `isPending` (not `isLoading`) per the project's known quirks.

### 4. Extension slot for Phase 1c

- The modal accepts an optional `suggestionsSlot?: React.ReactNode` prop; when rendered via the `MappingComponent` input renderer, that prop is left undefined. Phase 1c wires it to an assistant-driven suggestion component. The slot mounts in the modal header above the destination table. Document the seam and its expected props (`currentConfig`, `onApply(proposed: MapperConfig)`) in `src/frontend/src/modals/dataMapperModal/README.md`.

## User interaction flow (happy path)

1. User drags `Data Mapper` onto the canvas, connects two upstream inputs (e.g. a worker-list node and a jobs-details node).
2. User clicks the `Configure mapping` button on the node.
3. Modal opens. Both inputs' schema sources default to **Autodetect**. Modal queries `/monitor/builds?flow_id=…`:
   - If both upstream vertices have recent builds → fields are populated. Done.
   - If not → per-input "Run flow once to autodetect, or switch to Paste sample / JSON Schema" hint.
4. User designates input 0 as the driver (default: first connected input). For input 1, user sets join key: `driver.job_id = jobs.id`. "+ Add key" for composite if needed.
5. User defines the destination schema. Options: reuse the downstream consumer's shape (autodetect from the next-vertex input spec), paste sample, paste JSON Schema, or manually add rows.
6. For each destination field, user picks a transform and configures it. Inline validation flags unresolved sources or Jinja/expression parse errors.
7. User clicks Save. Modal calls `validate-mapping-config`. On success, modal closes, component field is updated with the new JSON. On failure, errors appear inline at their paths and Save stays disabled.

## Testing

### Backend

- `src/backend/tests/unit/api/test_mapping_config_endpoints.py`:
  - `validate-mapping-config` with a valid config → 204.
  - `validate-mapping-config` with bad JSON → 422 with structured error array.
  - `validate-mapping-config` with unknown transform type → 422 flagging the specific mapping path.
  - `jsonschema-to-fields` with a minimal `{type: "object", properties: {name: {type: "string"}}}` → returns `{fields: [{name: "name", type: "str", required: false}]}`.
  - `jsonschema-to-fields` with `$ref` chains → resolves correctly (reuses existing utility; smoke test only).
  - `jsonschema-to-fields` with malformed schema → 400.

### Frontend

- **Jest unit tests** under `src/frontend/tests/` for pure modules:
  - `configBuilder.ts`: addRow, removeRow, setTransform + adaptive config reset, setSource.
  - `useInferSampleFields.ts`: type walk for nested dict, list of dicts, primitives, nulls.
  - `TransformCell.tsx` rendering logic per transform type (snapshot-light render tests).
- **Playwright e2e** at `src/frontend/tests/core/unit/dataMapperModal.spec.ts`:
  - Open flow, add Data Mapper, configure a minimal 1-input/2-field mapping, save, verify the component's serialized value matches expected JSON.
  - Save-blocked state when a required destination has no mapping.

## Phase 1a ↔ Phase 1b compatibility

- The saved value in `mapping_config` is the same JSON shape, so **flows saved under Phase 1a continue to work**.
- The frontend component change is renderer-only: Phase 1a flows opened in Phase 1b see the modal instead of the raw JSON editor, pre-populated from their existing config.
- If a user saved an invalid config under Phase 1a (e.g. by editing raw JSON), opening the modal in 1b surfaces the Pydantic errors at open-time; user must fix before save.

## Risks

- **Autodetect fidelity**: upstream vertex build outputs are serialized records; extracting a reliable field list requires knowing the output schema (often just a dict of kwargs, some of which contain the actual payload). Mitigation: heuristic walk + paste-sample fallback + clear "autodetect couldn't parse this — paste a sample" hint.
- **Modal performance with 100+ fields**: row-per-destination table scaled to 100+ rows can slow on slower machines. Mitigation: virtualized list; defer to plan time if profiling shows an issue.
- **Component version bump migration**: 1a flows have `version: 1`. Langflow's "Update components" modal will prompt users to upgrade. Mitigation: the changelog note says "no action required"; runtime behavior is unchanged.

## Open questions

None blocking.

- Whether the validation endpoint should be authenticated-only or accept anonymous (if public endpoint exists for similar tools). Default: authenticated.
- Whether to expose the same validation endpoint publicly as an SDK helper for API users. Defer.
