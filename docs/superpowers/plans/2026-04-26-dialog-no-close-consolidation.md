# Dialog "no-close" consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse `ui/dialog-with-no-close.tsx` into `ui/dialog.tsx` by adding a `closable?: boolean` prop (default `true`), migrate the 2 callers, and remove the orphaned animation keyframes.

**Architecture:** Add the prop to canonical `DialogContent`; gate the existing Tooltip+Close block on it. Both call sites already override the canonical's padding/gap defaults, so the visual end-state matches; only the open/close motion changes (clip-path wipe → fade+zoom — adopted by user choice during brainstorming). After both callers migrate, delete the variant file and its 4 dead keyframes + 4 dead `@theme` tokens.

**Tech Stack:** React 18, Radix Dialog, Tailwind v4 (CSS-first config), Jest + Testing Library (frontend test stack), Vite, Biome.

**Standing rules (apply throughout):**
- Never push to `langflow-ai/langflow` (origin). Push only to `brycedeneen/langflow-mt` (fork).
- Ask the user before every `git commit` — even when this plan says to commit.
- All execution happens inside a worktree (`superpowers:using-git-worktrees`); the parent checkout has unrelated WIP.
- Subagents must stage explicit paths (no `git add -A`/`.`/`-a`).

**Reference spec:** `docs/superpowers/specs/2026-04-26-dialog-no-close-consolidation-design.md`

---

## File Map

- **Modify** `src/frontend/src/components/ui/dialog.tsx` — add `closable` prop + gate Close block.
- **Modify** `src/frontend/src/components/ui/__tests__/dialog.test.tsx` — add `closable={false}` test case.
- **Modify** `src/frontend/src/modals/baseModal/index.tsx` — drop the no-close imports, switch the `type === "modal"` branch to canonical `Dialog`/`DialogContent` with `closable={false}`.
- **Modify** `src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx` — switch the `Dialog`/`DialogContent` import source, add `closable={false}`.
- **Delete** `src/frontend/src/components/ui/dialog-with-no-close.tsx`.
- **Modify** `src/frontend/src/style/index.css` — delete keyframes at lines 199–234 and `@theme` tokens at lines 256–259 (line numbers as of HEAD).
- **Modify** `docs/superpowers/followups.md` — flip the Phase 7d follow-up checkbox to `[x]`.

---

## Task 0: Set up worktree

**Files:** none (creates a new worktree)

- [ ] **Step 1: Create worktree off `platform-multi-tenant`**

Use the `superpowers:using-git-worktrees` skill to create an isolated worktree. Branch name: `tailwind/dialog-consolidation`. Use the parent worktree's path style (peer of `review-tier1`, etc.).

- [ ] **Step 2: Verify clean working tree in the worktree**

Run from the worktree directory:

```bash
git status
git log --oneline -3
```

Expected: working tree clean (no modifications), `HEAD` is at `1db0d15cb6 docs(tailwind): spec for dialog-with-no-close consolidation` (the spec commit) or whatever current HEAD is on `platform-multi-tenant`.

- [ ] **Step 3: Verify the spec is present in the worktree**

```bash
ls docs/superpowers/specs/2026-04-26-dialog-no-close-consolidation-design.md
ls docs/superpowers/plans/2026-04-26-dialog-no-close-consolidation.md
```

Both files must exist (the worktree shares git history with the parent).

---

## Task 1: Add `closable` prop to `DialogContent` (TDD)

**Files:**
- Modify: `src/frontend/src/components/ui/dialog.tsx` (lines 53–134, the `DialogContent` definition)
- Test: `src/frontend/src/components/ui/__tests__/dialog.test.tsx` (append a new test case)

- [ ] **Step 1: Write the failing test**

Append to `src/frontend/src/components/ui/__tests__/dialog.test.tsx`, inside the existing `describe("DialogContent", ...)` block:

```tsx
  it("should_not_render_close_button_when_closable_is_false", () => {
    // Arrange — render with closable={false}
    renderWithProviders(
      <Dialog open>
        <DialogContent closable={false}>
          <DialogTitle>Test Dialog</DialogTitle>
          <DialogDescription>Test description</DialogDescription>
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );

    // Assert — no close button is rendered
    expect(
      screen.queryByRole("button", { name: /close/i }),
    ).not.toBeInTheDocument();
  });

  it("should_render_close_button_by_default", () => {
    // Arrange — render with default closable behavior (omit prop)
    renderWithProviders(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Test Dialog</DialogTitle>
          <DialogDescription>Test description</DialogDescription>
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );

    // Assert — close button is present
    expect(
      screen.getByRole("button", { name: /close/i }),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the failing test to verify it fails**

```bash
cd src/frontend && npx jest src/components/ui/__tests__/dialog.test.tsx -t "closable" --colors
```

Expected: `should_not_render_close_button_when_closable_is_false` **FAILS** (because `closable` prop is not yet supported and the close button still renders). The default-case test passes.

- [ ] **Step 3: Add `closable` prop to `DialogContent`**

Edit `src/frontend/src/components/ui/dialog.tsx`. Two surgical edits:

**(a) Add the prop to the type and destructure with default `true`** — replace lines 53–70:

```tsx
const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    hideTitle?: boolean;
    closeButtonClassName?: string;
    closable?: boolean;
  }
