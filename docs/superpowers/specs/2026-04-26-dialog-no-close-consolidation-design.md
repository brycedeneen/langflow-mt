# Dialog "no-close" consolidation

**Date:** 2026-04-26
**Phase:** Tailwind Maximization Phase 7d follow-up
**Status:** Spec — pending plan

## Goal

Collapse `src/frontend/src/components/ui/dialog-with-no-close.tsx` into the canonical `src/frontend/src/components/ui/dialog.tsx` by adding a `closable?: boolean` prop (default `true`) to `DialogContent`. Migrate the 2 callers, delete the variant file, and remove the now-orphaned animation keyframes.

## Why

`dialog-with-no-close.tsx` exists solely because the canonical `DialogContent` hardcodes a ✕ close button. It's a near-copy of the canonical with two surfaces consuming it (`modals/baseModal/index.tsx` and `CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx`). The duplication carries five real deltas (animations, centering, overlay, a11y auto-inject, ReactFlow guards), all of which the canonical handles better. Phase 7d audit deferred this consolidation; followup item recorded at `docs/superpowers/followups.md` ("2026-04-26 — Tailwind Phase 7d follow-up: consolidate dialog-with-no-close").

## Scope

In:
- Add `closable?: boolean` (default `true`) to `DialogContent` in `ui/dialog.tsx`.
- Skip rendering the close button (and its Tooltip wrapper) when `closable={false}`.
- Migrate `modals/baseModal/index.tsx` and `CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx` to the canonical `ui/dialog`.
- Delete `ui/dialog-with-no-close.tsx`.
- Delete the four orphaned keyframes (`overlayShow`, `overlayHide`, `contentShow`, `contentHide`) and their `--animate-*` `@theme` tokens in `src/frontend/src/style/index.css`.
- Add a unit test asserting `closable={false}` removes the close button.
- Mark the followup item in `docs/superpowers/followups.md` complete (flip `- [ ]` → `- [x]`; keep the entry for traceability).

Out:
- `BaseModal` itself (long-standing refactor target — leave).
- `DialogContentWithouFixed` (separate customization concern).
- `DialogHeader`'s `text-center sm:text-left` (no-close) vs. `text-left` (canonical) — canonical wins via consolidation; if a caller relied on `text-center`, surface during manual verification, otherwise nothing to do.

## Visual delta resolution

User-approved direction (option **A**): adopt canonical visuals for both migrated callers. Specifically the 2 surfaces will switch:

| Aspect | From (no-close) | To (canonical) |
|---|---|---|
| Open/close motion | `animate-contentShow`/`Hide` (clip-path wipe + box-shadow ramp, 400/500ms) | `animate-in/out` + `fade-in-0`/`fade-out-0` + `zoom-in-95`/`zoom-out-95` + `slide-out-to-left-1/2 slide-out-to-top-[48%]` |
| Overlay motion | `animate-overlayShow`/`Hide` | `dialogClass.dialogContent` (customization-driven) |
| Centering | `fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 grid` | Portal `flex items-center justify-center` wrapper + content `flex flex-col` |
| A11y | No auto-inject | Auto-injects VisuallyHidden `DialogTitle`/`Description` if missing |
| ReactFlow guards | None | Portal wrapper has `nopan nodelete nodrag noflow` |

End-state visual is the same (centered modal, dimmed backdrop, no ✕). Motion language changes for these 2 surfaces from a clip-path wipe to the standard fade+zoom that the rest of the app uses. A11y and ReactFlow-guard behavior strictly improve.

## Design

### `DialogContent` API change

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
    // ...existing a11y auto-inject and Portal/Overlay/Content unchanged...
    return (
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content ...>
          {/* a11y auto-inject */}
          {children}
          {closable && (
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <DialogPrimitive.Close className={cn(/* existing */, closeButtonClassName)}>
                  <Cross2Icon className="h-[18px] w-[18px]" />
                  <span className="sr-only">Close</span>
                </DialogPrimitive.Close>
              </TooltipTrigger>
              <TooltipContent ...>Close</TooltipContent>
            </Tooltip>
          )}
        </DialogPrimitive.Content>
      </DialogPortal>
    );
  },
);
```

Default `true` preserves behavior for every existing caller; only the 2 migrated surfaces opt out.

### Caller migration

**`src/frontend/src/modals/baseModal/index.tsx`**

Drop the `Dialog as Modal, DialogContent as ModalContent` import block (`from "../../components/ui/dialog-with-no-close"`). In the `type === "modal"` branch, replace `<Modal>` / `<ModalContent>` with `<Dialog>` / `<DialogContent closable={false}>` (using the existing canonical import that's already in the file). Keep the existing `contentClasses` className — it provides `flex flex-col flex-1 overflow-hidden max-h-[98dvh]` plus `minWidth`/`height` from `switchCaseModalSize`, all of which override canonical defaults.

**`src/frontend/src/CustomNodes/GenericNode/components/ListSelectionComponent/index.tsx`**

The file already imports `DialogFooter, DialogHeader` from `@/components/ui/dialog` (line 7). Change `import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close"` to import them from `@/components/ui/dialog`. Add `closable={false}` to the `<DialogContent>` element. Existing className `flex max-h-[65vh] min-h-[15vh] flex-col overflow-hidden rounded-xl p-0` continues to override canonical defaults (`p-0` wins over `p-6`).

