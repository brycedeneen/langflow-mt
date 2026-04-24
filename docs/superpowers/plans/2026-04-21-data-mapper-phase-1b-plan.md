# Data Mapper — Phase 1b (UI Modal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Phase 1a's raw-JSON `mapping_config` surface with a visual modal (row-per-destination table + schema-source tabs per input + compound join-key editor). Backend changes are minimal (one new input type, two new endpoints, one component migration); the work is mostly frontend React.

**Architecture:** `MappingInput` (new backend input type) renders in the frontend via a new case in `parameterRenderComponent/index.tsx` → `MappingComponent` (button + chip) → clicking opens `DataMapperModal`. Modal state is a `MapperConfig` draft JSON; subcomponents (schema-source tabs, join-key editor, destination table, transform cell) mutate slices through pure functions in `configBuilder.ts`. Save calls a new `validate-mapping-config` endpoint; modal stays open with inline errors until clean. Autodetect consumes the existing `GET /monitor/builds`; JSON Schema uploads go through a new `jsonschema-to-fields` endpoint that wraps the existing `lfx.schema.json_schema` utility.

**Tech Stack:** Python 3.11 backend (FastAPI + Pydantic), React + TypeScript frontend, React Query v5 (`isPending` not `isLoading`), Jest for frontend unit tests, Playwright for modal e2e. Component-authoring ritual: version bump 1 → 2 + changelog entry.

**Source spec:** `docs/superpowers/specs/2026-04-21-data-mapper-phase-1b-design.md`
**Prerequisite:** Phase 1a is shipped (commit `7384f699`).

---

## File structure

### Backend — new

| File | Responsibility |
|---|---|
| `src/lfx/src/lfx/inputs/inputs.py` (modify) | Add `MappingInput` class |
| `src/lfx/src/lfx/inputs/input_mixin.py` (modify) | Add `MAPPING = "mapping"` to `FieldTypes` |
| `src/lfx/src/lfx/io/__init__.py` (modify) | Re-export `MappingInput` |
| `src/lfx/src/lfx/components/processing/data_mapper.py` (modify) | Swap `CodeInput` → `MappingInput`, bump version, append ChangelogEntry |
| `src/backend/base/langflow/api/v1/<validate-file>.py` (modify, exact file resolved at plan time) | New `POST /api/v1/utils/validate-mapping-config` and `POST /api/v1/utils/jsonschema-to-fields` routes |
| `src/backend/tests/unit/api/test_mapping_config_endpoints.py` (new) | Backend endpoint tests |

### Frontend — new

| File | Responsibility |
|---|---|
| `src/frontend/src/modals/dataMapperModal/index.tsx` | Modal top-level component |
| `src/frontend/src/modals/dataMapperModal/README.md` | Documents the `suggestionsSlot` extension seam |
| `src/frontend/src/modals/dataMapperModal/types.ts` | TS types mirroring `MapperConfig` |
| `src/frontend/src/modals/dataMapperModal/util/configBuilder.ts` | Pure draft-mutation functions (addRow, setTransform, etc.) |
| `src/frontend/src/modals/dataMapperModal/util/inferSampleFields.ts` | Client-side JSON-sample → fields walk |
| `src/frontend/src/modals/dataMapperModal/hooks/useVertexBuildShapes.ts` | Derives `{fields: [...]}` per upstream vertex from `/monitor/builds` |
| `src/frontend/src/modals/dataMapperModal/components/InputsPanel.tsx` | Per-input top-bar (alias, schema source tabs, join-key editor) |
| `src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx` | Row-per-destination table |
| `src/frontend/src/modals/dataMapperModal/components/TransformCell.tsx` | Adaptive config cell per transform type |
| `src/frontend/src/modals/dataMapperModal/components/JoinKeyEditor.tsx` | Compound-AND two-dropdown list |
| `src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx` | Autodetect / Paste sample / JSON Schema selector |
| `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx` | New input renderer (button + chip that opens the modal) |
| `src/frontend/src/components/core/parameterRenderComponent/index.tsx` (modify) | Add `"MappingInput"` case in switch |
| `src/frontend/src/controllers/API/queries/utils/use-post-validate-mapping-config.ts` | New mutation hook |
| `src/frontend/src/controllers/API/queries/utils/use-post-jsonschema-to-fields.ts` | New mutation hook |
| `src/frontend/tests/unit/dataMapperModal/configBuilder.test.ts` | Jest tests for pure mutators |
| `src/frontend/tests/unit/dataMapperModal/inferSampleFields.test.ts` | Jest tests for type walk |
| `src/frontend/tests/unit/dataMapperModal/TransformCell.test.tsx` | Jest render tests for the adaptive cell |
| `src/frontend/tests/core/unit/dataMapperModal.spec.ts` | Playwright e2e |

### Regenerated

| File | Why |
|---|---|
| `src/lfx/src/lfx/_assets/component_index.json` | `DataMapperComponent.version` change 1 → 2 invalidates the cached entry |

---

## Commands used throughout

- **Run lfx unit tests:** `cd src/lfx && uv run pytest tests/unit/... -v`
- **Run langflow backend unit tests:** `cd src/backend && uv run pytest tests/unit/... -v`
- **Run changelog suite (required after version bump):** `cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v`
- **Frontend Jest:** `cd src/frontend && npm run test -- <pathglob>` (check `src/frontend/package.json` for the canonical script name).
- **Frontend Playwright:** `cd src/frontend && npx playwright test tests/core/unit/dataMapperModal.spec.ts`
- **Rebuild component index:** `uv run python scripts/build_component_index.py`
- **Dev-mode server:** `LFX_DEV=1 make run_cli`

---

## Task 1: Add `MAPPING` enum entry and `MappingInput` class

**Files:**
- Modify: `src/lfx/src/lfx/inputs/input_mixin.py:18` (FieldTypes enum)
- Modify: `src/lfx/src/lfx/inputs/inputs.py` (new class)
- Modify: `src/lfx/src/lfx/io/__init__.py` (re-export)
- Test: `src/lfx/tests/unit/inputs/test_mapping_input.py` (new)

- [x] **Step 1: Failing tests**

Create `src/lfx/tests/unit/inputs/test_mapping_input.py`:

```python
import pytest

from lfx.inputs import inputs as inputs_module
from lfx.inputs.input_mixin import FieldTypes


def test_field_types_has_mapping_entry():
    assert FieldTypes.MAPPING.value == "mapping"


def test_mapping_input_class_exists_and_has_correct_field_type():
    cls = inputs_module.MappingInput
    instance = cls(name="mapping_config", display_name="Mapping Config")
    assert instance.field_type == FieldTypes.MAPPING


def test_mapping_input_is_reexported_from_lfx_io():
    from lfx.io import MappingInput as ReexportedMappingInput
    assert ReexportedMappingInput is inputs_module.MappingInput
```

- [x] **Step 2: Verify failure**

```bash
cd src/lfx && uv run pytest tests/unit/inputs/test_mapping_input.py -v
```

Expected: FAIL — `AttributeError: MAPPING` (or `MappingInput` not found).