>(
  (
    {
      className,
      children,
      hideTitle = false,
      closeButtonClassName,
      closable = true,
      onOpenAutoFocus,
      ...props
    },
    ref,
  ) => {
```

**(b) Wrap the existing `<Tooltip>...</Tooltip>` block (lines 109–129 in the current file) with `{closable && (...)}`**. Replace:

```tsx
          {children}
          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <DialogPrimitive.Close
                className={cn(
                  "absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-sm ring-offset-background transition-opacity hover:bg-secondary-hover hover:text-accent-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground",
                  closeButtonClassName,
                )}
              >
                <Cross2Icon className="h-[18px] w-[18px]" />
                <span className="sr-only">Close</span>
              </DialogPrimitive.Close>
            </TooltipTrigger>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
              side="bottom"
              avoidCollisions={true}
              sticky="always"
            >
              Close
            </TooltipContent>
          </Tooltip>
        </DialogPrimitive.Content>
```

With:

```tsx
          {children}
          {closable && (
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <DialogPrimitive.Close
                  className={cn(
                    "absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-sm ring-offset-background transition-opacity hover:bg-secondary-hover hover:text-accent-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground",
                    closeButtonClassName,
                  )}
                >
                  <Cross2Icon className="h-[18px] w-[18px]" />
                  <span className="sr-only">Close</span>
                </DialogPrimitive.Close>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
                side="bottom"
                avoidCollisions={true}
                sticky="always"
              >
                Close
              </TooltipContent>
            </Tooltip>
          )}
        </DialogPrimitive.Content>
```

(Indentation: each line of the original Tooltip block gets two extra spaces because it's now nested inside the `{closable && (...)}` JSX expression.)

- [ ] **Step 4: Run the test suite for dialog to verify both tests pass**

```bash
cd src/frontend && npx jest src/components/ui/__tests__/dialog.test.tsx --colors
```

Expected: all tests in this file pass — both new ones plus the 2 pre-existing focus tests.

- [ ] **Step 5: Run typecheck on the frontend**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors. (Pre-existing warnings unrelated to dialog are acceptable; if a new dialog-related error appears, fix it before continuing.)

- [ ] **Step 6: Commit (gated on user approval)**

Show the user the diff:

```bash
git diff src/frontend/src/components/ui/dialog.tsx src/frontend/src/components/ui/__tests__/dialog.test.tsx
```

Then **ask the user** to approve the commit. Once approved:

```bash
git add src/frontend/src/components/ui/dialog.tsx src/frontend/src/components/ui/__tests__/dialog.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui): add closable prop to DialogContent

Default `true` preserves behavior for every existing caller. When
`closable={false}`, the Tooltip-wrapped ✕ close button is not rendered.
Tests assert both the default and the opt-out cases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If the user denies, do NOT amend or re-attempt — wait for instruction.

---

## Task 2: Migrate `baseModal` to canonical `DialogContent`

**Files:**
- Modify: `src/frontend/src/modals/baseModal/index.tsx` (lines 14–17, 291–300)

This task is independent of Task 3 and can be dispatched as a parallel subagent.

- [ ] **Step 1: Remove the no-close import block**

In `src/frontend/src/modals/baseModal/index.tsx`, delete lines 14–17:

```tsx
import {
  Dialog as Modal,
  DialogContent as ModalContent,
} from "../../components/ui/dialog-with-no-close";
```

- [ ] **Step 2: Switch the `type === "modal"` branch to canonical**

In the same file, replace lines 291–300 (the `type === "modal"` JSX block):

```tsx
      {type === "modal" ? (
        <Modal open={open} onOpenChange={setOpen}>
          {triggerChild}
          <ModalContent
            className={contentClasses}
            style={customHeight || customWidth ? customStyle : undefined}
          >
            {modalContent}
          </ModalContent>
        </Modal>
      ) : type === "full-screen" ? (
```

With (note: `Dialog` and `DialogContent` are already imported from `"../../components/ui/dialog"` higher in the file — line 5–13):

```tsx
      {type === "modal" ? (
        <Dialog open={open} onOpenChange={setOpen}>
          {triggerChild}
          <DialogContent
            closable={false}
            className={contentClasses}
            style={customHeight || customWidth ? customStyle : undefined}
          >
            {modalContent}
          </DialogContent>
        </Dialog>
      ) : type === "full-screen" ? (
```

- [ ] **Step 3: Verify no other reference to `Modal` / `ModalContent` survives in this file**

```bash
grep -n "\bModal\b\|\bModalContent\b" src/frontend/src/modals/baseModal/index.tsx
```

Expected: 0 matches (or only matches inside string literals / unrelated comments — verify by eye).

- [ ] **Step 4: Run typecheck**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 new errors related to this file.

- [ ] **Step 5: Run baseModal-adjacent tests**

```bash
cd src/frontend && npx jest src/modals/baseModal --colors
```

Expected: all tests pass (or the test directory doesn't exist — check first with `ls src/frontend/src/modals/baseModal/__tests__ 2>/dev/null`; if empty, run a broader sanity pass instead: `npx jest src/components/ui --colors`).

---

## Task 3: Migrate `ListSelectionComponent` to canonical `DialogContent`

**Files:**
- Modify: `src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx` (lines 7–8, 175–178)

This task is independent of Task 2 and can be dispatched as a parallel subagent.

- [ ] **Step 1: Consolidate the imports**

In `src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx`, replace lines 7–8:

```tsx
import { DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
```

With:

```tsx
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
} from "@/components/ui/dialog";
```

- [ ] **Step 2: Add `closable={false}` to `<DialogContent>`**

Replace the existing `<DialogContent>` opening tag (around lines 175–178):

```tsx
      <DialogContent
        className="flex max-h-[65vh] min-h-[15vh] flex-col overflow-hidden rounded-xl p-0"
        onKeyDown={handleKeyDown}
      >
```

With:

```tsx
      <DialogContent
        closable={false}
        className="flex max-h-[65vh] min-h-[15vh] flex-col overflow-hidden rounded-xl p-0"
        onKeyDown={handleKeyDown}
      >
```

- [ ] **Step 3: Verify the file no longer imports from `dialog-with-no-close`**

```bash
grep -n "dialog-with-no-close" src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx
```

Expected: 0 matches.

- [ ] **Step 4: Run typecheck**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 new errors related to this file.

- [ ] **Step 5: Run ListSelectionComponent-adjacent tests**

```bash
cd src/frontend && npx jest src/CustomNodes/GenericNode/components/ListSelectionComponent --colors
```

Expected: all tests pass (or directory has no tests — fall back to `npx jest src/CustomNodes --colors` for a broader sanity pass).

---

## Task 4: Commit caller migrations (combined commit)

**Files:** the staged outputs of Tasks 2 and 3 (no new edits in this task).

- [ ] **Step 1: Verify both files are dirty and the changes match the spec**

```bash
git diff --stat src/frontend/src/modals/baseModal/index.tsx \
                src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx
git diff src/frontend/src/modals/baseModal/index.tsx \
         src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx
```

- [ ] **Step 2: Run the broader frontend test suite for confidence**

```bash
cd src/frontend && npx jest src/components/ui src/modals src/CustomNodes/GenericNode --colors
```

Expected: all tests pass. If a test fails because of a snapshot involving the no-close variant, treat it as **expected**: update the snapshot only after eyeballing the diff and confirming the difference is exactly the documented motion change. Do NOT bulk `--updateSnapshot` blindly.

- [ ] **Step 3: Verify `dialog-with-no-close.tsx` now has zero source consumers**

```bash
grep -rn "dialog-with-no-close" src/frontend --include="*.ts" --include="*.tsx"
```

Expected: 0 matches.

- [ ] **Step 4: Commit (gated on user approval)**

Show the user the diff. After approval:

```bash
git add src/frontend/src/modals/baseModal/index.tsx \
        src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx
git commit -m "$(cat <<'EOF'
refactor(ui): migrate baseModal + ListSelectionComponent to canonical Dialog

Both surfaces switch from ui/dialog-with-no-close to ui/dialog with
`closable={false}`. Visual end-state is identical (centered modal, no ✕);
open/close motion changes from clip-path wipe to fade+zoom (the standard
the rest of the app uses) per the consolidation design.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Manual browser verification

**Files:** none (read-only verification step).

This task gates Task 6 (cleanup) — do not delete the variant file until manual verification passes.

- [ ] **Step 1: Start the dev server**

The repo's documented dev workflow lives in `Makefile`. Use `make dev` from the repo root if it works on your machine; otherwise start backend + frontend separately. For frontend-only verification (sufficient for this change), `cd src/frontend && npm run start` is enough — the dialogs render without backend interaction.

```bash
cd src/frontend && npm run start
```

The Vite dev server announces a localhost URL (typically `http://localhost:3000`).

- [ ] **Step 2: Find a `BaseModal type="modal"` consumer to exercise**

```bash
grep -rn 'type="modal"' src/frontend/src --include="*.tsx" | head -10
```

Pick one, navigate to it in the browser, and trigger it. Confirm:
- Modal centers on screen.
- Open animation = standard fade + zoom (NOT a clip-path wipe).
- Backdrop dims.
- **No ✕ close button** at top-right.
- `Esc` closes the modal.
- Click on backdrop closes the modal (unless the caller explicitly disables outside-click).

- [ ] **Step 3: Exercise `ListSelectionComponent` on the canvas**

Open any flow that has a node with a list-selection input (e.g., a tool-selection input on an Agent node). Click the input to open the list dialog. Confirm:
- Same checks as Step 2 (centering, animation, no ✕, Esc closes).
- **No pan/zoom of the canvas** while the dialog is open (the `nopan nodelete nodrag noflow` guards on the canonical Portal handle this).

- [ ] **Step 4: Sanity-check a `type="dialog"` (default) BaseModal somewhere else**

This path was untouched but uses the same `DialogContent`. Confirm a regular dialog (with a ✕) still renders the close button. Use any modal in Settings, the user-management modal, etc.

- [ ] **Step 5: Stop the dev server**

`Ctrl+C` in the terminal running Vite.

If any step fails, **stop and report** — do not proceed to Task 6. Cleanup is irreversible.

---

## Task 6: Cleanup — delete variant + dead keyframes + flip followup

**Files:**
- **Delete:** `src/frontend/src/components/ui/dialog-with-no-close.tsx`
- Modify: `src/frontend/src/style/index.css` (lines 199–234, 256–259)
- Modify: `docs/superpowers/followups.md` (the Phase 7d follow-up entry near the bottom)

- [ ] **Step 1: Delete `dialog-with-no-close.tsx`**

```bash
git rm src/frontend/src/components/ui/dialog-with-no-close.tsx
```

- [ ] **Step 2: Delete the 4 orphaned keyframes from `style/index.css`**

In `src/frontend/src/style/index.css`, delete lines 199–234 (the four `@keyframes` blocks: `overlayShow`, `overlayHide`, `contentShow`, `contentHide`). The exact block to remove:

```css
@keyframes overlayShow {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes overlayHide {
  from { opacity: 1; }
  to   { opacity: 0; }
}
@keyframes contentShow {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.95);
    clip-path: inset(50% 0);
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.1);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
    clip-path: inset(0% 0);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
}
@keyframes contentHide {
  from {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
    clip-path: inset(0% 0);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.95);
    clip-path: inset(50% 0);
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.1);
  }
}
```

Leave the surrounding `@keyframes wiggle`, `jiggle`, `border-beam`, `pulse-pink`, `text-shimmer` blocks intact.

- [ ] **Step 3: Delete the 4 dead `@theme` tokens**

In the same file, delete the four `--animate-*` tokens at lines 256–259. Find and remove these specific lines from the `@theme { ... }` block:

```css
  --animate-overlayShow: overlayShow 400ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-overlayHide: overlayHide 500ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-contentShow: contentShow 400ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-contentHide: contentHide 500ms cubic-bezier(0.16, 1, 0.3, 1);
```

Leave `--animate-wiggle`, `--animate-slow-wiggle`, `--animate-pulse-pink`, etc., untouched.

- [ ] **Step 4: Confirm zero residual references to the deleted symbols**

```bash
grep -rn "animate-contentShow\|animate-contentHide\|animate-overlayShow\|animate-overlayHide\|@keyframes contentShow\|@keyframes contentHide\|@keyframes overlayShow\|@keyframes overlayHide\|dialog-with-no-close" src/frontend
```

Expected: **0 matches**. If any match surfaces, stop and investigate before proceeding.

- [ ] **Step 5: Flip the followup checkbox in `docs/superpowers/followups.md`**

Find the entry "## 2026-04-26 — Tailwind Phase 7d follow-up: consolidate dialog-with-no-close" and change its single bullet from:

```markdown
- [ ] **`ui/dialog-with-no-close.tsx` is a near-copy of `ui/dialog.tsx` minus the close button.** Used by 2 surfaces (`modals/baseModal/index.tsx`, `CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx`). Consolidate by adding a `closable?: boolean` (default `true`) prop on `ui/dialog`'s `DialogContent`. When `closable={false}`, skip rendering the ✕ button. Then migrate the 2 callers to `ui/dialog` and delete `dialog-with-no-close.tsx`. Skipped during Phase 7d audit because the divergent fork was technically thin but the consolidation requires touching the much-used `ui/dialog`.
```

To:

```markdown
- [x] **RESOLVED (2026-04-26):** `ui/dialog-with-no-close.tsx` consolidated into `ui/dialog.tsx` via a `closable?: boolean` prop (default `true`). 2 callers migrated; orphaned `contentShow`/`contentHide`/`overlayShow`/`overlayHide` keyframes + `--animate-*` theme tokens deleted. See `docs/superpowers/specs/2026-04-26-dialog-no-close-consolidation-design.md` and plan `docs/superpowers/plans/2026-04-26-dialog-no-close-consolidation.md`.
```

- [ ] **Step 6: Run typecheck + dialog tests one more time**

```bash
cd src/frontend && npx tsc --noEmit && npx jest src/components/ui src/modals src/CustomNodes/GenericNode --colors
```

Expected: all green.

- [ ] **Step 7: Run lint on the touched files**

```bash
cd src/frontend && npx @biomejs/biome lint \
  src/components/ui/dialog.tsx \
  src/components/ui/__tests__/dialog.test.tsx \
  src/modals/baseModal/index.tsx \
  src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx \
  src/style/index.css
```

Expected: no errors. Warnings on pre-existing patterns are acceptable; new errors caused by this change are not.

- [ ] **Step 8: Commit (gated on user approval)**

Show the user the full diff:

```bash
git status
git diff --staged
git diff
```

After approval:

```bash
git add src/frontend/src/components/ui/dialog-with-no-close.tsx \
        src/frontend/src/style/index.css \
        docs/superpowers/followups.md
git commit -m "$(cat <<'EOF'
chore(ui): delete dialog-with-no-close + dead keyframes

After the 2 callers migrated to canonical `DialogContent` with
`closable={false}` (prior commit), the variant file is unreferenced
and its 4 keyframes (`overlayShow`, `overlayHide`, `contentShow`,
`contentHide`) plus the matching `--animate-*` `@theme` tokens are
dead. Flip the Phase 7d followup checkbox.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(`git rm` from Step 1 already staged the deletion; the explicit `git add` of the path is harmless and keeps the command symmetric.)

---

## Task 7: Integrate worktree branch + push to fork

**Files:** none (git operations only).

- [ ] **Step 1: Verify the worktree branch is ready**

From the worktree directory:

```bash
git log --oneline platform-multi-tenant..HEAD
```

Expected: 3 commits — `feat(ui): add closable prop`, `refactor(ui): migrate ...`, `chore(ui): delete dialog-with-no-close`.

- [ ] **Step 2: Switch to the parent checkout (platform-multi-tenant)**

`cd` to `/Users/brycedeneen/dev/langflow` (the primary worktree). Confirm the branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Expected: `platform-multi-tenant`.

- [ ] **Step 3: Stash any unrelated WIP if present**

The user has many in-flight modifications on `platform-multi-tenant`. Check:

```bash
git status --short
```

If there are dirty files unrelated to this slice, **ask the user** whether to stash before the merge, or whether to just `git fetch` + fast-forward without touching working-tree files. Do NOT stash without explicit permission.

- [ ] **Step 4: Fast-forward merge the worktree branch (gated on user approval)**

Show the user what will happen:

```bash
git log --oneline HEAD..tailwind/dialog-consolidation
```

After approval:

```bash
git merge --ff-only tailwind/dialog-consolidation
```

Expected: fast-forward succeeds (no merge commit). If `--ff-only` refuses (because `platform-multi-tenant` advanced during execution), **stop and ask the user** how to proceed — likely a rebase of `tailwind/dialog-consolidation` onto the new `platform-multi-tenant` head, then re-attempt the ff-merge.

- [ ] **Step 5: Push to fork (gated on user approval)**

Show the user the remotes:

```bash
git remote -v
```

Confirm the fork remote is `brycedeneen/langflow-mt` (typically named `fork` or similar — verify before pushing). After approval:

```bash
git push <fork-remote-name> platform-multi-tenant
```

**NEVER `git push origin`** — origin is `langflow-ai/langflow` and the standing rule forbids pushing there.

- [ ] **Step 6: Clean up the worktree**

After the merge + push succeed:

```bash
git worktree remove <path-to-worktree>
git branch -d tailwind/dialog-consolidation
```

(`-d` is safety-checked — refuses to delete if commits aren't merged. If it complains, do NOT use `-D`; investigate first.)

---

## Self-Review Checklist (run after writing this plan)

1. **Spec coverage:**
   - Spec §"Scope > In" item 1 (add `closable` prop) → Task 1. ✓
   - Spec §Scope item 2 (skip rendering when false) → Task 1, Step 3(b). ✓
   - Spec §Scope item 3 (migrate 2 callers) → Tasks 2 and 3. ✓
   - Spec §Scope item 4 (delete variant) → Task 6, Step 1. ✓
   - Spec §Scope item 5 (delete keyframes + tokens) → Task 6, Steps 2–3. ✓
   - Spec §Scope item 6 (add unit test) → Task 1, Step 1. ✓
   - Spec §Scope item 7 (flip followup) → Task 6, Step 5. ✓
   - Spec §Test Impact (typecheck, jest) → Task 1 Step 5, Task 6 Step 6. ✓
   - Spec §Manual Verification → Task 5. ✓
   - Spec §Subagent Parallelism (3 commits) → Tasks 1, 4, 6 are commit boundaries; Tasks 2 and 3 are the parallel-friendly inner steps. ✓

2. **Placeholder scan:** No "TBD"/"TODO"/"implement later"/"appropriate"/"handle edge cases". All test code shown literally. ✓

3. **Type consistency:** `closable?: boolean` named consistently across Tasks 1, 2, 3. Default `true` stated consistently. Files paths consistent (e.g., `src/frontend/src/components/ui/dialog.tsx` everywhere). ✓
