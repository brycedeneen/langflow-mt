# simple-sidebar rename + animated-close removal — Design Spec

**Date:** 2026-04-25
**Branch:** `platform-multi-tenant`
**Status:** Design approved; ready for implementation plan
**Parent plan:** `docs/superpowers/plans/2026-04-22-tailwind-maximization.md` (Phase 1 / Phase 2 / Phase 7a deferrals)

## Goal

Resolve three coupled deferrals from the Tailwind Maximization plan in one pass:

1. **Phase 1 deferral — `simple-sidebar.tsx` ↔ `ui/sidebar` consolidation blocker.** The two have materially different APIs and can't be unified without bloating one or stripping the other.
2. **Phase 2 deferral — `animated-close.tsx` (`AnimatedConditional`).** Was blocked on the simple-sidebar resolution; uses framer-motion for a `width: 0 ↔ auto` animation.
3. **Phase 7a — full `framer-motion` removal.** Both files above are framer-motion consumers; replacing them drops two of the five remaining importer files (current count: 7 import-statement matches across 5 files; expected after this work: 5 matches across 3 files). Remaining consumers: `disclosure.tsx`, `animatedNumbers/index.tsx`, `flowBuildingComponent/index.tsx`.

## Non-goals

- Unifying `simple-sidebar` and `ui/sidebar` into a single component. Investigation confirmed they model different problems (per-pixel drag-resize overlay vs. cookie-persisted sectioned menu) and merging would either bloat the section sidebar with resize plumbing or strip features its many consumers depend on.
- Removing `framer-motion` from `package.json`. Ten other consumers remain; full removal stays in the Phase 7a backlog.
- Behavioral redesign of any sidebar surface. Pixel-level visual parity is the bar; the only acceptable visible change is the framer-motion → CSS swap removing any subpixel difference in easing curves at frame boundaries (imperceptible at 300ms).

## Scope inventory

### Files renamed
- `src/frontend/src/components/ui/simple-sidebar.tsx` → `src/frontend/src/components/ui/resizable-sidebar.tsx`

### Symbols renamed (within the renamed file and at every importer)
- `SimpleSidebar` → `ResizableSidebar`
- `SimpleSidebarProvider` → `ResizableSidebarProvider`
- `SimpleSidebarTrigger` → `ResizableSidebarTrigger`
- `SimpleSidebarHeader` → `ResizableSidebarHeader`
- `SimpleSidebarContent` → `ResizableSidebarContent`
- `SimpleSidebarResizeHandle` → `ResizableSidebarResizeHandle`
- `useSimpleSidebar` → `useResizableSidebar`
- `SimpleSidebarContext` → `ResizableSidebarContext` (internal)
- `--simple-sidebar-width` CSS var → `--resizable-sidebar-width` (rename for consistency; only consumed inside the file itself)
- `--simple-sidebar-parent-width` CSS var → `--resizable-sidebar-parent-width` (same)
- `data-simple-sidebar="..."` data attrs → `data-resizable-sidebar="..."` (same)
- `group/simple-sidebar-wrapper` group name → `group/resizable-sidebar-wrapper` (same)
- `data-testid="playground-btn-flow-io"` on `SimpleSidebarTrigger` — **unchanged** (Playwright depends on it)

### Files deleted
- `src/frontend/src/components/ui/animated-close.tsx`

### Files modified (importers)

simple-sidebar importers (3):
- `src/frontend/src/pages/FlowPage/index.tsx` (uses `SimpleSidebar`, `SimpleSidebarProvider`)
- `src/frontend/src/components/core/flowToolbarComponent/components/playground-button.tsx` (uses `SimpleSidebarTrigger`)
- `src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx` (uses `useSimpleSidebar`)