- [x] **Step 3: Implement**

In `src/lfx/src/lfx/inputs/input_mixin.py:18` (FieldTypes enum), add the new entry alphabetically (kept with existing string-enum pattern):

```python
    MAPPING = "mapping"
```

In `src/lfx/src/lfx/inputs/inputs.py`, find the `CodeInput` class and add a sibling:

```python
class MappingInput(BaseInputMixin, ListableInputMixin):
    """Data Mapper mapping-config input.

    Stores a JSON string describing source-to-destination field mappings.
    Rendered by the frontend as a button + modal editor; the backend treats
    the value opaquely (validation lives in DataMapperComponent, not here).
    """
    field_type: SerializableFieldTypes = FieldTypes.MAPPING
```

Mixin imports follow whatever pattern `CodeInput` uses — likely already in scope at the top of `inputs.py`.

In `src/lfx/src/lfx/io/__init__.py`, find the existing `CodeInput` re-export and add `MappingInput` in the same place (both the `from lfx.inputs.inputs import ...` block and the `__all__` list, alphabetical).

- [x] **Step 4: Verify passes**

```bash
cd src/lfx && uv run pytest tests/unit/inputs/test_mapping_input.py -v
```

Expected: all 3 PASS.

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/inputs/input_mixin.py \
        src/lfx/src/lfx/inputs/inputs.py \
        src/lfx/src/lfx/io/__init__.py \
        src/lfx/tests/unit/inputs/test_mapping_input.py
git commit -m "feat(lfx/inputs): add MappingInput input type for Data Mapper modal"
```

HEREDOC + Co-Authored-By trailer.

---

## Task 2: Migrate `DataMapperComponent` to `MappingInput` (version bump 1→2)

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/data_mapper.py`
- Modify: `src/lfx/tests/unit/components/processing/test_data_mapper_component.py`

- [x] **Step 1: Append failing assertions to the component tests**

Add three tests to `test_data_mapper_component.py`:

```python
def test_component_uses_mapping_input_for_mapping_config():
    mapping_input = next(i for i in DataMapperComponent.inputs if i.name == "mapping_config")
    from lfx.io import MappingInput
    assert isinstance(mapping_input, MappingInput)


def test_component_version_is_2_for_phase_1b():
    assert DataMapperComponent.version == 2


def test_component_changelog_has_two_entries():
    assert len(DataMapperComponent.changelog) == 2
    assert DataMapperComponent.changelog[-1].version == 2
    assert DataMapperComponent.changelog[-1].notes is not None
```

- [x] **Step 2: Verify failure**

```bash
cd src/lfx && uv run pytest tests/unit/components/processing/test_data_mapper_component.py -v
```

Expected: the three new assertions FAIL (still using `CodeInput`; `version == 1`; one-entry changelog).

- [x] **Step 3: Implement the migration**

In `src/lfx/src/lfx/components/processing/data_mapper.py`:

1. Change the import: `from lfx.io import CodeInput, DropdownInput, HandleInput, Output` → `from lfx.io import DropdownInput, HandleInput, MappingInput, Output` (drop `CodeInput`, add `MappingInput`, keep alphabetical).
2. In `DataMapperComponent.inputs`, swap the `mapping_config` entry:
   ```python
       MappingInput(
           name="mapping_config",
           display_name="Mapping Config",
           info=(
               "Visual mapping editor. Describes inputs, join keys, destination schema, "
               "and per-field transforms."
           ),
           required=True,
       ),
   ```
3. Bump `version: int = 1` → `version: int = 2`.
4. Extend the `changelog` class attribute:
   ```python
   changelog: ClassVar[list[ChangelogEntry]] = [
       ChangelogEntry(version=1, changes="Initial release."),
       ChangelogEntry(
           version=2,
           changes="Config surface upgraded from raw JSON editor to visual modal.",
           notes="No action needed; existing saved configurations continue to parse.",
       ),
   ]
   ```

- [x] **Step 4: Verify**

```bash
cd src/lfx && uv run pytest tests/unit/components/processing/test_data_mapper_component.py -v
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v
```

Both suites must pass.

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/processing/data_mapper.py \
        src/lfx/tests/unit/components/processing/test_data_mapper_component.py
git commit -m "feat(lfx/data_mapper): migrate mapping_config to MappingInput (v2)"
```

---

## Task 3: Backend endpoint — `POST /api/v1/utils/validate-mapping-config`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/<validate-file>.py` (find at plan time — the file containing the existing `/validate/code` handler)
- Create: `src/backend/tests/unit/api/test_mapping_config_endpoints.py`

- [x] **Step 1: Locate the sibling endpoint**

```bash
grep -rn "validate.*code\|/validate/code" /Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v1/ | head -5
```

Open the file(s) mentioned and confirm which hosts the existing code-validation route — new endpoint colocates there. Common location: `validate.py` or `endpoints.py`.

- [x] **Step 2: Failing test**

Create `src/backend/tests/unit/api/test_mapping_config_endpoints.py`:

```python
import pytest
from httpx import AsyncClient


VALID_CFG = {
    "driver_index": 0,
    "inputs": [
        {
            "alias": "workers",
            "schema_source": "autodetect",
            "schema": {"fields": [{"name": "user_id", "type": "str", "required": True}]},
        }
    ],
    "destination_schema": [
        {"name": "External_ID", "type": "str", "required": True, "default": None},
    ],
    "mappings": [
        {
            "destination": "External_ID",
            "transform": "direct",
            "sources": [{"input": "workers", "field": "user_id"}],
        }
    ],
}


@pytest.mark.asyncio
async def test_validate_mapping_config_valid_returns_empty_errors(client: AsyncClient, logged_in_headers):
    r = await client.post(
        "/api/v1/utils/validate-mapping-config",
        json=VALID_CFG,
        headers=logged_in_headers,
    )
    assert r.status_code == 200
    assert r.json() == {"errors": []}


@pytest.mark.asyncio
async def test_validate_mapping_config_unknown_transform_returns_422(client: AsyncClient, logged_in_headers):
    cfg = {**VALID_CFG, "mappings": [{**VALID_CFG["mappings"][0], "transform": "bogus"}]}
    r = await client.post(
        "/api/v1/utils/validate-mapping-config",
        json=cfg,
        headers=logged_in_headers,
    )
    assert r.status_code == 422
    body = r.json()
    assert len(body["errors"]) >= 1
    assert body["errors"][0]["path"][0] == "mappings"
    assert "transform" in " ".join(str(x) for x in body["errors"][0]["path"]) or "bogus" in body["errors"][0]["message"]


@pytest.mark.asyncio
async def test_validate_mapping_config_missing_required_dest_returns_422(client: AsyncClient, logged_in_headers):
    cfg = {
        **VALID_CFG,
        "destination_schema": [
            {"name": "External_ID", "type": "str", "required": True, "default": None},
            {"name": "Email", "type": "str", "required": True, "default": None},
        ],
        # Only External_ID mapped; Email unmapped and required
        "mappings": VALID_CFG["mappings"],
    }
    r = await client.post(
        "/api/v1/utils/validate-mapping-config",
        json=cfg,
        headers=logged_in_headers,
    )
    assert r.status_code == 422
    assert any("Email" in e["message"] for e in r.json()["errors"])


@pytest.mark.asyncio
async def test_validate_mapping_config_requires_auth(client: AsyncClient):
    r = await client.post("/api/v1/utils/validate-mapping-config", json=VALID_CFG)
    assert r.status_code == 401
```

