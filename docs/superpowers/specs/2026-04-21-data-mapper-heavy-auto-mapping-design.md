# Data Mapper — Heavy (Assistant-Driven) Auto-Mapping Design

**Status:** Draft
**Date:** 2026-04-21
**Owner:** bryced
**Target branch:** `platform-multi-tenant`
**Supersedes:** the "Heavy auto-mapping" bullet under Non-goals of `2026-04-21-data-mapper-phase-1b-design.md`; folds the originally-planned Phase 1c into Phase 1 polish. The previously-scoped "light (heuristic) auto-mapping" from `2026-04-21-data-mapper-phase-1-polish-kickoff.md` is dropped entirely in favor of this approach.

## Purpose

Fill the `suggestionsSlot` extension seam wired up in Phase 1b with a working auto-mapping experience. When a user has connected inputs and defined a destination schema, clicking "Suggest mappings" produces a list of `MappingEntry` proposals — one per empty destination — that the user can accept selectively (per-row) or in bulk. The LLM proposal is produced by a dedicated Langflow flow (`DataMapperAutoMap.json`) shipped in-repo and invoked via the existing `POST /api/v1/session/{slug}/run` endpoint.

## Why a shipped flow (approach C) and not a hardcoded backend endpoint

The Data Mapper component is expected to be one of the platform's highest-value, most-used components. The auto-mapping prompt, transform vocabulary, and output contract are product surface — they will evolve as the component grows. Keeping that surface in a **flow** (authored in Langflow itself, tuneable without a backend release) rather than a Python string literal gives us tight alignment between assistant behavior and component behavior over time.

Concretely, this means:
- The prompt lives in the flow's nodes, editable like any other flow.
- Model choice (`assistant.provider` / `assistant.model` / `assistant.api_key`) is per-org, read from Variables the same way `TemplateAssistant` reads them.
- No new backend route, no new backend Python code — just a JSON file in `src/backend/base/langflow/agentic/flows/` that the existing `load_agentic_flows()` loader discovers at startup.

## Scope

### In scope

- **New shipped flow:** `src/backend/base/langflow/agentic/flows/DataMapperAutoMap.json`.
- **New frontend component:** `MappingSuggestions` rendered inside `DataMapperModal`'s `suggestionsSlot`.
- **Contract extension on `DataMapperModal`:** four new optional props (`pendingSuggestions`, `showPendingSuggestions`, `onAcceptSuggestion`, `onRejectSuggestion`) that let the destination table render proposed rows with per-row ✓/✗. Backwards-compatible — Phase 1b callers that don't pass suggestions are unchanged.
- **New query hook:** `use-data-mapper-auto-map.ts`, modeled on `use-template-assistant.ts`, targeting `POST /api/v1/session/DataMapperAutoMap/run`.
- **Pure utilities** (Jest-testable): `filterEligibleSuggestions.ts` (never-overwrite rule), `applyMappingSuggestion.ts` (merge logic).
- **State orchestration** in `MappingComponent` (the input renderer that opens the modal).
- **Test coverage:** backend test hitting the session endpoint with a mocked LLM provider; frontend Jest unit coverage for pure modules; Playwright e2e for the full Suggest → Apply flow.

### Non-goals (explicitly deferred)

