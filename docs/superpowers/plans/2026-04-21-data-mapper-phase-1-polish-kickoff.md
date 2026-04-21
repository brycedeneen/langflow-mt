# Data Mapper — Phase 1 Polish Kickoff

**Status:** Scoping note (not a full implementation plan yet)
**Date:** 2026-04-21
**For:** fresh session picking up after Phase 1a + 1b shipped
**Next step after this doc:** use `superpowers:brainstorming` to sharpen scope, then `superpowers:writing-plans` for the implementation plan.

## Where we are

The Data Mapper component is **functionally shipped**:

- **Phase 1a** (backend + raw JSON config): `2026-04-21-data-mapper-component-design.md` / `2026-04-21-data-mapper-component-phase-1a.md`. 20 tasks shipped across ~20 commits ending `7384f699`. 104 tests green.
- **Phase 1b** (visual modal UI): `2026-04-21-data-mapper-phase-1b-design.md` / `2026-04-21-data-mapper-phase-1b-plan.md`. 19 tasks shipped. `DataMapperComponent` bumped v1 → v2. 145 tests green (117 backend + 28 Jest + 4 Playwright specs parse). A runtime render-loop bug from mixing `useGetBuildsQuery`'s `setFlowPool` side effect with the modal's always-mounted hook was caught and fixed in `6b0d8f88`.

Confirmed working end-to-end via manual smoke test (the bug above was how we found it; the fix is in).

## What "Phase 1 polish" means

The order of operations agreed with the user is: **finish Phase 1 polish → Phase 2 feature items → heavy assistant-driven auto-mapping (Phase 1c).**

Phase 1 polish = the three UX gaps that exist in the shipped modal, plus light auto-mapping as a pure-frontend heuristic. No backend engine changes. No new transform types.

### Work items

#### 1. Light auto-mapping (heuristic, no LLM)

When both sides of the modal have resolved field lists (driver input schema + destination schema), offer a "Suggest mappings" button that populates unset mapping rows using a heuristic match. Reasonable scoring:

- Exact match (case-insensitive) of normalized names — highest confidence.
- Normalize once via `snake_case → camelCase → PascalCase` equivalence plus whitespace/underscore stripping. (`first_name`, `firstName`, `FirstName`, `first name` all match.)
- Built-in synonym list for common ETL aliases: `id ↔ external_id ↔ uid`, `email ↔ email_address`, `created_at ↔ created_on ↔ created_date`, etc. Small table, extend as cases appear.
- Token-Jaccard fallback on multi-word names for low-confidence suggestions.
- **Never overwrite an already-configured mapping.** Only fill rows whose `transform === "direct"` and `sources.length === 0` (untouched default state).

UX: button in the modal's existing `suggestionsSlot` extension seam (already wired). Click → produces a diff view (which destinations would get which source) → user accepts / rejects individually or "Apply all." Drops the need for the assistant team for the common case. Ships in isolation; the heavy assistant-driven tool (Phase 1c) supersedes this later for hard cases.

Spec should live at `docs/superpowers/specs/YYYY-MM-DD-data-mapper-light-auto-mapping-design.md`.

#### 2. Schema UX gaps (in `DataMapperModal`)

Today the modal's three schema-source tabs have rough edges:

- **Paste sample** — the textarea parses input as JSON and writes the inferred `schema.fields` to the input, but **shows no preview**. Users can't see what was inferred until they try to wire a field. Add an inline field-list preview below the textarea (name + type pill per field, or a "No fields inferred yet" state).
- **JSON Schema** — the tab currently stashes the raw JSON Schema document in `input.jsonschema` but **never calls the backend endpoint** that converts it to fields. The `usePostJsonSchemaToFields` mutation hook exists (`src/frontend/src/controllers/API/queries/utils/use-post-jsonschema-to-fields.ts`) — the tab needs to call it on valid JSON, populate `input.schema.fields` from the response, and show errors from the 400 path inline.
- **Autodetect** — when no recent flow run exists (`flowPool[vertexId]` is absent), the UI shows a terse hint. Tighten: add a "Run this flow once to autodetect" call-to-action with a link/button that triggers a flow run, and distinguish "upstream never ran" from "upstream ran but produced no output."