Note: adjust the `client` / `logged_in_headers` fixture names to match whatever the backend test suite uses (grep existing endpoint tests in `src/backend/tests/unit/api/` for the pattern).

- [x] **Step 3: Verify failure**

```bash
cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py -v
```

Expected: 4 tests FAIL with 404.

- [x] **Step 4: Implement the endpoint**

Inside the validate file identified in Step 1, append:

```python
from pydantic import ValidationError

from lfx.components.processing._data_mapper import MapperConfig


@router.post("/utils/validate-mapping-config")
async def validate_mapping_config(
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    """Validate a Data Mapper mapping_config blob against the Pydantic schema.

    Returns {errors: []} on success (200) or {errors: [...]} on failure (422).
    Each error is {path: [...], message: str} so the modal can attach to a row.
    """
    try:
        MapperConfig.model_validate(body)
    except ValidationError as e:
        errors = [
            {"path": list(err["loc"]), "message": err["msg"]}
            for err in e.errors()
        ]
        raise HTTPException(status_code=422, detail={"errors": errors})
    return {"errors": []}
```

Imports likely already in scope (`router`, `HTTPException`, `Depends`, `User`, `get_current_active_user`). Follow whatever prefix/tag convention the neighbour routes use.

Implementation notes:
- `raise HTTPException(status_code=422, detail={"errors": [...]})` — FastAPI serializes `detail` as the response body, but clients often receive `{"detail": {"errors": [...]}}`. Verify against the failing-test expected shape; if the client strips the wrapper, unpack accordingly. Alternative: return a `JSONResponse(status_code=422, content={"errors": [...]})` to control the shape precisely.
- The 4xx-vs-envelope choice must match the test expectations. Reconcile before calling DONE.

- [x] **Step 5: Verify passes**

```bash
cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py -v
```

All 4 tests PASS.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/<validate-file>.py \
        src/backend/tests/unit/api/test_mapping_config_endpoints.py
git commit -m "feat(api): POST /utils/validate-mapping-config for Data Mapper modal"
```

---

## Task 4: Backend endpoint — `POST /api/v1/utils/jsonschema-to-fields`

**Files:**
- Modify: same file as Task 3
- Modify: same test file as Task 3 (append tests)

- [x] **Step 1: Append failing tests**

Add to `test_mapping_config_endpoints.py`:

```python
@pytest.mark.asyncio
async def test_jsonschema_to_fields_basic_object(client: AsyncClient, logged_in_headers):
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "active": {"type": "boolean"},
        },
        "required": ["name"],
    }
    r = await client.post(
        "/api/v1/utils/jsonschema-to-fields",
        json=schema,
        headers=logged_in_headers,
    )
    assert r.status_code == 200
    by_name = {f["name"]: f for f in r.json()["fields"]}
    assert by_name["name"]["type"] == "str"
    assert by_name["name"]["required"] is True
    assert by_name["age"]["type"] == "int"
    assert by_name["age"]["required"] is False
    assert by_name["active"]["type"] == "bool"


@pytest.mark.asyncio
async def test_jsonschema_to_fields_datetime_format(client: AsyncClient, logged_in_headers):
    schema = {
        "type": "object",
        "properties": {
            "updated_at": {"type": "string", "format": "date-time"},
            "created_on": {"type": "string", "format": "date"},
        },
    }
    r = await client.post(
        "/api/v1/utils/jsonschema-to-fields",
        json=schema,
        headers=logged_in_headers,
    )
    assert r.status_code == 200
    by_name = {f["name"]: f for f in r.json()["fields"]}
    assert by_name["updated_at"]["type"] == "datetime"
    assert by_name["created_on"]["type"] == "date"


@pytest.mark.asyncio
async def test_jsonschema_to_fields_malformed_returns_400(client: AsyncClient, logged_in_headers):
    r = await client.post(
        "/api/v1/utils/jsonschema-to-fields",
        json={"not_a_real_schema": 42},
        headers=logged_in_headers,
    )
    # create_input_schema_from_json_schema may either raise or produce an empty
    # schema. If it produces `fields: []`, change this test to expect 200 with
    # empty fields — but 400 is preferred so the modal surfaces the error.
    assert r.status_code in (400, 200)
    if r.status_code == 200:
        assert r.json() == {"fields": []}
```

- [x] **Step 2: Verify failure**

```bash
cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py::test_jsonschema_to_fields_basic_object -v
```

Expected: 404.

- [x] **Step 3: Implement**

Append to the same file as Task 3:

```python
from lfx.schema.json_schema import create_input_schema_from_json_schema


_JSON_SCHEMA_FIELD_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}


def _infer_field_type(prop: dict) -> str:
    """Map a single JSON Schema property dict to our FieldType string."""
    fmt = prop.get("format")
    if prop.get("type") == "string" and fmt == "date-time":
        return "datetime"
    if prop.get("type") == "string" and fmt == "date":
        return "date"
    return _JSON_SCHEMA_FIELD_TYPE_MAP.get(prop.get("type", "string"), "str")


@router.post("/utils/jsonschema-to-fields")
async def jsonschema_to_fields(
    schema: dict,
    current_user: User = Depends(get_current_active_user),
):
    """Convert a JSON Schema document into a flat `{fields: [...]}` list.

    Uses `lfx.schema.json_schema.create_input_schema_from_json_schema` to resolve
    $refs and nested $defs, then walks the top-level properties.
    """
    try:
        # The helper is used here mostly for $ref resolution; we still walk the
        # input schema directly to produce a flat field list, since nested
        # objects collapse to type="dict".
        create_input_schema_from_json_schema(schema)  # validates the shape
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON Schema: {e}") from e

    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields = [
        {
            "name": name,
            "type": _infer_field_type(prop),
            "required": name in required,
        }
        for name, prop in properties.items()
    ]
    return {"fields": fields}
```

- [x] **Step 4: Verify**

```bash
cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py -v
```

All 7 tests PASS (4 from Task 3 + 3 new).

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/<validate-file>.py \
        src/backend/tests/unit/api/test_mapping_config_endpoints.py
git commit -m "feat(api): POST /utils/jsonschema-to-fields for Data Mapper modal"
```

---

## Task 5: Frontend query hooks for the two new endpoints + monitor-builds

**Files:**
- Create: `src/frontend/src/controllers/API/queries/utils/use-post-validate-mapping-config.ts`
- Create: `src/frontend/src/controllers/API/queries/utils/use-post-jsonschema-to-fields.ts`
- Possibly create or reuse: `src/frontend/src/controllers/API/queries/monitor/use-get-monitor-builds.ts`

- [x] **Step 1: Check for an existing monitor-builds hook**

