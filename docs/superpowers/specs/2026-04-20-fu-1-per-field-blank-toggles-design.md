## FU-1 — Per-field Blank/Keep Toggles

**Date:** 2026-04-20
**Status:** Design
**Scope:** Frontend rewrite of the "What gets stripped?" panel inside `SaveAsTemplateModal`. No backend changes.
**Parent spec:** [`2026-04-20-save-as-template-frontend-design.md`](./2026-04-20-save-as-template-frontend-design.md) §10 (FU-1)

---

### 1. Context

The Save-as-Template modal currently scans the source flow for credential-shaped fields (`scanBlankableFields.ts`) and shows a read-only collapsible list of every field it will blank server-side. The backend (`POST /api/v1/templates`) already accepts an arbitrary `blanked_fields: list[BlankedField]` — it blanks exactly the fields the client tells it to. The frontend just always sends the full detected list today.

FU-1 turns that read-only list into per-field interactive toggles, so a superuser can opt out of blanking specific fields (e.g., a non-sensitive shared API key the author wants bundled into the template) before submitting.

This is a frontend-only change.

### 2. Goals

- **G1.** Inside the existing collapsible panel, render the detected credential fields as labeled checkboxes the user can toggle.
- **G2.** All fields default to "blank" (checked); user opts out per field.
- **G3.** Group field rows under their owning component header (alphabetical by component name).
- **G4.** Show a persistent inline warning whenever the user has opted to keep ≥1 field, both in the closed `<summary>` line and inside the open panel.
- **G5.** Submit only sends the user-chosen subset to `POST /api/v1/templates`; backend behavior unchanged.

### 3. Non-goals

- Save-time confirmation dialog. The persistent warning is the safeguard.
- Master "select all / strip all" toggles (per-component or global). YAGNI for typical 1-10 field counts.
- Severity / reason indicators per field (e.g., "matched because: auto_promote=true"). Keep the rows minimal.
- Persisting the user's per-field choices across modal opens. Each open starts fresh.
- Backend changes — the API already accepts a free-form blank list.

### 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | Default state of each field | All blanked (checked) — user opts out by exception |
| Q2 | UI layout | Grouped by component |
| Q3 | Save-time safeguard | Inline warning, no confirm dialog |
| Q4 | Component groups collapsible? | No — non-collapsible component headers, always-visible field rows |

### 5. UI

#### 5.1 Closed `<summary>` line

The panel's summary line replaces today's `What gets stripped? ({N})` with a status that reflects the kept-vs-blanked split:

| State | Summary content |
|---|---|
| All N fields blanked (default) | `What gets stripped (N)` |
| 0 fields blanked, all N kept | `⚠ N credentials will be saved with this template` |
| K of N kept | `What gets stripped (B of N)` plus `⚠ K credentials will be saved` |
| N=0 (no credentials detected) | `What gets stripped (0)` (panel still expandable; reveals empty state) |

Where `B = N - K`. The warning uses a `text-yellow-600` color token plus an `<AlertTriangle>` icon from lucide. The summary stays inside the existing `<details>` `<summary>` element so the user can expand-to-edit.

#### 5.2 Open panel body

```
▾ What gets stripped (3 of 5)
   ⚠ 2 credentials will be saved with this template

   OpenAI
     [✓] API Key
     [✓] Org ID
   Pinecone
     [✗] Index API Key
   Webhook
     [✓] HMAC Secret
     [✗] Bearer Token
```

- Component header: `text-sm font-medium`, no leading affordance (not collapsible).
- Field rows: `<label>` wrapping a `<input type="checkbox">` and the field's `field_display_name`. Indented under the component header.
- Default state: every checkbox `checked={true}` when the field's key is NOT in `keptFieldKeys`.
- Component groups: alphabetical by `component_display_name`.
- Field rows within a group: scan-insertion order (i.e., `Object.entries(template)` iteration order — stable for a given flow).
- Warning row inside the open body: same copy and treatment as the summary warning, repeated for emphasis since users who open the panel lose the closed-summary view.

#### 5.3 Empty state

When `fields.length === 0`, render the existing `No credential fields detected.` italic line. No checkboxes, no warning, no header count beyond `(0)`.

### 6. State and data flow

#### 6.1 Component state

`SaveAsTemplateModal/index.tsx` adds one new state slot:

```ts
const [keptFieldKeys, setKeptFieldKeys] = useState<Set<string>>(new Set());
```

The key format is `${node_id}:${field_name}` — the same composite the existing rendering loop already uses for React keys.

#### 6.2 Reset

The existing `useEffect` that resets the modal on `open=true` adds `setKeptFieldKeys(new Set())` to its body. Closing the modal effectively resets state via this same effect on re-open.

#### 6.3 Toggle handler

```ts
const toggleField = useCallback((node_id: string, field_name: string) => {
  setKeptFieldKeys((prev) => {
    const next = new Set(prev);
    const key = `${node_id}:${field_name}`;
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
}, []);
```

