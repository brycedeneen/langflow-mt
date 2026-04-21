# Save as Template — Frontend Phase 1

**Date:** 2026-04-20
**Status:** Design
**Scope:** Frontend for creating new templates in the UI (connects to the already-shipped `/api/v1/templates` backend)

## 1. Context

The Template Management Phase 1 **backend** landed on `platform-multi-tenant` at commit `654ff9ad4f`: `Template` SQLModel, additive alembic migration (`bb45fc63cdcd`), `/api/v1/templates` CRUD router with 5 endpoints (list, get, create, update, delete), superuser-only, 13 tests passing.

No frontend entry point exists today. This spec defines the minimal UI to let a superuser save the current flow as a template — the user's explicitly stated goal: "create new templates in the UI."

A prior stale branch (`feat/template-management-phase-1`, retired) carried a `SaveAsTemplateModal` nested under `modals/AssistantPanel/`. Its 5 query hooks + TypeScript types will be ported (they're pure API glue); its modal will be **rebuilt fresh** at `modals/SaveAsTemplateModal/` (top-level), decoupled from the AssistantPanel context.

## 2. Goals

- **G1.** A superuser on any flow canvas can click Share → "Save as Template" and create a new Template row via `POST /api/v1/templates` — without leaving the flow.
- **G2.** Credentials (PEMs, API keys, password-typed fields, any `auto_promote: true` field, any `__autosecret_` reference) are **automatically stripped from the template's `nodes` JSON** before submission. Template consumers supply their own credentials.
- **G3.** Users see *what* is being stripped (transparency) even if they can't control it yet.
- **G4.** Minimum metadata capture for catalog rendering: name, description, icon, gradient — matching how `TemplateCardComponent` already consumes template data.
- **G5.** Ship the smallest surface that delivers a usable "create template" flow. Anything more sophisticated (per-field toggles, overwrite confirm, non-superuser auth, template editing, catalog integration) is deferred.

## 3. Non-goals

- Per-field blank/keep control in the review panel — it's read-only in Phase 1.
- Overwrite confirmation on name collision — Phase 1 errors the user back to re-enter.
- Template editing (`PUT`) and deletion (`DELETE`) via UI — backend supports them; frontend doesn't expose.
- Catalog gallery showing templates from the new endpoint — gallery still reads starter projects.
- Non-superuser template creation permissions.
- Cleaning up the author's Variable rows after template creation — the author's original Variables remain on their own flow untouched. Template consumers get blank fields and supply their own.
- Icon / gradient picker polish (search-as-you-type with fuzzy rank, custom icon upload, etc.) — Phase 1 ships static picker grids.

## 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | UI entry point | Share dropdown, between Export and MCP Server, superuser-only |
| Q2 | Reuse stale branch or rebuild | Port 5 query hooks + types verbatim; rebuild modal fresh (top-level `modals/`, not AssistantPanel-nested) |
| Q3 | Field-review UI | Auto-blank credentials + collapsible read-only "What gets stripped?" list (no per-field toggles in Phase 1) |
| Q4 | Name collision | Backend returns 409 → UI shows inline error on Name field, user retypes. No overwrite flow. |
| Q5 | Metadata captured on create | Name (required) + description + icon + gradient |
| Q6 | Icon / gradient pickers | Reuse existing `gradients` array from `src/frontend/src/utils/styleUtils.ts` + `fontAwesomeIcons` library; build two small local picker components (grid swatches for gradient, searchable grid for icon) |
| Q7 | After-success behavior | Success toast + modal closes; user stays on flow canvas |

## 5. Architecture overview

Six units, all in frontend:

1. **API query hooks + types** — port verbatim from stale branch (retired). `src/frontend/src/controllers/API/queries/templates/` (`use-list-templates.ts`, `use-get-template.ts`, `use-create-template.ts`, `use-update-template.ts`, `use-delete-template.ts`, `index.ts`) and `src/frontend/src/types/template/index.ts`. Verbatim port — hooks are mechanical wrappers over the endpoints we just shipped.

2. **`SaveAsTemplateModal`** — new top-level component at `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`. Single-page form. Handles its own state machine (idle / submitting / error-inline / error-toast / success-close).

3. **`IconPickerField`** — local picker component at `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx`. Renders the current icon + "Change" button that opens a searchable popover of `fontAwesomeIcons`. Stores the selected icon name string.

4. **`GradientPickerField`** — local picker at `src/frontend/src/modals/SaveAsTemplateModal/GradientPickerField.tsx`. Renders the existing `gradients` array as a 4×3 grid of swatches. Click to select. Stores the selected index as a string (matches how `TemplateCardComponent` parses it).

5. **`credentialBlankingUtils`** — small helper module at `src/frontend/src/modals/SaveAsTemplateModal/credentialBlanking.ts` (or a shared util location if one fits). Walks a flow's `nodes` template dicts and returns `{cleaned_nodes, blanked_fields}`. Pure function — no React, easy to unit-test.

6. **Share-dropdown menu-item insertion** — tiny edit to the Share dropdown component (exact path verified at implementation time; expected `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx` or nearest equivalent on current main). New menu item "Save as Template" inserted between Export and MCP Server, conditionally rendered when `currentUser.is_superuser` is `true`, opens `SaveAsTemplateModal`.

## 6. Modal UX

### 6.1 Layout (top-to-bottom)

1. **Name** — required text input, autofocus on modal open, `maxLength={255}`, placeholder "e.g. Customer Support Agent". Client-side validation: non-empty after trim.
2. **Description** — optional textarea, 3 rows, `maxLength={1000}`, prefilled from the current flow's `description` if it has one (editable).
3. **Icon** — `IconPickerField`. Default "FileText" (matches `TemplateCardComponent`'s fallback).
4. **Gradient** — `GradientPickerField` inline as a 4×3 swatch grid. Default to first entry (index "0") if user doesn't pick.
5. **Collapsible "What gets stripped?"** — closed by default. Expand shows a bulleted list `{component display_name} — {field display_name}` for every field the blanking scan will clear. Read-only.
6. **Footer** — "Cancel" (secondary) + "Save as Template" (primary, disabled while Name is empty or submitting).

### 6.2 State machine

| State | Trigger | Effect |
|---|---|---|
| `idle` | User edits fields | Name validity drives Save button enabled state |
| `submitting` | User clicks Save | Inputs disabled, spinner on button, `POST /api/v1/templates` in flight |
| `idle` (success) | 201 response | Toast "Template 'X' saved", modal closes, user stays on flow canvas |
| `idle` (name collision) | 409 response | Inline error on Name input: "A template with that name already exists — pick a different one". Button re-enables. |
| `idle` (other error) | 4xx (not 409) / 5xx / network | Generic error toast. Button re-enables for retry. |

### 6.3 Request payload

```json
{
  "name": "Customer Support Agent",
  "description": "A starter flow for triaging support tickets.",
  "icon": "FileText",
  "gradient": "0",
  "nodes": [/* cleaned copy from credentialBlankingUtils */],
  "edges": [/* current flow edges, unchanged */]
}
```

`scope` defaults to `"platform"` server-side; `org_id` remains null (Phase 1 reserved for Phase 2). `created_by` / `updated_by` are set server-side from the authenticated superuser.

## 7. Credential blanking

### 7.1 Blanking rule

Walk every node in `flow.data.nodes`. For each `data.node.template[field_name]` entry that is a dict:

- If any of the following conditions is true, blank the field:
  - `field["_input_type"]` is in the explicit set `{"SecretStrInput", "TextFileSecretInput", "MultilineSecretInput"}` (exact match, not suffix-based — prevents false positives on future unrelated `*Input` names)
  - `field.get("auto_promote") is True`
  - `field.get("password") is True`
  - `field.get("value")` is a string that starts with `"__autosecret_"`
- **Blanking** = set `value` to `""` and `load_from_db` to `false`.
- Record the blanked field for the "What gets stripped?" list as `{node_id, component_display_name, field_name, field_display_name}`.

The walker returns:
```ts
{
  cleaned_nodes: FlowNode[],   // deep-copied flow.data.nodes with credential values blanked
  blanked_fields: BlankedField[],  // metadata for the "What gets stripped?" list
}
```

### 7.2 Why this rule set

The union covers the three ways credentials surface in Langflow flow data today:
- **Typed-secret class** — `_input_type` name tells us (every SecretStr subclass).
- **Opt-in flag** — `auto_promote: true` (default on all SecretStrInput after recent work; gets set explicitly by component authors who want silent encryption).
- **Masking hint** — `password: true` (legacy signal from pre-auto-promote components).
- **Runtime reference** — values starting with `"__autosecret_"` are references to hidden Variables owned by the current user. These can't resolve for template consumers, so blanking them prevents broken template instantiation.

### 7.3 What the walker does NOT do

- It does not mutate the original flow (deep-copies before walking).
- It does not call any API or touch the author's Variables (those remain in the author's Variable store, still valid for the author's original flow).
- It does not scan `flow.data.edges` — edges are pure topology, contain no secrets.
- It does not try to detect "probably a secret" heuristically (length, high entropy, etc.). Only explicit markers are blanked — reducing false positives.

## 8. Testing

### 8.1 Credential-blanking unit tests

`src/frontend/src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts`:

- Blanks `_input_type: "SecretStrInput"` with `auto_promote: true`
- Blanks `_input_type: "TextFileSecretInput"`
- Blanks `password: true` fields regardless of input type
- Blanks `value: "__autosecret_..."` references
- Leaves normal text fields (StrInput, MessageTextInput with plain values) untouched
- Blanking sets `value: ""` and `load_from_db: false`
- Returns correct `blanked_fields` list for a multi-node fixture
- Does not mutate the original flow (input untouched after call)

### 8.2 Modal component tests

`src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` (Jest + Testing Library, mirroring existing modal tests' patterns):

- Renders all fields with initial defaults (empty name, empty/prefilled description, default icon "FileText", gradient index "0")
- Autofocus lands on Name input
- Name required: Save button disabled while Name is empty
- Description prefill: flow fixture with `description` → that value appears in the textarea
- IconPickerField opens + selection updates displayed icon
- GradientPickerField swatch click updates selected gradient
- "What gets stripped?" collapse: closed by default; expanded shows correct bullet list for a flow fixture with one PEM field
- Submit calls the create-template mutation with the expected payload (blanked nodes, current edges)
- 409 response → inline name error appears, Save button re-enables
- 5xx response → error toast fires, modal stays open
- Success → toast + `onClose` callback fires

### 8.3 Picker component tests

Keep minimal; verify open/close behavior and onChange propagation. Can be absorbed into the modal test if the components are tiny enough.

### 8.4 Integration / end-to-end

Not in scope for Phase 1. Backend integration tests already cover the CRUD endpoints. A manual smoke test before merging: load a flow with credentials → click Share → Save as Template → supply name → save → verify template row exists in the DB + "What gets stripped?" shows the credential fields.

## 9. Share-dropdown integration

### 9.1 Menu-item insertion

The Share dropdown lives inside `deploy-dropdown.tsx` (or equivalent on current main — implementer verifies exact path and component structure). The implementer:

1. Finds the dropdown's menu-item list.
2. Inserts a new `<DropdownMenuItem>` between the existing "Export" and "MCP Server" entries.
3. Labels it "Save as Template".
4. Uses an icon consistent with sibling entries (e.g., `FileText` or similar from lucide-react).
5. Wraps the entry in a conditional that checks `useAuthStore((state) => state.currentUser?.is_superuser)` (or whichever selector the auth store exposes).
6. On click, opens the `SaveAsTemplateModal` via local modal state or existing modal-routing machinery.

### 9.2 If the path differs

If the Share dropdown on current main is structured differently (a separate component, a different menu library, the menu items live in a constants file), the implementer adapts — the requirement is the visible outcome ("new menu item appears, gated on superuser, opens modal"), not a specific code path.

## 10. Scope boundaries (Phase 1.5 / Phase 2 backlog)

Deferred explicitly, tracked in the corresponding implementation plan as follow-ups:

- **Per-field blank/keep toggles.** Enable power users to keep specific credentials (e.g., non-sensitive API keys they want bundled). Requires turning the "What gets stripped?" collapse into an interactive table. Medium effort.
- **Name-collision overwrite flow.** On 409, show "Overwrite existing template?" confirm dialog → `PUT /api/v1/templates/{id}` instead of POST. Requires second modal + fetching the existing template's id. Small-to-medium effort.
- **Catalog gallery integration.** Existing gallery reads from starter-projects folder. Point it at `GET /api/v1/templates` as a second source (or replace entirely). Medium-to-large effort depending on how migration from starter projects is handled.
- **Edit / delete templates from UI.** Admin page listing templates with edit + delete actions. Medium effort.
- **Non-superuser authoring permission.** Per-user flag in User model + backend check + UI gating. Medium effort.
- **Richer pickers.** Icon search-as-you-type, custom uploaded icons, custom gradient colors. Polish; defer until Phase 1 ships and we see real usage.
- **Interactive blanking review.** Add entropy-based heuristics, preview of what the template will look like when instantiated. Pure polish.

## 11. Risks

- **R1. Share dropdown location drift.** The dropdown component's exact path on current main may differ from the stale branch's reference (`deploy-dropdown.tsx`). Mitigation: implementer verifies during implementation; adapts to current structure without changing spec intent.
- **R2. `is_superuser` selector mismatch.** If the auth store exposes the field under a different name (e.g. `isSuperuser`, `role === "admin"`), the implementer uses the correct selector. Low-risk adjustment.
- **R3. Blanking misses a credential pattern.** If Langflow introduces a new secret-input type after this ships, templates could leak credentials until the blanking rule list is updated. Mitigation: centralize the rule in `credentialBlanking.ts`; add tests for each current input type; flag new secret types for review in a lint check (future).
- **R4. `fontAwesomeIcons` list is long.** The picker popover could be sluggish without pagination/virtualization. Mitigation: Phase 1 uses a simple grid with static filter-as-you-type; add virtualization only if users complain.
- **R5. Prefilled description being the current flow's description** may embed internal-only wording a template author doesn't want exposed. The field is editable in the modal — user can clean it up before saving.

## 12. Implementation plan

Out of scope for this spec. Plan will be written next via `superpowers:writing-plans` and saved to `docs/superpowers/plans/`.