```bash
grep -rln "monitor/builds\|useGetMonitorBuilds\|VertexBuildTable" /Users/brycedeneen/dev/langflow/src/frontend/src/controllers/API/ | head -5
```

If a hook exists, note the import path and reuse in Task 8. If not, create it in Step 3 below.

- [x] **Step 2: Write validate-mapping-config hook**

Create `src/frontend/src/controllers/API/queries/utils/use-post-validate-mapping-config.ts`:

```typescript
import { useMutation, UseMutationResult } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type MappingConfigError = {
  path: (string | number)[];
  message: string;
};

export type ValidateMappingConfigResponse = {
  errors: MappingConfigError[];
};

export function usePostValidateMappingConfig(): UseMutationResult<
  ValidateMappingConfigResponse,
  Error,
  Record<string, unknown>
> {
  return useMutation({
    mutationFn: async (config) => {
      try {
        const response = await api.post<ValidateMappingConfigResponse>(
          getURL("UTILS", { 1: "validate-mapping-config" }),
          config,
        );
        return response.data;
      } catch (err: any) {
        // 422 responses carry `{detail: {errors: [...]}}` or `{errors: [...]}`
        // depending on FastAPI version — normalize to the flat shape.
        const body = err?.response?.data;
        const errors = body?.errors ?? body?.detail?.errors;
        if (Array.isArray(errors)) return { errors };
        throw err;
      }
    },
  });
}
```

- [x] **Step 3: Write jsonschema-to-fields hook**

Create `src/frontend/src/controllers/API/queries/utils/use-post-jsonschema-to-fields.ts`:

```typescript
import { useMutation, UseMutationResult } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type InferredField = {
  name: string;
  type: "str" | "int" | "float" | "bool" | "list" | "dict" | "date" | "datetime";
  required: boolean;
};

export type JsonSchemaToFieldsResponse = { fields: InferredField[] };

export function usePostJsonSchemaToFields(): UseMutationResult<
  JsonSchemaToFieldsResponse,
  Error,
  Record<string, unknown>
> {
  return useMutation({
    mutationFn: async (schema) => {
      const response = await api.post<JsonSchemaToFieldsResponse>(
        getURL("UTILS", { 1: "jsonschema-to-fields" }),
        schema,
      );
      return response.data;
    },
  });
}
```

- [x] **Step 4: (If needed) Write monitor-builds hook**

Only if Step 1 showed no existing hook. Create `src/frontend/src/controllers/API/queries/monitor/use-get-monitor-builds.ts` following the same pattern (query hook, `useQuery`, path `/monitor/builds?flow_id={flowId}`). Use `isPending` not `isLoading` per project convention.

- [x] **Step 5: Confirm `UTILS` key exists in `getURL`**

```bash
grep -n "UTILS\|VALIDATE" /Users/brycedeneen/dev/langflow/src/frontend/src/controllers/API/helpers/constants.ts | head -5
```

If `UTILS` isn't in the URL constants table, add an entry mapping to `/api/v1/utils/{1}`. Model after the existing `VALIDATE` entry (which maps to `/api/v1/validate/{1}`).

- [x] **Step 6: Commit**

```bash
git add src/frontend/src/controllers/API/queries/utils/ \
        src/frontend/src/controllers/API/queries/monitor/ \
        src/frontend/src/controllers/API/helpers/constants.ts
git commit -m "feat(frontend): add React Query hooks for mapping-config + jsonschema endpoints"
```