- **Destination schema auto-proposal.** The flow does not suggest destination fields — only mappings for destinations the user has already defined.
- **Confidence scoring + rationale per entry.** Considered during brainstorming (option c of "output shape"), dropped for v1.
- **Conflict-resolution panel.** A separate "show what the LLM would have proposed for customized rows" panel — considered during brainstorming (option b of "merge rule"), deferred.
- **Per-row "redo" for customized rows.** Today: user clears a row to get it re-suggested. Row-level "redo with AI" button is a follow-up.
- **Per-invocation "send samples" toggle.** Privacy control; trust model for v1 is "same as any other LLM component in the user's flows."
- **Per-org custom system prompts.** Tuning the flow's prompt per organization. Interesting future expansion; out of v1 scope.
- **Live row-by-row streaming.** Rows appearing as the LLM emits them, mid-stream. v1 uses spinner-until-complete; the endpoint still uses `stream: true` to match the template-assistant pattern but the UI only parses on completion.
- **Learning from rejections.** Feedback loop where rejected suggestions inform future prompts. Way out there.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Flow Builder canvas                                     │
│  ┌────────────────────────┐                              │
│  │ MappingComponent        │                              │
│  │ (input renderer)        │◄──── opens ──── button click│
│  │  owns suggestion state  │                              │
│  └────────┬────────────────┘                              │
│           │ mount                                         │
│           ▼                                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │ DataMapperModal                                    │  │
│  │   suggestionsSlot: <MappingSuggestions/>           │  │
│  │     ┌────────────────────────────────┐             │  │
│  │     │ Suggest button / spinner /     │             │  │
│  │     │ tab toggle / Apply-all /       │             │  │
│  │     │ error chip                     │             │  │
│  │     └────────────────────────────────┘             │  │
│  │   destination table:                               │  │
│  │     reads pendingSuggestions + handlers as props   │  │
│  │     renders blue rows with per-row ✓/✗             │  │
│  └────────────┬───────────────────────────────────────┘  │
└───────────────┼─────────────────────────────────────────┘
                │  POST  input_value=<JSON blob>, stream=true
                ▼
┌─────────────────────────────────────────────────────────┐
│  POST /api/v1/session/DataMapperAutoMap/run             │
│  (EXISTING endpoint — same one TemplateAssistant uses)  │
│                                                          │
│  Runs the shipped flow:                                  │
│   agentic/flows/DataMapperAutoMap.json                   │
│   └─ chat input (receives JSON blob)                     │
│   └─ JSON parse                                          │
│   └─ prompt builder (interpolates schemas + samples)     │
│   └─ LLM node (uses org assistant.* Variables)           │
│   └─ output cleaner (strip fences → parse → validate)    │
│   └─ chat output (emits validated MappingEntry[] JSON)   │
└─────────────────────────────────────────────────────────┘
```

### Principle: flow is the product surface

The flow is authored and shipped exactly like `TemplateAssistant.json`, `SystemMessageGen.json`, and `LangflowAssistant.json`. It is auto-discovered on startup by `load_agentic_flows()` at `src/backend/base/langflow/initial_setup/setup.py:693`. The frontend references it by the string slug `"DataMapperAutoMap"` — not a UUID — so the client-side call is stable across environments.

## Backend

### 1. The shipped flow (`DataMapperAutoMap.json`)

**Location:** `src/backend/base/langflow/agentic/flows/DataMapperAutoMap.json`.

**Flow composition (high level; exact node graph is a plan-level detail):**

1. **Chat Input** — receives the JSON blob from `input_value`.
2. **JSON Parse** — deserializes into `{driver, destinations, lookups}`. On parse failure, routes to error output.
3. **Prompt Builder** — assembles the system prompt (see below) with the parsed schemas interpolated.
4. **LLM node** — uses org-scoped `assistant.provider` / `assistant.model` / `assistant.api_key` Variables. No model hardcoded.
5. **Output cleaner** — strips markdown fences, extracts the first balanced JSON array, validates each entry matches the `MappingEntry` shape at the structural level (does not verify that referenced inputs/fields exist — that's the frontend's job).
6. **Chat Output** — emits the JSON string.

### 2. System prompt strategy

Lives inside the flow's prompt-builder node. Content:

- Describes the task: "For each destination field in the input, propose a mapping. Output a JSON array of `MappingEntry` objects and nothing else."
- Enumerates the allowed vocabulary: `transform ∈ {direct, static, variable, template, array}`. **`expression` is explicitly excluded** — the LLM is instructed never to emit it.
- Includes 2–3 few-shot examples showing when to pick each non-direct transform (e.g., `full_name = "{first_name} {last_name}"` for `template`; `source = "adp"` for `static`).
- Hard instruction: "If a destination is ambiguous or you are unsure, omit it from the output. Never guess." (Explicit permission to skip produces cleaner output than trying to get the LLM to refuse.)
- Sample embedding: per `InputDef.sample` in the config schema, `sample` is either a single dict (one record) or a list (many records) or null. When present, embed up to 5 values per field, each truncated to 200 characters: for a dict sample that's at most 1 value per field; for a list sample take the first 5 records and pull each field's value. Fall back to schema-only when `sample` is null or `.fields` has no matching keys.
- Final guard: "Do not include `expression` as a transform type under any circumstances."

### 3. The output cleaner is non-negotiable

LLMs wrap JSON in markdown fences (` ```json ... ``` `) roughly 20% of the time despite explicit instruction not to. The cleaner is two small steps:
1. Regex-strip fences if present.
2. Find the first balanced `[...]` region.
3. `json.loads` the result.

If all three fail, the flow emits `{"error": "unparseable_output"}` and the frontend surfaces a generic "Could not parse assistant output" message with a Retry action.

### 4. Input contract (the JSON blob)

```json
{
  "driver": {
    "alias": "users",
    "fields": [{"name": "first_name", "type": "str", "required": true}, ...],
    "sample": {"first_name": "Jane", "last_name": "Doe", ...}
  },
  "destinations": [
    {"name": "full_name", "type": "str", "required": true},
    ...
  ],
  "lookups": [
    {
      "alias": "profiles",
      "fields": [...],
      "sample": {...},
      "join_fields": [{"driver_field": "id", "lookup_field": "user_id"}]
    }
  ]
}
```

Only `driver.fields` and `destinations` are strictly required. `sample`, `lookups`, and `join_fields` are optional and the flow degrades gracefully when they are missing.

### 5. Output contract

```json
[
  {
    "destination": "full_name",
    "transform": "template",
    "sources": [{"input": "users", "field": "first_name"}, {"input": "users", "field": "last_name"}],
    "config": {"template": "{first_name} {last_name}"}
  },
  ...
]
```

The output is a JSON array of `MappingEntry` objects (see `src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py` for the authoritative Pydantic definition). The flow's cleaner validates structural conformance; the frontend validates semantic conformance (destination/input/field references exist; transform is not `expression`).

On flow-internal error: `{"error": "<code>", "detail": "<message>"}` instead of an array.

## Frontend

### 1. DataMapperModal contract extension

Four new optional props added to `DataMapperModal`, all backwards-compatible:

```ts
interface DataMapperModalProps {
  // ... existing Phase 1b props