### Cleanup

After the 2 callers are migrated, in this order:

1. Delete `src/frontend/src/components/ui/dialog-with-no-close.tsx`.
2. Delete the 4 keyframes at `src/frontend/src/style/index.css:199–234` (`overlayShow`, `overlayHide`, `contentShow`, `contentHide`).
3. Delete the 4 `--animate-*` `@theme` tokens at `src/frontend/src/style/index.css:256–259`.
4. Flip the followup checkbox at `docs/superpowers/followups.md` from `- [ ]` to `- [x]` for the entry "2026-04-26 — Tailwind Phase 7d follow-up: consolidate dialog-with-no-close".

Verified pre-spec: those keyframes and tokens have **zero** consumers elsewhere — only `dialog-with-no-close.tsx` references them. Once the file is gone, they are dead.

### Test impact

- Add one new case to `src/frontend/src/components/ui/__tests__/dialog.test.tsx`: `<DialogContent closable={false}>` renders no close button (assert `screen.queryByRole("button", { name: /close/i })` is null). Default behavior already covered by existing tests; ensure they continue to pass.
- `npm run check-types` (typecheck) on the frontend.
- `npm test -- dialog` to run dialog test suite.
- `npx jest src/components/ui` for adjacent component tests (sanity).

### Manual verification

Run `npm run start` and verify in browser:
1. Trigger a `BaseModal` with `type="modal"` (e.g., any confirmation/selection dialog that uses the modal type — pick one from a quick `grep "type=\"modal\"" src/frontend`). Confirm: centers, fades+zooms in, dims backdrop, no ✕, escape/outside-click closes.
2. Open `ListSelectionComponent` from a node with a list-selection input on the canvas. Confirm: same as above, plus no pan/zoom inside ReactFlow when the dialog is open.
3. Confirm the rest of the app's dialogs (the `type="dialog"` path of BaseModal — vast majority) still render the ✕ close.

### Subagent parallelism plan

Three commit boundaries, each gated on user approval per the no-commits-without-permission rule:

1. **Add prop + test** — single commit, single file diff in `dialog.tsx` + new test case. No subagent needed.
2. **Migrate callers** — both files are independent and can be migrated in parallel by 2 subagents (each subagent stages explicit paths, no `git add -A`). Single commit consolidates both.
3. **Cleanup** — single commit: delete the file + 4 keyframes + 4 theme tokens + followup doc strike.

## Risks

- **Motion-language change for 2 surfaces.** Mitigated by manual verification. Low risk — the canonical animation is what the rest of the app uses.
- **`grid` → `flex flex-col` layout shift in callers.** Both callers add `flex flex-col` themselves, so the canonical's `flex flex-col` is the same effective container. Low risk; manual verification covers.
- **Customization layer.** Canonical's `DialogPortal` + `DialogOverlay` go through `dialogClass.dialogContent` (customization). The no-close variant didn't — so there's a remote possibility a downstream customization was intentionally bypassed by no-close. Verify by grepping `customization/utils/dialog-class` for surprises during execution; expected to be a no-op for the open-source path.

## Out-of-scope follow-ups

If `BaseModal`'s `DialogHeader` `text-center` regresses on a tiny-viewport modal, capture as a one-line tweak — don't expand scope to relitigate `BaseModal`.

## References

- `docs/superpowers/followups.md` — Phase 7d follow-up item.
- `docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md` — phase plan.
- `docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md` — Phase 7 spec.
- `src/frontend/src/components/ui/dialog.tsx` — canonical.
- `src/frontend/src/components/ui/dialog-with-no-close.tsx` — variant to delete.
- `src/frontend/src/components/ui/__tests__/dialog.test.tsx` — existing tests.
- `src/frontend/src/style/index.css:199–259` — orphaned keyframes + theme tokens.