(Omit paths from the `git add` that don't apply because the hook already existed.)

---

## Task 6: Shared types (`types.ts`)

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/types.ts`

- [x] **Step 1: Write the types file**

```typescript
// Mirror of src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py.
// Keep in sync by hand — small surface, rare changes.

export type FieldType =
  | "str" | "int" | "float" | "bool"
  | "list" | "dict"
  | "date" | "datetime";

export type TransformType =
  | "direct" | "static" | "variable"
  | "template" | "expression" | "array";

export type SchemaSource = "autodetect" | "sample" | "jsonschema";

export interface FieldDef {
  name: string;
  type: FieldType;
  required: boolean;
}

export interface InputSchema { fields: FieldDef[]; }

export interface JoinKey {
  driver_field: string;
  lookup_field: string;
}

export interface JoinDef { on: JoinKey[]; }

export interface InputDef {
  alias: string;
  schema_source: SchemaSource;
  schema: InputSchema;
  sample?: Record<string, unknown> | unknown[] | null;
  jsonschema?: Record<string, unknown> | null;
  join?: JoinDef | null;
}

export interface DestFieldDef {
  name: string;
  type: FieldType;
  required: boolean;
  default: unknown;
}

export interface SourceRef { input: string; field: string; }

export interface MappingEntry {
  destination: string;
  transform: TransformType;
  sources: SourceRef[];
  config: Record<string, unknown>;
}

export interface MapperConfig {
  driver_index: number;
  inputs: InputDef[];
  destination_schema: DestFieldDef[];
  mappings: MappingEntry[];
}

export const EMPTY_MAPPER_CONFIG: MapperConfig = {
  driver_index: 0,
  inputs: [],
  destination_schema: [],
  mappings: [],
};
```

- [x] **Step 2: Smoke-check it compiles**

```bash
cd src/frontend && npx tsc --noEmit src/modals/dataMapperModal/types.ts 2>&1 | head -5
```

Expected: no output (tsc is silent on success).

- [x] **Step 3: Commit**

```bash
git add src/frontend/src/modals/dataMapperModal/types.ts
git commit -m "feat(frontend/data-mapper): add TS types mirroring MapperConfig"
```

---

## Task 7: Pure util — `configBuilder.ts` (draft mutators) + Jest tests

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/util/configBuilder.ts`
- Create: `src/frontend/tests/unit/dataMapperModal/configBuilder.test.ts`

- [x] **Step 1: Failing tests**

Create `src/frontend/tests/unit/dataMapperModal/configBuilder.test.ts`:

```typescript
import {
  addDestinationField,
  removeDestinationField,
  setTransformForDestination,
  setSourcesForDestination,
  addInput,
  setDriverIndex,
  setJoinKey,
  addJoinKey,
  removeJoinKey,
} from "@/modals/dataMapperModal/util/configBuilder";
import { EMPTY_MAPPER_CONFIG, MapperConfig } from "@/modals/dataMapperModal/types";

test("addDestinationField appends and defaults to direct transform", () => {
  const next = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "External_ID", type: "str", required: true, default: null });
  expect(next.destination_schema).toHaveLength(1);
  expect(next.mappings).toHaveLength(1);
  expect(next.mappings[0]).toMatchObject({ destination: "External_ID", transform: "direct" });
});

test("removeDestinationField removes both the schema entry and the mapping", () => {
  const withOne = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "External_ID", type: "str", required: true, default: null });
  const cleaned = removeDestinationField(withOne, "External_ID");
  expect(cleaned.destination_schema).toHaveLength(0);
  expect(cleaned.mappings).toHaveLength(0);
});

test("setTransformForDestination resets config and sources appropriately", () => {
  const start = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "Region", type: "str", required: false, default: "" });
  const asStatic = setTransformForDestination(start, "Region", "static");
  expect(asStatic.mappings[0].transform).toBe("static");
  expect(asStatic.mappings[0].sources).toEqual([]);
  expect(asStatic.mappings[0].config).toEqual({ value: "" });
});

test("setSourcesForDestination replaces the sources array", () => {
  const start = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "Name", type: "str", required: false, default: "" });
  const withSources = setSourcesForDestination(start, "Name", [
    { input: "workers", field: "first_name" },
    { input: "workers", field: "last_name" },
  ]);
  expect(withSources.mappings[0].sources).toHaveLength(2);
});

test("addInput preserves driver_index when adding a lookup", () => {
  const withDriver = addInput(EMPTY_MAPPER_CONFIG, { alias: "workers", schema_source: "autodetect", schema: { fields: [] } });
  const withLookup = addInput(withDriver, { alias: "jobs", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "job_id", lookup_field: "id" }] } });
  expect(withLookup.driver_index).toBe(0);
  expect(withLookup.inputs).toHaveLength(2);
});

test("setDriverIndex in range is accepted; out of range is rejected", () => {
  const withTwo = addInput(addInput(EMPTY_MAPPER_CONFIG, { alias: "a", schema_source: "autodetect", schema: { fields: [] } }), { alias: "b", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "x", lookup_field: "y" }] } });
  expect(setDriverIndex(withTwo, 1).driver_index).toBe(1);
  expect(() => setDriverIndex(withTwo, 5)).toThrow(/out of range/);
});

test("addJoinKey / setJoinKey / removeJoinKey operate on the target input", () => {
  const cfg = addInput(addInput(EMPTY_MAPPER_CONFIG, { alias: "workers", schema_source: "autodetect", schema: { fields: [] } }), { alias: "jobs", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "x", lookup_field: "y" }] } });
  const added = addJoinKey(cfg, "jobs", { driver_field: "", lookup_field: "" });
  expect(added.inputs[1].join!.on).toHaveLength(2);
  const setted = setJoinKey(added, "jobs", 1, { driver_field: "org_id", lookup_field: "org_id" });
  expect(setted.inputs[1].join!.on[1]).toEqual({ driver_field: "org_id", lookup_field: "org_id" });
  const removed = removeJoinKey(setted, "jobs", 0);
  expect(removed.inputs[1].join!.on).toHaveLength(1);
});
```

- [x] **Step 2: Verify failure**

```bash
cd src/frontend && npx jest tests/unit/dataMapperModal/configBuilder.test.ts
```

Expected: module-not-found on `configBuilder`.

- [x] **Step 3: Implement**

Create `src/frontend/src/modals/dataMapperModal/util/configBuilder.ts`:

```typescript
import {
  DestFieldDef,
  InputDef,
  JoinKey,
  MapperConfig,
  MappingEntry,
  SourceRef,
  TransformType,
} from "@/modals/dataMapperModal/types";

// Cheap deep clone that works for JSON-safe structures (our whole surface is).
function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

function defaultConfigForTransform(t: TransformType): Record<string, unknown> {
  switch (t) {
    case "template": return { template: "" };
    case "expression": return { expression: "" };
    case "static": return { value: "" };
    case "variable": return { variable: "" };
    case "array": return { skip_missing: false };
    case "direct": default: return {};
  }
}

export function addDestinationField(cfg: MapperConfig, field: DestFieldDef): MapperConfig {
  const next = clone(cfg);
  next.destination_schema.push(field);
  next.mappings.push({
    destination: field.name,
    transform: "direct",
    sources: [],
    config: {},
  });
  return next;
}

export function removeDestinationField(cfg: MapperConfig, name: string): MapperConfig {
  const next = clone(cfg);
  next.destination_schema = next.destination_schema.filter((d: DestFieldDef) => d.name !== name);
  next.mappings = next.mappings.filter((m: MappingEntry) => m.destination !== name);
  return next;
}

export function setTransformForDestination(cfg: MapperConfig, name: string, t: TransformType): MapperConfig {
  const next = clone(cfg);
  const m = next.mappings.find((mm: MappingEntry) => mm.destination === name);
  if (!m) return next;
  m.transform = t;
  m.config = defaultConfigForTransform(t);
  // `static` and `variable` don't use sources; others keep existing.
  if (t === "static" || t === "variable") m.sources = [];
  return next;
}

export function setSourcesForDestination(cfg: MapperConfig, name: string, sources: SourceRef[]): MapperConfig {
  const next = clone(cfg);
  const m = next.mappings.find((mm: MappingEntry) => mm.destination === name);
  if (m) m.sources = sources;
  return next;
}

export function addInput(cfg: MapperConfig, inp: InputDef): MapperConfig {
  const next = clone(cfg);
  next.inputs.push(inp);
  return next;
}

export function setDriverIndex(cfg: MapperConfig, idx: number): MapperConfig {
  if (idx < 0 || idx >= cfg.inputs.length) {
    throw new Error(`driver_index ${idx} out of range for ${cfg.inputs.length} inputs`);
  }
  const next = clone(cfg);
  next.driver_index = idx;
  return next;
}

function mutateJoin(cfg: MapperConfig, alias: string, fn: (keys: JoinKey[]) => JoinKey[]): MapperConfig {
  const next = clone(cfg);
  const inp = next.inputs.find((i: InputDef) => i.alias === alias);
  if (!inp || !inp.join) return next;
  inp.join.on = fn(inp.join.on);
  return next;
}

export function addJoinKey(cfg: MapperConfig, alias: string, key: JoinKey): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => [...keys, key]);
}

export function setJoinKey(cfg: MapperConfig, alias: string, idx: number, key: JoinKey): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => keys.map((k, i) => (i === idx ? key : k)));
}

export function removeJoinKey(cfg: MapperConfig, alias: string, idx: number): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => keys.filter((_, i) => i !== idx));
}
```

- [x] **Step 4: Verify passes**

```bash
cd src/frontend && npx jest tests/unit/dataMapperModal/configBuilder.test.ts
```

All pass.

- [x] **Step 5: Commit**

```bash
git add src/frontend/src/modals/dataMapperModal/util/configBuilder.ts \
        src/frontend/tests/unit/dataMapperModal/configBuilder.test.ts
git commit -m "feat(frontend/data-mapper): add pure configBuilder utils"
```

---

## Task 8: Pure util — `inferSampleFields.ts` (client-side sample-JSON → fields) + tests

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/util/inferSampleFields.ts`
- Create: `src/frontend/tests/unit/dataMapperModal/inferSampleFields.test.ts`

- [x] **Step 1: Failing test**

```typescript
// src/frontend/tests/unit/dataMapperModal/inferSampleFields.test.ts
import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";

test("flat object infers each field to its primitive type", () => {
  expect(inferSampleFields({ name: "Ada", age: 36, active: true })).toEqual([
    { name: "name", type: "str", required: false },
    { name: "age", type: "int", required: false },
    { name: "active", type: "bool", required: false },
  ]);
});

test("float vs int is inferred", () => {
  expect(inferSampleFields({ ratio: 0.5, count: 3 })).toEqual([
    { name: "ratio", type: "float", required: false },
    { name: "count", type: "int", required: false },
  ]);
});

test("array field becomes 'list'; nested object becomes 'dict'", () => {
  expect(inferSampleFields({ tags: ["x", "y"], meta: { a: 1 } })).toEqual([
    { name: "tags", type: "list", required: false },
    { name: "meta", type: "dict", required: false },
  ]);
});

test("null field falls back to 'str'", () => {
  expect(inferSampleFields({ nope: null })).toEqual([
    { name: "nope", type: "str", required: false },
  ]);
});

test("list of objects uses the first object to infer a shape", () => {
  expect(inferSampleFields([{ a: 1, b: "x" }])).toEqual([
    { name: "a", type: "int", required: false },
    { name: "b", type: "str", required: false },
  ]);
});

test("empty list returns empty fields", () => {
  expect(inferSampleFields([])).toEqual([]);
});

test("ISO datetime string infers datetime", () => {
  expect(inferSampleFields({ at: "2026-04-21T10:00:00Z" })).toEqual([
    { name: "at", type: "datetime", required: false },
  ]);
});
```

- [x] **Step 2: Verify failure**

```bash
cd src/frontend && npx jest tests/unit/dataMapperModal/inferSampleFields.test.ts
```

- [x] **Step 3: Implement**

```typescript
// src/frontend/src/modals/dataMapperModal/util/inferSampleFields.ts
import { FieldDef, FieldType } from "@/modals/dataMapperModal/types";

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function inferType(v: unknown): FieldType {
  if (v === null || v === undefined) return "str";
  if (typeof v === "string") {
    if (ISO_DATETIME.test(v)) return "datetime";
    if (ISO_DATE.test(v)) return "date";
    return "str";
  }
  if (typeof v === "boolean") return "bool";
  if (typeof v === "number") return Number.isInteger(v) ? "int" : "float";
  if (Array.isArray(v)) return "list";
  if (typeof v === "object") return "dict";
  return "str";
}

export function inferSampleFields(sample: unknown): FieldDef[] {
  const obj =
    Array.isArray(sample) && sample.length > 0 && typeof sample[0] === "object" && sample[0] !== null
      ? (sample[0] as Record<string, unknown>)
      : sample && typeof sample === "object" && !Array.isArray(sample)
      ? (sample as Record<string, unknown>)
      : null;

  if (!obj) return [];

  return Object.entries(obj).map(([name, v]) => ({
    name,
    type: inferType(v),
    required: false,
  }));
}
```

- [x] **Step 4: Verify + Commit**

Tests pass.

```bash
git add src/frontend/src/modals/dataMapperModal/util/inferSampleFields.ts \
        src/frontend/tests/unit/dataMapperModal/inferSampleFields.test.ts
git commit -m "feat(frontend/data-mapper): add client-side sample-JSON field inference"
```

---

## Task 9: `useVertexBuildShapes` hook

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/hooks/useVertexBuildShapes.ts`

- [x] **Step 1: Implement**

```typescript
// Consumes the existing /monitor/builds query and extracts a `{alias: FieldDef[] | null}` map
// for the upstream vertex IDs connected to this Data Mapper node.

import { useMemo } from "react";
// import the existing monitor-builds hook, or the one added in Task 5

import { FieldDef, FieldType } from "@/modals/dataMapperModal/types";
import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";

export interface UpstreamShape {
  alias: string;
  vertexId: string;
  fields: FieldDef[] | null; // null = no recent build / not autodetectable
}

export interface UseVertexBuildShapesArgs {
  flowId: string;
  upstreams: { alias: string; vertexId: string }[];
}

export function useVertexBuildShapes({ flowId, upstreams }: UseVertexBuildShapesArgs) {
  // 1. Run the existing monitor-builds hook.
  // 2. For each upstream.vertexId, take the latest build entry, extract its
  //    `data` (the output values), and pick the first value — that's usually the
  //    component's "output" result. Feed it to `inferSampleFields`.
  // 3. If any step fails or no build exists, set `fields: null` for that alias.
  const { data: buildsByVertex, isPending } = /* useGetMonitorBuilds */ undefined as any;

  return useMemo(() => {
    if (!buildsByVertex) {
      return {
        shapes: upstreams.map((u) => ({ ...u, fields: null })) as UpstreamShape[],
        isPending,
      };
    }

    const shapes: UpstreamShape[] = upstreams.map(({ alias, vertexId }) => {
      const builds = buildsByVertex[vertexId];
      if (!builds || builds.length === 0) return { alias, vertexId, fields: null };
      const latest = builds[builds.length - 1];
      const dataValues = Object.values(latest?.data ?? {});
      if (dataValues.length === 0) return { alias, vertexId, fields: null };
      const payload = dataValues[0];
      const fields = inferSampleFields(payload);
      return { alias, vertexId, fields: fields.length > 0 ? fields : null };
    });

    return { shapes, isPending };
  }, [buildsByVertex, upstreams, isPending]);
}
```

**Note:** the exact monitor-builds hook name and response shape must be resolved from Task 5 Step 1. If the existing hook's response format is different (e.g. `{vertex_builds: {...}}` instead of direct map), adjust indexing here. The important invariant is: given a vertex ID, return the latest build's `data` values.

- [x] **Step 2: No unit test (integration-covered by modal playwright e2e)**

This hook only aggregates existing data; Jest mocking of react-query is possible but low value. Leave the coverage to the e2e test.

- [x] **Step 3: Commit**

```bash
git add src/frontend/src/modals/dataMapperModal/hooks/useVertexBuildShapes.ts
git commit -m "feat(frontend/data-mapper): derive upstream field shapes from monitor builds"
```

---

## Task 10: `SchemaSourceTabs.tsx`

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx`
- Create: `src/frontend/tests/unit/dataMapperModal/SchemaSourceTabs.test.tsx`

- [x] **Step 1: Failing render test**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { SchemaSourceTabs } from "@/modals/dataMapperModal/components/SchemaSourceTabs";

test("renders all three tabs and calls onSourceChange when a tab is clicked", () => {
  const onSourceChange = jest.fn();
  render(<SchemaSourceTabs source="autodetect" onSourceChange={onSourceChange} onSampleChange={() => {}} onJsonSchemaChange={() => {}} />);
  expect(screen.getByText("Autodetect")).toBeInTheDocument();
  expect(screen.getByText("Paste sample")).toBeInTheDocument();
  expect(screen.getByText("JSON Schema")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Paste sample"));
  expect(onSourceChange).toHaveBeenCalledWith("sample");
});

test("autodetect tab shows a hint when fields is null", () => {
  render(
    <SchemaSourceTabs
      source="autodetect"
      fields={null}
      onSourceChange={() => {}}
      onSampleChange={() => {}}
      onJsonSchemaChange={() => {}}
    />,
  );
  expect(screen.getByText(/run this flow once/i)).toBeInTheDocument();
});

test("paste-sample tab renders a textarea", () => {
  render(
    <SchemaSourceTabs
      source="sample"
      onSourceChange={() => {}}
      onSampleChange={() => {}}
      onJsonSchemaChange={() => {}}
    />,
  );
  expect(screen.getByRole("textbox")).toBeInTheDocument();
});
```

- [x] **Step 2: Verify failure + implement**

```tsx
// src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx
import { useState } from "react";
import { FieldDef, SchemaSource } from "@/modals/dataMapperModal/types";

export interface SchemaSourceTabsProps {
  source: SchemaSource;
  fields?: FieldDef[] | null;
  onSourceChange: (s: SchemaSource) => void;
  onSampleChange: (sample: unknown) => void;
  onJsonSchemaChange: (schema: Record<string, unknown>) => void;
}

const TAB_LABELS: Record<SchemaSource, string> = {
  autodetect: "Autodetect",
  sample: "Paste sample",
  jsonschema: "JSON Schema",
};

export function SchemaSourceTabs(props: SchemaSourceTabsProps) {
  const { source, fields, onSourceChange, onSampleChange, onJsonSchemaChange } = props;
  const [sampleText, setSampleText] = useState("");
  const [schemaText, setSchemaText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  return (
    <div className="schema-source-tabs">
      <div role="tablist" className="tab-row">
        {(["autodetect", "sample", "jsonschema"] as SchemaSource[]).map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={source === s}
            onClick={() => onSourceChange(s)}
          >
            {TAB_LABELS[s]}
          </button>
        ))}
      </div>

      {source === "autodetect" && (
        <div>
          {fields && fields.length > 0 ? (
            <span>{fields.length} fields detected</span>
          ) : (
            <p className="hint">
              No recent flow run found — run this flow once, or switch to Paste sample / JSON Schema.
            </p>
          )}
        </div>
      )}

      {source === "sample" && (
        <div>
          <textarea
            value={sampleText}
            onChange={(e) => {
              setSampleText(e.target.value);
              try {
                onSampleChange(JSON.parse(e.target.value));
                setParseError(null);
              } catch (err: any) {
                setParseError(err?.message ?? "Invalid JSON");
              }
            }}
            placeholder='Paste a representative JSON payload, e.g. {"user_id": "u-1", "email": "a@b.co"}'
          />
          {parseError && <p className="error">{parseError}</p>}
        </div>
      )}

      {source === "jsonschema" && (
        <div>
          <textarea
            value={schemaText}
            onChange={(e) => {
              setSchemaText(e.target.value);
              try {
                onJsonSchemaChange(JSON.parse(e.target.value));
                setParseError(null);
              } catch (err: any) {
                setParseError(err?.message ?? "Invalid JSON");
              }
            }}
            placeholder="Paste a JSON Schema document"
          />
          {parseError && <p className="error">{parseError}</p>}
        </div>
      )}
    </div>
  );
}
```

- [x] **Step 3: Verify passes + Commit**

```bash
git add src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx \
        src/frontend/tests/unit/dataMapperModal/SchemaSourceTabs.test.tsx
git commit -m "feat(frontend/data-mapper): add SchemaSourceTabs subcomponent"
```

---

## Task 11: `JoinKeyEditor.tsx` (compound-AND two-dropdown list)

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/JoinKeyEditor.tsx`
- Create: `src/frontend/tests/unit/dataMapperModal/JoinKeyEditor.test.tsx`

- [x] **Step 1: Tests + implementation**

Tests cover: renders N rows = keys.length, clicking "Add another key" appends one, changing a dropdown calls setJoinKey, clicking "Remove" calls removeJoinKey (last key can't be removed — minimum 1).

Implementation: driver-field dropdown is populated from driver's detected fields, lookup-field dropdown from this input's detected fields. Each row has a small "−" remove button except when exactly 1 key remains.

(Full test + implementation code structure mirrors Task 10's pattern; implementer writes the test first, verifies fail, implements, verifies pass, commits.)

**Commit message:** `feat(frontend/data-mapper): add JoinKeyEditor with compound-AND keys`

---

## Task 12: `TransformCell.tsx` (adaptive config cell per transform type)

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/TransformCell.tsx`
- Create: `src/frontend/tests/unit/dataMapperModal/TransformCell.test.tsx`

- [x] **Step 1: Tests**

Tests cover each transform type's expected inline UI:
- `direct`: renders a source-field picker (input alias dropdown + field dropdown)
- `template`: renders a Jinja textarea showing the current `config.template`
- `expression`: renders a single-line code input
- `static`: renders a JSON-value input (string/number/bool sensitive)
- `variable`: renders a variable-name input
- `array`: renders a multi-field picker + a "skip missing" checkbox

Each onChange dispatches the appropriate config / sources mutation.

- [x] **Step 2: Implementation**

Component accepts `{mapping: MappingEntry, inputs: InputDef[], onMappingChange: (m: MappingEntry) => void}`. Switches on `mapping.transform` to render the right inline editor. Inline editors are self-contained; they compute the new MappingEntry and call `onMappingChange`.

**Commit message:** `feat(frontend/data-mapper): add TransformCell adaptive editor`

---

## Task 13: `InputsPanel.tsx`

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/InputsPanel.tsx`

Top bar: lists each connected upstream input as a card. Per card:
- Alias field (text input; auto-populated from upstream vertex's display_name)
- Driver toggle (radio, single selection across the row of cards — setting it mutates `cfg.driver_index`)
- `SchemaSourceTabs` (from Task 10)
- `JoinKeyEditor` (from Task 11; hidden on the driver card)

- [x] **Step 1: Compose**

This task is mostly composition + layout. No new logic. No standalone unit tests — covered by e2e.

**Commit message:** `feat(frontend/data-mapper): assemble InputsPanel top bar`

---

## Task 14: `DestinationTable.tsx`

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx`

Columns: `Destination field`, `Type`, `Required`, `Transform`, `Source / Config` (renders `<TransformCell />`), `Default`, row actions (delete).

- Row count = `cfg.destination_schema.length`.
- Below the table: an "+ Add field" button (opens an inline form with name / type / required / default, appends via `addDestinationField`).
- Error chips on rows whose destination is in the current validation error path.

- [x] **Step 1: Implement, compose, commit**

**Commit message:** `feat(frontend/data-mapper): assemble DestinationTable`

---

## Task 15: `DataMapperModal/index.tsx` — modal shell

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/index.tsx`
- Create: `src/frontend/src/modals/dataMapperModal/README.md`

Root component wires everything:
- Props: `open: boolean, value: string, onChange: (newValue: string) => void, onClose: () => void, nodeId: string, flowId: string, connectedUpstreams: {alias: string, vertexId: string}[], suggestionsSlot?: React.ReactNode`.
- `useState<MapperConfig>` initialized from `JSON.parse(value || stringify(EMPTY_MAPPER_CONFIG))`.
- `useVertexBuildShapes` fetches upstream shapes.
- `usePostValidateMappingConfig` on Save.
- Layout: `<ModalHeader>{suggestionsSlot}</ModalHeader>` | `<InputsPanel />` | `<DestinationTable />` | `<Footer with [Cancel] [Save] />`.
- On Save → mutate → on success → `onChange(JSON.stringify(cfg))` → `onClose()`. On failure → show error banner with error count + decorate error rows.

README documents the `suggestionsSlot` extension seam for the assistant team.

- [x] **Step 1: Implement + commit**

**Commit message:** `feat(frontend/data-mapper): add DataMapperModal shell`

---

## Task 16: `MappingComponent` input renderer + registration

**Files:**
- Create: `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`
- Modify: `src/frontend/src/components/core/parameterRenderComponent/index.tsx` (add `"MappingInput"` case)

Renders:
- Button: `Configure mapping` (empty state) or `Edit mapping · N fields` (where N = destination row count parsed from current value).
- A small summary chip below the button (e.g. `driver: workers`).
- Click opens `DataMapperModal`, passing the current value + `onChange` that writes back to the component field.

- [x] **Step 1: Implement + register**

Add case in `parameterRenderComponent/index.tsx` switch:

```tsx
case "MappingInput":
  return <MappingComponent {...baseInputProps} />;
```

(Exact line placement: match the alphabetical ordering already in use for the `case` arms.)

- [x] **Step 2: Commit**

**Commit message:** `feat(frontend/data-mapper): register MappingInput → MappingComponent renderer`

---

## Task 17: Playwright e2e — end-to-end configuration + save

**Files:**
- Create: `src/frontend/tests/core/unit/dataMapperModal.spec.ts`

- [x] **Step 1: Write the spec**

Scenarios:
1. Happy path: add Data Mapper, connect two upstreams (existing starter flow or quick seed), open modal, set driver, add one join key, define one destination field with direct mapping, save, verify the node's serialized `mapping_config` value contains the expected JSON.
2. Save blocked when a required destination has no mapping.
3. Save-loop after fix: add the missing mapping, save succeeds, modal closes.
4. Paste-sample tab infers fields correctly and populates the mapping dropdowns.

Follow the pattern of `src/frontend/tests/core/unit/codeAreaModalComponent.spec.ts` for bootstrap + modal interaction helpers.

- [x] **Step 2: Run locally against a dev server**

```bash
cd src/frontend && npx playwright test tests/core/unit/dataMapperModal.spec.ts
```

All scenarios green.

- [x] **Step 3: Commit**

**Commit message:** `test(frontend/data-mapper): playwright e2e for modal configuration`

---

## Task 18: Rebuild the prebuilt component index (version bump invalidation)

**Files:**
- Modify: `src/lfx/src/lfx/_assets/component_index.json`

- [x] **Step 1: Rebuild**

```bash
uv run python scripts/build_component_index.py
```

- [x] **Step 2: Verify version bump landed**

```bash
grep -c '"version": 2' src/lfx/src/lfx/_assets/component_index.json
```

Expected: at least one match (the DataMapper entry now shows version 2).

- [x] **Step 3: Commit only the index file**

```bash
git add src/lfx/src/lfx/_assets/component_index.json
git commit -m "chore(lfx): rebuild component index for DataMapperComponent v2"
```

**Scope caveat:** as with Task 18 of Phase 1a, this rebuild may re-pick unrelated WIP components the branch has accumulated. If the diff is bigger than expected, note it in the task report as a concern — do NOT attempt to hand-prune the JSON.

---

## Task 19: Full test sweep + dev-server smoke (recommended)

**Files:** none (verification).

- [x] **Step 1: Backend unit tests (data_mapper + new endpoints)**

```bash
cd src/lfx && uv run pytest tests/unit/components/processing/ -v -k data_mapper
cd src/lfx && uv run pytest tests/unit/inputs/test_mapping_input.py -v
cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py -v
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v
```

All green.

- [x] **Step 2: Frontend unit tests**

```bash
cd src/frontend && npx jest tests/unit/dataMapperModal/
```

All green.

- [x] **Step 3: Playwright**

```bash
cd src/frontend && npx playwright test tests/core/unit/dataMapperModal.spec.ts
```

All green.

- [x] **Step 4 (human-in-the-loop): dev server smoke**

```bash
LFX_DEV=1 make run_cli
```

Open a flow, add Data Mapper (now shows version 2), connect two upstreams, open the modal, configure one mapping, save, run the flow. Confirm the mapping runs end-to-end.

- [x] **Step 5: No commit — verification only.**

---

## Self-Review

### Spec coverage

| Spec section | Covered by |
|---|---|
| `MappingInput` type + `MAPPING` enum | Task 1 |
| `MappingInput` re-export from `lfx.io` | Task 1 |
| Component migration (CodeInput → MappingInput, v2, changelog) | Task 2 |
| `validate-mapping-config` endpoint | Task 3 |
| `jsonschema-to-fields` endpoint | Task 4 |
| Frontend query hooks | Task 5 |
| TS `MapperConfig` mirror | Task 6 |
| Pure configBuilder utils | Task 7 |
| Client-side sample inference | Task 8 |
| Vertex-build shape derivation | Task 9 |
| Schema-source tabs UI | Task 10 |
| Compound join-key editor | Task 11 |
| Adaptive transform cell | Task 12 |
| InputsPanel composition | Task 13 |
| DestinationTable composition | Task 14 |
| Modal shell + suggestionsSlot seam + README | Task 15 |
| Input renderer + switch-case registration | Task 16 |
| Playwright e2e | Task 17 |
| Component index rebuild (version 2) | Task 18 |
| Full sweep | Task 19 |

Every in-scope spec item maps to at least one task. ✅

### Placeholder scan

- Task 3 has one open placeholder: the exact file location of the `/validate/code` handler. Plan explicitly tells the implementer to resolve it at the top of Task 3 via grep. Acceptable because the grep result is deterministic (there's one such file).
- Task 5 Step 5 asks the implementer to check if the `UTILS` URL key exists and add it if not. Explicit, not hand-wave.
- Tasks 11, 12, 13, 14 rely on shorter "tests cover..., implementation mirrors..." prose rather than inlining full test code. Each task is composition-heavy, and the bulk of the testable logic is in `configBuilder` (Task 7) and `inferSampleFields` (Task 8) — the visual components are straightforward wiring. Acceptable for Jest snapshot-ish coverage plus Playwright e2e covering user flows.
- **Tightening candidate:** Tasks 11–14 could use fuller code snippets if implementers stall. If that happens during execution, expand the task prompt at dispatch time rather than rewriting the plan.

### Type consistency

- `MapperConfig` and its subtypes are defined in the TS `types.ts` (Task 6) and referenced consistently across Tasks 7–16.
- `MapperConfigError` / `ValidateMappingConfigResponse` types defined in Task 5, used in Task 15.
- `InferredField` (from Task 5) and `FieldDef` (from Task 6) overlap but are not the same type — the jsonschema endpoint returns `InferredField`, the internal model uses `FieldDef`. These are structurally compatible; the modal consumes the response as `FieldDef[]` at the call site. Acceptable (minor duplication; formal unification would be premature).
- Hook return types include `{ isPending }` consistently with React Query v5.

All consistent. ✅