#### 6.4 Submit transformation

The existing `handleSubmit` builds the `blanked_fields` payload with:

```ts
const blanked_fields: BlankedField[] = blankableFields.map((f) => ({
  node_id: f.node_id,
  field_name: f.field_name,
}));
```

After FU-1, this filters first:

```ts
const blanked_fields: BlankedField[] = blankableFields
  .filter((f) => !keptFieldKeys.has(`${f.node_id}:${f.field_name}`))
  .map((f) => ({ node_id: f.node_id, field_name: f.field_name }));
```

If the user kept every field, `blanked_fields` is `[]` — the backend persists the template with the full nodes JSON intact. By design (Q3:B trusts the user once warned).

### 7. Component decomposition

| File | Status | Purpose |
|---|---|---|
| `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` | modify | Add `keptFieldKeys` state, reset, toggle, filtered submit. Replace inline `<details>` body with `<StripPanel>`. |
| `src/frontend/src/modals/SaveAsTemplateModal/StripPanel.tsx` | new | Stateless component. Owns rendering of summary, warning, grouped checkbox list, and empty state. |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx` | new | Unit-level component tests for StripPanel. |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` | modify | Add 3 integrated tests covering submit-with-kept-fields and reset-on-reopen. |

`StripPanel` is pulled out for two reasons: it has real logic (grouping + summary computation + warning), and `index.tsx` already sits at ~200 lines — extracting keeps that file focused on form orchestration.

#### 7.1 `StripPanel` props

```ts
type Props = {
  fields: BlankableFieldInfo[];
  keptKeys: Set<string>;
  onToggle: (node_id: string, field_name: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};
```

The parent owns the open/closed state (lifted from today's `detailsOpen`) so the modal-reset effect can collapse the panel on re-open.

### 8. Testing

Jest + React Testing Library, mirroring patterns already in the modal's existing test files.

#### 8.1 `StripPanel` unit tests

- Renders the empty state line `No credential fields detected.` when `fields=[]`; no warning, no checkboxes.
- Summary text reads `What gets stripped (N)` when `keptKeys` is empty.
- Summary text reads `What gets stripped (B of N)` when 1 ≤ K < N fields are kept.
- Summary text reads only the warning (no count) when all N fields are kept (K = N).
- Warning row with `role="alert"` is rendered when K ≥ 1; absent when K = 0.
- Component groups render alphabetically by `component_display_name`.
- Within a component group, field rows render in input-array order.
- Each field row renders a labeled checkbox; default `checked={true}` when its key is not in `keptKeys`.
- Field rows whose key is in `keptKeys` render `checked={false}`.
- Clicking a checkbox calls `onToggle(node_id, field_name)` exactly once with the right args.
- `open={false}` keeps the body collapsed; `open={true}` reveals it.
- Toggling the `<details>` calls `onOpenChange(true|false)`.

#### 8.2 `SaveAsTemplateModal` integration tests (additions)

- Render with a flow fixture containing ≥2 credential fields across ≥2 components. Open the panel, uncheck one field, click Save → the create-mutation receives `blanked_fields` that excludes the unchecked field's `{node_id, field_name}`.
- Same setup; uncheck a field, re-check it, then Save → the create-mutation receives the full `blanked_fields` list including that field.
- Open the panel, uncheck a field, close the modal, re-open it → the panel is closed and the now-checked-again field is again in the kept-by-default state.

### 9. Edge cases

- **All fields kept (user unchecks everything).** Submit fires with `blanked_fields: []`. Backend persists the template as-is. Already supported.
- **Flow `description` changes while the modal is open.** Existing reset effect already handles this; the new state slot follows the same pattern.
- **`keptFieldKeys` references a key not in current `blankableFields`.** The submit-time filter intersects against current `blankableFields`, so orphaned keys are silently ignored. No cleanup pass needed.
- **No credentials detected.** Empty state renders as today; the new state slot stays empty; the submit payload's `blanked_fields` is `[]` — same as today.

### 10. Risks

- **R1. Visual hierarchy of the warning.** The summary warning competes for attention with other modal elements (Name field validation, etc.). Mitigation: use a single distinct warning treatment (`text-yellow-600` + `<AlertTriangle>`) that doesn't appear elsewhere in this modal today.
- **R2. User loses per-field selections on Cancel.** Acceptable for Phase 1 — we don't persist partial template-creation drafts anywhere. If a user accidentally cancels, they re-open with the safe default and have to redo any opt-outs.
- **R3. Stale state if the source flow mutates mid-edit.** The modal already pulls `flow.data?.nodes` into a `useMemo` keyed on `flow.data?.nodes`, so a rebuild of the scan triggers naturally. The submit-time filter handles any orphaned keys.

### 11. Implementation plan

Out of scope for this spec. Plan will be written next via `superpowers:writing-plans` and saved to `docs/superpowers/plans/`.
