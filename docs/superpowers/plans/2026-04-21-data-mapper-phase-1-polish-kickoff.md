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

The order of operations agreed with the user (updated 2026-04-21): **finish Phase 1 polish — which now folds in heavy assistant-driven auto-mapping, previously slated as Phase 1c — then Phase 2 feature items.** Light/heuristic auto-mapping is dropped entirely; heavy subsumes it.

Phase 1 polish = heavy (assistant-driven) auto-mapping, plus the three UX gaps in the shipped modal. No engine changes. No new transform types.

### Work items

#### 1. Heavy (assistant-driven) auto-mapping

Use an LLM-backed assistant to infer mappings from the two resolved schemas (driver input + destination): fills in `sources`, `transform`, and the associated config so the user starts from a mostly-filled mapping list instead of a blank one. One button in the modal's existing `suggestionsSlot` seam. Replaces the light heuristic approach entirely.

Open questions to resolve in brainstorming (before any code):

- **Infra availability.** What component-assistant infra exists today in this repo? Is there a shared client / endpoint / model config, or does this ship its own? Which model (Opus/Sonnet/Haiku) is the right default given latency + cost + quality for structured-mapping output?
- **Prompt surface.** How do we present both schemas to the assistant — fields + types only, or also sample values from `flowPool` when available? How do we describe the transform vocabulary so the assistant actually uses `lookup`/`concat`/`split`/etc. instead of defaulting everything to `direct`?
- **Response contract.** Does the assistant return a full `MappingConfig` (and we validate + merge), or a lighter "suggestions" payload that the modal reconciles? Streaming or single-shot? What's the fallback when the response fails schema validation?
- **UX for accept/reject.** Diff view with per-row accept/reject, same as we'd have done for the light version? Confidence indicator per suggestion? What does "Apply all" mean when some rows are low-confidence?
- **Never-overwrite rule.** Same as light would have had: only fill rows where `transform === "direct"` and `sources.length === 0`. (Confirm this is still the right guardrail for an assistant that might want to *change* an existing row.)
- **Failure modes.** API down, rate-limited, timeout, invalid output, user cancels mid-stream — what does the UI do in each?
- **Auth / keys.** Does this reuse a repo-level API key, the user's own key via a secret Variable, or the organization-scoped credential? (Ties into the existing `SecretStrInput.auto_promote` behavior — see `project_secret_str_input_auto_promote.md`.)

Spec target: `docs/superpowers/specs/YYYY-MM-DD-data-mapper-heavy-auto-mapping-design.md`. Plan target: `docs/superpowers/plans/YYYY-MM-DD-data-mapper-heavy-auto-mapping-plan.md`.

#### 2. Schema UX gaps (in `DataMapperModal`)

Today the modal's three schema-source tabs have rough edges:

- **Paste sample** — the textarea parses input as JSON and writes the inferred `schema.fields` to the input, but **shows no preview**. Users can't see what was inferred until they try to wire a field. Add an inline field-list preview below the textarea (name + type pill per field, or a "No fields inferred yet" state).
- **JSON Schema** — the tab currently stashes the raw JSON Schema document in `input.jsonschema` but **never calls the backend endpoint** that converts it to fields. The `usePostJsonSchemaToFields` mutation hook exists (`src/frontend/src/controllers/API/queries/utils/use-post-jsonschema-to-fields.ts`) — the tab needs to call it on valid JSON, populate `input.schema.fields` from the response, and show errors from the 400 path inline.
- **Autodetect** — when no recent flow run exists (`flowPool[vertexId]` is absent), the UI shows a terse hint. Tighten: add a "Run this flow once to autodetect" call-to-action with a link/button that triggers a flow run, and distinguish "upstream never ran" from "upstream ran but produced no output."

All three gaps are client-side work inside `src/frontend/src/modals/dataMapperModal/components/SchemaSourceTabs.tsx` + its parent (`InputsPanel.tsx`) and possibly `index.tsx` for orchestration. No new backend endpoints needed.

#### 3. Live Playwright e2e (verification, not a feature)

The Playwright spec `src/frontend/tests/core/unit/dataMapperModal.spec.ts` parses and lists 4 scenarios but has never been run against a live dev server (the session that wrote it didn't have one available). Running it once against `LFX_DEV=1 make run_cli` and closing any gaps is cheap cleanup. If the spec needs updates after the polish items land, do them here.

## Non-goals for Phase 1 polish

- **Light/heuristic auto-mapping** — dropped; heavy (assistant-driven) replaces it entirely.
- **Any Phase 2 feature** — `lookup` dict transform, join-type switcher (inner/right/outer), one-to-many aggregation, OpenAPI schema ingestion. Each gets its own small spec after polish ships.
- **Engine or config-schema changes** — UI + a possible new backend endpoint for the assistant call, but no changes to `MappingConfig` semantics or the transform engine.
- **Component version bump** — none of the polish items is a user-visible contract change, so `version: int = 2` stays. (Re-evaluate if heavy auto-mapping ends up altering the component's input surface.)

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

1. Read this doc, the two Phase 1b spec + plan docs, and the memory entries listed above.
2. Work the items in order: **heavy auto-mapping → schema UX gaps → Playwright run.**
3. Heavy auto-mapping: run `superpowers:brainstorming` first (infra availability, prompt surface, response contract, accept/reject UX, failure modes) → write a spec → `superpowers:writing-plans` → execute.
4. Schema UX gaps and Playwright: mechanical — go straight to `superpowers:writing-plans` for short plans, then execute with `superpowers:subagent-driven-development`.

Commit authorization for Phase 1 polish work is **not yet granted** — the blanket approval from Phase 1a/1b was scoped to those plans. Ask before committing in the new session.