All three gaps are client-side work inside `src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx` + its parent (`InputsPanel.tsx`) and possibly `index.tsx` for orchestration. No new backend endpoints needed.

#### 3. Live Playwright e2e (verification, not a feature)

The Playwright spec `src/frontend/tests/core/unit/dataMapperModal.spec.ts` parses and lists 4 scenarios but has never been run against a live dev server (the session that wrote it didn't have one available). Running it once against `LFX_DEV=1 make run_cli` and closing any gaps is cheap cleanup. If the spec needs updates after the polish items land, do them here.

## Non-goals for Phase 1 polish

- **Heavy (assistant-driven) auto-mapping** — Phase 1c, separate plan when the component-assistant infra is ready.
- **Any Phase 2 feature** — `lookup` dict transform, join-type switcher (inner/right/outer), one-to-many aggregation, OpenAPI schema ingestion. Each gets its own small spec after polish ships.
- **Engine or config-schema changes** — this phase is UI-only.
- **Component version bump** — none of the polish items is a user-visible contract change, so `version: int = 2` stays.

## Pointers the next session will need

### Committed design & plan docs
- `docs/superpowers/specs/2026-04-21-data-mapper-component-design.md` — Phase 1a spec
- `docs/superpowers/specs/2026-04-21-data-mapper-phase-1b-design.md` — Phase 1b spec (has the `suggestionsSlot` extension-seam contract we'll plug into for auto-mapping)
- `docs/superpowers/plans/2026-04-21-data-mapper-component-phase-1a.md` — Phase 1a plan
- `docs/superpowers/plans/2026-04-21-data-mapper-phase-1b-plan.md` — Phase 1b plan
- `src/frontend/src/modals/dataMapperModal/README.md` — documents the `suggestionsSlot` contract

### Code landmarks
- Mapper config shape (source of truth): `src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py`
- Engine (unchanged by polish): `src/lfx/src/lfx/components/processing/_data_mapper/`
- Component shell: `src/lfx/src/lfx/components/processing/data_mapper.py`
- Backend endpoints: `src/backend/base/langflow/api/v1/validate.py` (search `validate-mapping-config`, `jsonschema-to-fields`)
- Frontend modal: `src/frontend/src/modals/dataMapperModal/`
- Frontend input renderer: `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`
- TS types (mirrors the Pydantic schema): `src/frontend/src/modals/dataMapperModal/types.ts`
- Pure utilities (already have Jest coverage): `src/frontend/src/modals/dataMapperModal/util/configBuilder.ts` + `inferSampleFields.ts`

### Memory entries relevant to this work
- `project_use_get_builds_side_effect.md` — don't re-introduce the render loop.
- `feedback_subagent_commit_hygiene.md` — dispatched subagents must stage explicit paths.
- `project_zustand_v5_migration.md` — `useShallow` for object/array selectors.
- `project_frontend_test_stack.md` — Jest (not Vitest); `isPending` not `isLoading`.

### Running tests
- Backend: `cd src/lfx && uv run pytest tests/unit/components/processing/ -v -k data_mapper`
- Backend API: `cd src/backend && uv run pytest tests/unit/api/test_mapping_config_endpoints.py -v`
- Frontend unit: `cd src/frontend && npx jest tests/unit/dataMapperModal/ src/modals/dataMapperModal/ --no-coverage`
- Playwright: `cd src/frontend && npx playwright test tests/core/unit/dataMapperModal.spec.ts`
- Dev server: `LFX_DEV=1 make run_cli` (from repo root)

## Suggested flow for the next session

1. Read this doc, the two Phase 1b spec + plan docs, and the three memory entries listed above.
2. Pick one of: light auto-mapping, schema UX gaps, or Playwright run. Each is independently shippable.
3. If picking light auto-mapping: run `superpowers:brainstorming` to sharpen the heuristic scoring + synonym list before writing code.
4. If picking schema UX gaps or Playwright: those are mechanical — go straight to `superpowers:writing-plans` for a short plan, then execute with `superpowers:subagent-driven-development`.

Commit authorization for Phase 1 polish work is **not yet granted** — the blanket approval from Phase 1a/1b was scoped to those plans. Ask before committing in the new session.