  /** Proposed entries to render as highlighted "pending" rows. */
  pendingSuggestions?: MappingEntry[];

  /** Tab state for the Current/Suggested toggle. Default: true when pendingSuggestions is non-empty. */
  showPendingSuggestions?: boolean;

  /** Called when the user clicks ✓ on a pending row. */
  onAcceptSuggestion?: (destination: string) => void;

  /** Called when the user clicks ✗ on a pending row. */
  onRejectSuggestion?: (destination: string) => void;
}
```

Rendering rules inside `DestinationTable`:
- Destination rows whose `name` matches a `pendingSuggestions` entry, **and** `showPendingSuggestions === true`: render in the blue "pending" state — proposed `sources` / `transform` / `config` shown inline (greyed), with a ✓/✗ icon pair at row-end.
- Same rows with `showPendingSuggestions === false`: render as their underlying state (typically "(unset)").
- All other rows: render normally, unaffected by suggestion state.

### 2. State ownership

`MappingComponent` (the input renderer that opens the modal) is the single source of truth. It holds three new pieces of state:

- `pendingSuggestions: MappingEntry[]` — proposals still awaiting ✓/✗.
- `showPendingSuggestions: boolean` — tab toggle.
- `suggestionRequestState: "idle" | "fetching" | "pending" | "empty" | "error"` — drives which UX `<MappingSuggestions>` renders (see the state table in the Error handling section).

State flows down two paths: into `DataMapperModal` (for table rendering) and into `<MappingSuggestions>` via the `suggestionsSlot` prop (for the header chrome).

### 3. New files

Under `src/frontend/src/modals/dataMapperModal/`:

- `components/MappingSuggestions.tsx` — slot content. Stateless (receives everything via props from `MappingComponent`). Renders the right UX state: Suggest button / spinner / tab toggle / Apply-all / error chip.
- `hooks/useMappingSuggestions.ts` — fetch + SSE accumulation + parse + validate + never-overwrite filter. Returns `{run, cancel, state, entries, error}`. Uses `AbortController` for cancellation.
- `util/applyMappingSuggestion.ts` — pure: `(config: MapperConfig, entry: MappingEntry) => MapperConfig`. Jest-unit-testable.
- `util/filterEligibleSuggestions.ts` — pure: applies never-overwrite rule. Drops entries targeting destinations where the existing `MappingEntry` has any customization (non-direct transform, non-empty sources, or non-empty config). Jest-unit-testable.

Existing files to extend:

- `src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx` — accept the new props and branch render on pending rows.
- `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx` — own the three new state pieces; render `<MappingSuggestions>` into `suggestionsSlot`; pass pending props to the modal.

New query hook:

- `src/frontend/src/controllers/API/queries/assistant/use-data-mapper-auto-map.ts` — modeled on `use-template-assistant.ts`. POSTs to `/api/v1/session/DataMapperAutoMap/run` with `{input_value, input_type: "chat", output_type: "chat", stream: true}`. Returns the streaming response; the consumer accumulates tokens.

## Data flow (happy path)

1. User connects upstream inputs and defines destination schema in the modal.
2. User clicks "Suggest mappings" (in `<MappingSuggestions>` inside `suggestionsSlot`).
3. `MappingComponent`'s handler transitions `suggestionRequestState` from `"idle"` to `"fetching"`. `<MappingSuggestions>` renders a spinner + Cancel button.
4. `useMappingSuggestions` builds the JSON blob from the current draft (driver + destinations + lookups + whatever samples exist in flowPool or paste-sample state) and POSTs to `/session/DataMapperAutoMap/run`.
5. SSE stream accumulates. On `message_complete`, the accumulated text is parsed as JSON.
6. Parsed array is validated entry-by-entry: destination must exist in `destination_schema`; input/field refs must exist in `inputs`; transform must be in the allowed enum (not `expression`). Invalid entries dropped silently.
7. Remaining entries are filtered by `filterEligibleSuggestions` (drop any targeting customized destinations).
8. If any survive: `pendingSuggestions` is set; `showPendingSuggestions = true`; state transitions to `"pending"`. Tab toggle + Apply-all render.
9. If none survive (flow returned an empty array, or all entries were filtered out): state transitions to `"empty"` and a transient chip renders. State auto-returns to `"idle"` after ~4s or on any user action.
10. User hits ✓ on a row: `onAcceptSuggestion(destination)` → `MappingComponent` merges the entry into the draft config via `applyMappingSuggestion` **and** removes it from `pendingSuggestions`. Row turns from blue to plain.
11. User hits ✗ on a row: entry removed from `pendingSuggestions` without merging. Row returns to "(unset)".
12. User hits "Apply all suggestions": every remaining pending entry is merged; `pendingSuggestions` is cleared; tab toggle + Apply-all disappear.
13. Modal returns to normal editing state. User saves as usual.

## Error handling

### Backend-originated errors (flow emits `{"error": "<code>"}`):

| Code | Cause | User-facing message |
|---|---|---|
| `invalid_input` | Client sent malformed JSON blob | (should never happen; treated as generic error) |
| `llm_unavailable` | Provider rate limit / auth / downtime | "Auto-mapping is temporarily unavailable. Try again in a moment." |
| `unparseable_output` | LLM output failed all three cleaner strategies | "Could not parse assistant output. Retry?" |

### Frontend-originated errors:

| Condition | User-facing message |
|---|---|
| HTTP 404 on `/session/DataMapperAutoMap/run` | "Auto-mapping isn't available in this environment. Ask your admin to update Langflow." |
| HTTP 401/403 | Standard Langflow auth error. |
| Assistant config missing (detected via error payload) | "Auto-mapping requires an assistant API key. Configure it in Settings → Assistant." |
| Network error / connection drop | "Connection lost. Retry?" |
| Client-side timeout (default 60s) | "Auto-mapping took too long. Retry?" |
| Valid JSON, wrong shape / hallucinated references / `expression` transform | Entries dropped silently. No user notification. |
| Zero entries after filtering | "No new suggestions — the assistant couldn't find matches for the remaining destinations." Transient chip. |

### UX states `<MappingSuggestions>` cycles through:

| State | What renders |
|---|---|
| `idle` | "Suggest mappings" button. Disabled when every destination is customized (tooltip: "Clear a row to get suggestions"). |
| `fetching` | Spinner + "Analyzing schemas…" + Cancel button (aborts the SSE via `AbortController`). |
| `pending` | Tab toggle (Current / Suggested (N)) + "Apply all suggestions" button. |
| `error` | Inline error chip with user-facing message + Retry button. Clears on Retry or next successful fetch. |
| `empty` | Transient "No new suggestions" chip. Auto-dismisses after ~4s or on any user action. |

### Pending-suggestions ↔ Save interaction

Pending rows are **local preview state**. They do not count toward required-field validation. Clicking Save with pending suggestions discards them implicitly (equivalent to ✗-ing all). No confirm dialog — the blue rows are visible; if the user wanted them, they would have ✓-ed them. Save semantics are unchanged from Phase 1b.

### Cancel-during-fetch

`AbortController` aborts the SSE. State reverts to `idle`. The hook never exposes a partial `pendingSuggestions` — consumers see either a complete validated array or nothing.

## Testing

**Backend.** Verify `DataMapperAutoMap.json` is auto-discovered by `load_agentic_flows()` (extend the existing loader test if present, otherwise add one). Add an endpoint test that POSTs to `/session/DataMapperAutoMap/run` with a fixture blob, mocks the LLM provider at the `AnthropicProviderClient` / `OpenAIProviderClient` layer, and asserts the flow returns a validated `MappingEntry[]` JSON string. Test both the happy path and the output-cleaner fallback (markdown-fenced LLM response still parses).

**Frontend — Jest.** Pure-module coverage for `filterEligibleSuggestions.ts` (every branch of the never-overwrite rule) and `applyMappingSuggestion.ts` (merge against a fresh config, against an existing default entry, against absent entries). `useMappingSuggestions.ts` state machine tested with a mocked fetch returning: valid JSON array; markdown-fenced JSON (should still parse after cleaner); invalid JSON (should error); zero-entry array (should enter empty state); 404; AbortController cancellation. Component tests for `MappingSuggestions.tsx` across all five UX states and for `DestinationTable.tsx`'s blue-row rendering when `pendingSuggestions` is non-empty.

**Frontend — Playwright.** New spec at `src/frontend/tests/core/unit/dataMapperAutoMapping.spec.ts`. Route-intercept `/session/DataMapperAutoMap/run` with canned responses. Scenarios: happy path (Suggest → Apply-all → Save verifies serialized `mapping_config`); per-row ✓ merges one entry; per-row ✗ removes without merging; error state with Retry; "all customized → button disabled" tooltip; Cancel during fetch returns to idle.

## Risks

- **LLM output variance.** Structured-JSON LLM calls are generally reliable but not deterministic. The output cleaner catches the common misbehaviors (markdown fences, trailing prose, leading commentary); anything more exotic surfaces as "unparseable_output." Retry is the user's escape hatch. Mitigation: start with a conservative prompt + few-shot examples; tune in-flow (no backend release) based on real usage.
- **Assistant not configured per org.** Orgs without `assistant.api_key` configured will hit a confusing error path. The frontend detects this from the flow's error payload and surfaces a specific message pointing at Settings → Assistant. This is the same failure mode TemplateAssistant has today — we inherit its UX.
- **Model cost & latency.** Using the org's default model for structured output may be slower/more expensive than needed (Opus overkill for enum selection). Mitigation: if this turns out to matter in practice, the flow itself is the tuning dial (pin a specific tier). No contract change needed.
- **Modal cognitive load.** Adding a tab toggle + banner + blue rows is net-new UI. Mitigation: the hybrid design (header chrome from Option C, content from Option A) was validated in brainstorming; per-row ✓/✗ matches the code-review paradigm users already understand.
- **Flow-seeding drift.** Deployments on older Langflow versions won't have `DataMapperAutoMap.json`. Mitigation: the 404 error path is explicit and user-facing; "Ask your admin to update" points them at the resolution.

## Open questions

1. **How are existing shipped flows (TemplateAssistant / SystemMessageGen / LangflowAssistant) tested?** Need to check the pattern before finalizing the backend test approach. Plan-level concern.
2. **Model selection default.** Flow uses org-configured `assistant.model`. Should it override to a specific tier (e.g., force Sonnet) for structured JSON output? Lean: use org config; revisit if quality or latency issues appear post-ship.
3. **Where precisely in the modal header does `<MappingSuggestions>` render?** Phase 1b README says "above the destination table." The hybrid UX assumes the slot owns the full header region (tab toggle on the left, Apply-all on the right). Confirm the slot's current render location supports this layout, or widen it as part of this work.
