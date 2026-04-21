## FU-2 — Name-collision Overwrite Flow

**Date:** 2026-04-21
**Status:** Design
**Scope:** Frontend-only change inside `SaveAsTemplateModal`. Uses the backend `PUT /api/v1/templates/{id}` endpoint already shipped in Template Management Phase 1.
**Parent spec:** [`2026-04-20-save-as-template-frontend-design.md`](./2026-04-20-save-as-template-frontend-design.md) §10 (FU-2)

---

### 1. Context

Today a `POST /api/v1/templates` that hits a name collision returns 409, and the frontend surfaces an inline error on the Name input ("A template with that name already exists — pick a different one"). The user has to re-type or abandon.

The backend `PUT /api/v1/templates/{id}` has shipped, does a full replace of the row (name / description / icon / gradient / nodes / edges), and is already covered by a ready-to-use `useUpdateTemplate` query hook and a `useListTemplates` query hook — both ported during the Phase 1 work.

FU-2 turns the 409 into an actionable choice: show a confirm dialog with enough information to decide, then issue `PUT` on confirm or fall back to the inline error on cancel.

### 2. Goals

- **G1.** On 409 from the create mutation, open a `ConfirmOverwriteDialog` over the Save-as-Template modal.
- **G2.** The dialog surfaces the colliding template's name, description, and a relative last-updated timestamp so the user can decide whether to clobber it.
- **G3.** On confirm, issue `PUT /api/v1/templates/{id}` with the same payload shape used for create (source_flow_id, name, description, icon, gradient, blanked_fields).
- **G4.** On cancel (or when the template list isn't available at 409 time), fall back to today's inline name-error behavior.
- **G5.** Success uses a distinct "Template 'X' updated" toast (vs today's "saved").

### 3. Non-goals

- Backend changes (PUT already exists; list already returns everything we need).
- Counting flows created from a template in the dialog. Requires a new `source_template_id` column on `Flow` and new wiring — separate feature.
- Pre-emptive client-side name-collision detection as the user types. Scope creep; a separate UX improvement.
- Editing any template from anywhere else in the app (FU-4).
- Multi-step overwrite flows (e.g. "which fields to overwrite"). Full replace only.

### 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | Confirm UX | Second modal on top of the Save-as-Template modal |
| Q2 | Dialog contents | Name + description + relative last-updated |
| Q3 | List-fetch timing | Eager on modal open (fall back to inline error if not ready at 409 time) |

### 5. UX

#### 5.1 Steady-state flow (unchanged)

User fills the modal → Save → POST → 201 → success toast + close.

#### 5.2 409-collision flow

1. POST → 409.
2. Modal looks up `templatesList?.find((t) => t.name.trim() === attemptedName.trim())` against the result of the `useListTemplates` hook that fired on modal open.
3. **If found** → open `ConfirmOverwriteDialog`:

   ```
   Template "Customer Support" already exists
   ──────────────────────────────────────────
   Triage support tickets via a routing LLM
   then hand off to a human if escalation is needed.

   Last updated 45 days ago

                         [Cancel]  [Overwrite]
   ```

   - Description rendered as plain text with `line-clamp-3`; empty description renders italic `(no description)`.
   - Timestamp relative: "just now" / "N minutes ago" / "N hours ago" / "N days ago" / "on {date}" for >29 days (exact thresholds in §6.3).
   - Focus lands on **Cancel** (the safe option) so an errant Enter doesn't clobber.
   - Escape key and backdrop click = Cancel.
   - **Overwrite** button styled with the repo's destructive/warning token (matches other destructive confirmations in Langflow).

4. **On Cancel** → dialog closes, the Save-as-Template modal returns to today's state: the inline "A template with that name already exists — pick a different one" error on the Name input, Save button re-enabled.
5. **On Overwrite** → dialog closes, modal fires `PUT /api/v1/templates/{conflict.id}` with the same payload shape that would have been POSTed. Success → toast "Template 'X' updated" + modal closes. Error → generic error toast; modal stays open; dialog does not re-open.
6. **If the list fetch isn't ready by 409 time** (user submitted faster than the GET returned — rare) → dialog never opens. Fall back to today's inline error. User can click Save again; the list will almost certainly be ready by then.

#### 5.3 Button states during the dance

| Outer Save button | Confirm Overwrite button | Confirm Cancel button |
|---|---|---|
| Disabled while `createTemplate.isPending` | — | — |
| Disabled while confirm dialog is open | — | — |
| Disabled while `updateTemplate.isPending` | Disabled with spinner | Stays enabled (so user can abort a stuck request) |

### 6. Architecture

#### 6.1 New component: `ConfirmOverwriteDialog.tsx`

Stateless modal-on-modal. Props:

```ts
type Props = {
  open: boolean;
  templateName: string;
  description: string | null;
  updatedAt: string; // ISO
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};
```

Internals: BaseModal (or the repo's confirm-dialog primitive — implementer picks the right one after surveying what the rest of the codebase uses for destructive confirms), a header with the template name, body text as specified in §5.2, and a footer with Cancel + Overwrite buttons. Escape / outside-click = `onCancel`. `autoFocus` on Cancel. No business logic inside — the parent drives the PUT.

#### 6.2 Parent modal additions (`SaveAsTemplateModal/index.tsx`)

Three new state slots and two new hooks:

```ts
const { data: templatesList } = useListTemplates();
const updateTemplate = useUpdateTemplate();

const [confirmOpen, setConfirmOpen] = useState(false);
const [conflict, setConflict] = useState<TemplateRead | null>(null);
// existing nameError slot stays; used as the fallback when list isn't ready
```

Mutation payload is shared between create and update via an extracted `buildPayload()` helper so the two paths can't drift.

Reset-on-open extends to wipe `confirmOpen` and `conflict`.

#### 6.3 Relative-date utility

The dialog formats `updatedAt` relative to now. If the repo already has a `formatDistanceToNow` helper (via `date-fns` or a local util), use it. Otherwise a small local utility `formatRelativeTime(iso: string, now: Date = new Date()): string` with the following thresholds:

| Elapsed | Output |
|---|---|
| < 60s | `just now` |
| < 60m | `{N} minutes ago` (singular `1 minute ago`) |
| < 24h | `{N} hours ago` (singular `1 hour ago`) |
| < 30d | `{N} days ago` (singular `1 day ago`) |
| ≥ 30d | `on {locale date}` |

The implementer spot-checks for an existing helper during execution; if one exists, use it; don't create a duplicate.

#### 6.4 Create-error branch (pseudocode)

```ts
onError: (err) => {
  if (err?.response?.status !== 409) {
    setErrorData({ title: "Failed to save template", list: [...] });
    return;
  }
  const match = templatesList?.find(
    (t) => t.name.trim() === name.trim(),
  );
  if (match) {
    setConflict(match);
    setConfirmOpen(true);
    return;
  }
  // Fallback: list not ready
  setNameError("A template with that name already exists — pick a different one.");
}
```

#### 6.5 Overwrite handler

```ts
function handleOverwriteConfirm() {
  if (!conflict) return;
  updateTemplate.mutate(
    { templateId: conflict.id, body: buildPayload() },
    {
      onSuccess: () => {
        setSuccessData({ title: `Template "${name.trim()}" updated` });
        setConfirmOpen(false);
        setConflict(null);
        onClose();
      },
      onError: (err) => {
        setConfirmOpen(false);
        setConflict(null);
        setErrorData({
          title: "Failed to overwrite template",
          list: [err?.response?.data?.detail ?? "Please try again."],
        });
      },
    },
  );
}
```

#### 6.6 Cancel handler

```ts
function handleOverwriteCancel() {
  setConfirmOpen(false);
  setConflict(null);
  setNameError("A template with that name already exists — pick a different one.");
}
```

### 7. Testing

#### 7.1 `ConfirmOverwriteDialog` unit tests

- Renders template name in the header, description in the body, and a relative-date line.
- Empty/null description renders italic `(no description)`.
- Focus lands on Cancel after render.
- Escape key fires `onCancel`.
- Clicking Overwrite fires `onConfirm`.
- Clicking Cancel fires `onCancel`.
- Overwrite disabled when `submitting={true}`; Cancel stays enabled.
- `open={false}` renders no dialog DOM.

#### 7.2 `formatRelativeTime` unit tests (only if a new utility is added)

- 0s → "just now"
- 59s → "just now"
- 60s → "1 minute ago"
- 119s → "1 minute ago"
- 3599s → "59 minutes ago"
- 3600s → "1 hour ago"
- 86399s → "23 hours ago"
- 86400s → "1 day ago"
- 29d → "29 days ago"
- 30d → "on {localized date}"

#### 7.3 `SaveAsTemplateModal` integration tests (additions)

Four new tests. The file's existing mock for `useCreateTemplate` expands to also mock `useListTemplates` and `useUpdateTemplate`. Suggested mock shape:

```ts
const listMock = jest.fn();
const updateMock = jest.fn();
jest.mock("@/controllers/API/queries/templates", () => ({
  useCreateTemplate: () => ({ mutate: mutateMock, isPending: false }),
  useListTemplates: () => ({ data: listMock() }),
  useUpdateTemplate: () => ({ mutate: updateMock, isPending: false }),
}));
```

Tests:
1. **409 + matching row → confirm dialog opens with the right content.** Pre-seed `listMock` to return `[{id: "T-1", name: "Duplicate", description: "X", updated_at: "2026-04-01T…"}]`. `mutateMock` fires `onError({response: {status: 409}})`. Assert dialog visible, shows "Duplicate", shows "X", shows a relative-date string.
2. **409 + list not ready → inline error fallback.** `listMock` returns `undefined`. 409 fires. Assert the inline name error appears; no dialog.
3. **Overwrite confirm → PUT fires with correct payload.** From state #1, click Overwrite. Assert `updateMock` was called with `{templateId: "T-1", body: {source_flow_id, name, description, icon, gradient, blanked_fields}}`.
4. **Cancel → dialog closes, inline error shows, Save button re-enables.** From state #1, click Cancel. Assert dialog is absent, inline name error is visible, Save button is enabled.

### 8. Edge cases

- **User renames between 409 and Overwrite.** `conflict.id` is locked in when the dialog opened; the new name flows through `buildPayload()`. If the new name collides with a DIFFERENT existing row, PUT returns 409 → caught by the error branch → generic toast (no recursive confirm). Acceptable — user can abandon and retry.
- **Whitespace name comparison.** `name.trim()` on both sides of the `.find()` so " X " and "X" collide correctly.
- **Template soft-deleted between list fetch and PUT.** PUT returns 404. Generic error toast; modal stays open.
- **Modal closed mid-PUT.** `onSuccess`/`onError` may fire against a closed modal; toasts are global so they surface anyway. Acceptable.
- **Stale `templatesList` cache shows an older description/timestamp than reality.** Low cost; react-query refetches on focus. If the PUT itself 404s, we handle it via the error branch.

### 9. Risks

- **R1. Double-fire.** If the user manages to click Save twice before the first 409 returns, they could open two confirm dialogs. Mitigation: the Save button is disabled while `createTemplate.isPending`.
- **R2. Race: other user creates a row between our list fetch and our POST.** Our list doesn't know about the row. The 409 fires. `.find()` returns undefined. Fall back to inline error — user sees the accurate "already exists" message and retries. Correctness is intact.
- **R3. Help copy drift.** The fallback inline error and the confirm dialog's body text live in different places. If product ever wants to change phrasing, they have to be kept in sync. Low risk, worth a doc comment.

### 10. Implementation plan

Out of scope for this spec. Plan will be written next via `superpowers:writing-plans` and saved to `docs/superpowers/plans/`.