animated-close importers (2 — beyond simple-sidebar's dead import):
- `src/frontend/src/components/core/playgroundComponent/chat-view/chat-header/components/chat-header.tsx` (4 `<AnimatedConditional>` sites, no `width` prop → animates auto)
- `src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx` (1 `<AnimatedConditional>` site with `width="236px"`)

### Tests / mocks to inspect
- Any Jest test that mocks `framer-motion`, `simple-sidebar`, or `animated-close`. The Phase 2 commit (`7eb956edb6`) noted a mock removal in `InspectionPanel.test.tsx`; this work may need similar housekeeping.

## Replacement strategy

### `simple-sidebar.tsx` framer-motion → CSS

The two `motion.div`s currently animate:
- **Spacer** — `width: spacerWidth` where `spacerWidth ∈ {0, "100%", "var(--simple-sidebar-width)"}`
- **Sidebar** — `width: sidebarWidth`, `x: xPosition ∈ {"0%", "-100%", "100%"}`, `opacity: 0|1`

All three CSS-friendly. The replacement:

```tsx
<div
  className={cn(
    "relative h-full bg-transparent transition-[width] duration-300 ease-in-out",
    "data-[resizing=true]:transition-none data-[fullscreen=true]:transition-none",
  )}
  data-resizing={isResizing}
  data-fullscreen={fullscreen}
  style={{ width: spacerWidth }}
/>
<div
  className={cn(
    "absolute inset-y-0 z-50 flex h-full transition-[width,transform,opacity] duration-300 ease-in-out",
    "data-[resizing=true]:transition-none data-[fullscreen=true]:transition-none",
    className,
  )}
  data-resizing={isResizing}
  data-fullscreen={fullscreen}
  style={{
    width: sidebarWidth,
    transform: `translateX(${xPosition})`,
    opacity: open ? 1 : 0,
    left: side === "left" ? 0 : "auto",
    right: side === "right" ? 0 : "auto",
    pointerEvents: open ? "auto" : "none",
  }}
>
  {/* unchanged inner div */}
</div>
```

The data attributes carry the "skip animation while dragging" and "skip animation in fullscreen" rules that the old `transitionDuration: 0` branches encoded.

The dead `AnimatedConditional` import on line 9 is removed.

### `flow-page-sliding-container.tsx` `AnimatedConditional` (fixed width)

Replace:
```tsx
<AnimatedConditional isOpen={sidebarOpen} width="236px">
  {children}
</AnimatedConditional>
```

With:
```tsx
<div
  data-open={sidebarOpen}
  className="overflow-hidden whitespace-nowrap transition-[width] duration-300 ease-in-out"
  style={{ width: sidebarOpen ? "236px" : 0 }}
>
  {children}
</div>
```

### `chat-header.tsx` `AnimatedConditional` (auto width × 4 sites)

Replace each occurrence with the grid-`fr` trick, which animates `0fr ↔ 1fr` and renders the inner content at its natural width:

```tsx
<div
  data-open={isSessionDropdownVisible}
  className="grid grid-cols-[0fr] transition-[grid-template-columns] duration-300 ease-in-out data-[open=true]:grid-cols-[1fr] overflow-hidden whitespace-nowrap"
>
  <div className="min-w-0 overflow-hidden">
    {children}
  </div>
</div>
```

User accepted the one quirk: when opening, content snaps to its measured intrinsic width and the column animates from 0fr to 1fr — visually equivalent to framer-motion for short text content (which all 4 sites are).

## Verification bar

The full per-phase bar from the parent plan, run end-to-end after all changes land (no per-call-site gating):

1. `cd src/frontend && npm run type-check` — clean
2. `cd src/frontend && npm run test -- --silent` — green (jest)
3. `cd src/frontend && npm run build` — production bundle builds without errors
4. `make tests_frontend` — Playwright e2e green
5. `grep -rn "framer-motion" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l` — count drops from 7 to 5; `grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l` — file count drops from 5 to 3
6. `grep -rn "simple-sidebar\|SimpleSidebar\|useSimpleSidebar" src/frontend/src --include="*.ts" --include="*.tsx"` — zero results
7. `grep -rn "animated-close\|AnimatedConditional" src/frontend/src --include="*.ts" --include="*.tsx"` — zero results

### Manual eyeball (must run dev server)

The five anchor surfaces from the parent plan, plus the surfaces that exercise the changed components:

- Flow canvas (any flow loads, nodes render, connections draw)
- Playground — open chat, expand/collapse session dropdown, expand/collapse fullscreen, open/close the playground sidebar (drag the resize handle, verify width persists during drag, verify hitting min/max constraints)
- Settings page — layout intact
- Admin → Users page — table renders
- Admin → Organizations page — list renders
- Flow page sliding container — open/close, verify the 236px transition animates smoothly

No pixel-perfect comparison needed; just no broken layouts and no console errors.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| CSS `transition-[width]` from `var(--resizable-sidebar-width)` doesn't animate because CSS can't transition between two `var()` values reliably across browsers | Low | The width value is computed to a px string in JS state, not via `var()` for the inline `style.width`. The `--resizable-sidebar-width` CSS var stays internal. Verified the spacer + sidebar both set `style.width` directly. |
| Grid-`fr` trick has different a11y semantics (collapsed content stays in DOM with 0 width) | Low | Identical to framer-motion's behavior — same DOM presence, same content opacity, same `overflow: hidden`. |
| Playwright tests assert text presence inside collapsed `AnimatedConditional` and the new grid layout reports different bounding boxes | Medium | Verification step 4 catches it. If Playwright fails, the fallback is a JS-measured width approach (more code, no quirk). |
| Renaming the trigger component breaks Playwright that relies on the `data-testid="playground-btn-flow-io"` attr | Low | The `data-testid` is preserved verbatim in the rename. |
| A jest test mocks `framer-motion` and the mock now applies to a non-framer-motion component (or vice versa) | Low | Verification step 2. Phase 2's `7eb956edb6` fixed one such case; this work may surface another. Removing dead mocks if found. |

## Posture and constraints

| Dimension | Call |
|---|---|
| Delivery shape | Single coherent commit (or small commit series, at the user's discretion when committing). User opted for "ton of work before committing" cadence. |
| Branch target | `platform-multi-tenant`. No upstream PR. |
| Worktree | Isolated worktree branched from `platform-multi-tenant` per the user's standing preference. |
| Commit cadence | **Pause and ask before every `git commit`**. Stage explicit file paths only — never `git add -A` or `.`. |
| Visual fidelity | "Indistinguishable at a glance"; the grid-`fr` quirk is accepted. |
| Testing | TDD not applicable (refactor with no behavior change); rely on existing jest + Playwright suites for regression catch. |

## Open questions

None. Design fork resolved (rename + CSS, not merge); grid-`fr` quirk accepted by user.
