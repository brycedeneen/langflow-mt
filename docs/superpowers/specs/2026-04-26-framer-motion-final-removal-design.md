# framer-motion final removal + tailwind followup audit

**Date:** 2026-04-26
**Phase:** Tailwind Maximization Phase 7a follow-up (final framer-motion sweep) + followup-doc hygiene
**Status:** Spec — pending plan

## Goal

Migrate the last remaining `framer-motion` consumer to CSS, uninstall the dependency, and flip the four `docs/superpowers/followups.md` entries that prior commits silently resolved.

## Why

Phase 7a (`83e9b10cf7`), the `chore/framer-motion-removal` merge (`7eb956edb6`), and the targeted commits for `BorderTrail` (`8e7b84f7f8`), `TextShimmer` (`0c4ac8db8e`), and `animated-close`/`simple-sidebar` (`ea5f6108d9`) collectively dropped `framer-motion`'s import count from 19 → 1 without finishing the dep removal. The followup doc still says 14 — stale by 13. Closing this loop:

- Frees `package.json` of a sizeable runtime dep.
- Eliminates the lone `<AnimatePresence>` + `<motion.div>` we still ship to users.
- Fixes followup-doc drift that mis-reports four already-completed items as open.

## Scope

In:
- Migrate `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx` from `framer-motion` to the established CSS pattern (`useDelayedUnmount` + `grid-template-rows: 0fr ↔ 1fr` Tailwind classes).
- Update the test mock in `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx` (currently `jest.mock("framer-motion", ...)`) — drop or replace with whatever `useDelayedUnmount` needs.
- `cd src/frontend && npm uninstall framer-motion` (removes from `package.json` + `package-lock.json` + `node_modules`).
- Verify zero residual references to `framer-motion` outside historical comments via `grep`.
- Flip four entries in `docs/superpowers/followups.md` from `- [ ]` to `- [x]` with RESOLVED-by-commit references:
  1. Line 174 — `@chakra-ui/number-input` consumed → `820ae77865`
  2. Line 194 — animated-close blocked by simple-sidebar → `ea5f6108d9`
  3. Line 198 — `border-trail` framer-motion → `8e7b84f7f8`
  4. Line 246 — "14 framer-motion consumers" → this slice

Out:
- The historical comments in `src/frontend/src/utils/useDelayedUnmount.ts:4` and `src/frontend/src/components/ui/disclosure.tsx:150` that reference framer-motion as context (they explain *why* the CSS approach exists — keep them).
- The other still-open follow-ups (line 178 simple-sidebar→ui/sidebar consolidation, line 182 classes.css visual QA, line 237 Phase 4 inline-51, line 250 shadTooltipComponent, line 254 genericIconComponent, line 262 Phase 7e palette) — those need their own dedicated slices.
- Any other framer-motion-style transition refactor outside the one consumer.

## Design

### Migration recipe (established by `disclosure.tsx`)

The lone `framer-motion` block in `flowBuildingComponent/index.tsx`:

```tsx
<AnimatePresence>
  {buildInfo?.error && (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="my-1.5 align-text-top truncate-doubleline">
        <Markdown ...>...</Markdown>
      </div>
    </motion.div>
  )}
</AnimatePresence>
```

Becomes:

```tsx
const showError = useDelayedUnmount(!!buildInfo?.error, 200);
// ...
{showError && (
  <div
    data-state={buildInfo?.error ? "open" : "closed"}
    className="grid grid-rows-[0fr] opacity-0 overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-in-out data-[state=open]:grid-rows-[1fr] data-[state=open]:opacity-100"
  >
    <div className="min-h-0 overflow-hidden">
      <div className="my-1.5 align-text-top truncate-doubleline">
        <Markdown ...>...</Markdown>
      </div>
    </div>
  </div>
)}
```

Why this pattern:
- `useDelayedUnmount(condition, ms)` keeps the element mounted for `ms` after `condition` flips to false, replacing `<AnimatePresence>`'s exit gating.
- The outer `grid grid-rows-[0fr] data-[state=open]:grid-rows-[1fr]` animates the row track from 0fr to 1fr — CSS-supported, transitions through `transition-[grid-template-rows]`.
- The inner `min-h-0 overflow-hidden` collapses to 0 when the parent track is 0fr.
- `transition-[grid-template-rows,opacity] duration-200 ease-in-out` matches the prior `transition={{ duration: 0.2 }}`.
- `200ms` for the `useDelayedUnmount` matches the same duration.

### Imports

Drop `import { AnimatePresence, motion } from "framer-motion";` (line 1).
`useDelayedUnmount` is already imported (line 11) — no new import needed.

### Test mock

`__tests__/index.test.tsx:6`:

```tsx
jest.mock("framer-motion", () => {
  // ...
});
```

After framer-motion is uninstalled, this mock has no module to resolve and Jest's module resolver will fail loudly. Remove the entire `jest.mock("framer-motion", ...)` block. The test no longer needs it because the component no longer imports framer-motion.

### Uninstall

```bash
cd src/frontend && npm uninstall framer-motion
```

This removes the entry from `package.json`'s `dependencies`, prunes `package-lock.json`, and deletes the `node_modules/framer-motion` tree.

### Verification

```bash
grep -rn "framer-motion" src/frontend/src
```

Expected matches (all historical comments — acceptable):
- `src/frontend/src/utils/useDelayedUnmount.ts:4` — file-level JSDoc explaining what the hook replaces
- `src/frontend/src/components/ui/disclosure.tsx:150` — inline comment explaining the CSS pattern's origin

Any *import statement* or `jest.mock` referencing framer-motion is a regression — fix before continuing.

```bash
grep -E '"framer-motion"' src/frontend/package.json src/frontend/package-lock.json
```

Expected: 0 matches (the package-lock matches some transitive dep names like `motion-utils` but not the literal `"framer-motion"` after uninstall).

### Followup-doc flips

Open `docs/superpowers/followups.md` and flip exactly four entries. Each flip:
- Line 174 — `@chakra-ui/number-input` chakra dep removal — RESOLVED by `820ae77865`.
- Line 194 — `animated-close` (`AnimatedConditional`) blocked-by-simple-sidebar — RESOLVED by `ea5f6108d9` (the rename commit deleted `animated-close.tsx`).
- Line 198 — `border-trail` framer-motion — RESOLVED by `8e7b84f7f8`.
- Line 246 — "framer-motion import count is currently 14" — RESOLVED by this slice.

Each flip preserves the original text below the heading; just change the leading `[ ]` to `[x]` and prefix the bullet's content with `**RESOLVED (2026-04-26 by <SHA>):**`. Pattern matches the dialog-no-close consolidation flip from this morning.

### Commit plan

Three commits, each gated on user approval (per the standing rule):

1. **`chore(frontend): drop final framer-motion consumer in flowBuildingComponent`** — `index.tsx` migration + test mock removal.
2. **`chore(frontend): uninstall framer-motion`** — `package.json` + `package-lock.json` + `node_modules` cleanup.
3. **`docs: flip resolved tailwind followups (chakra, animated-close, border-trail, framer-motion)`** — followups.md.

(Commits 1 and 2 could be folded into one — they're tightly coupled. Splitting only buys a slightly cleaner revert if a regression surfaces. User picks.)

### Subagent parallelism

None. The work fits in one file + one doc edit + one shell command. Linear execution + verification is faster than dispatch overhead.

## Risks

- **The `useDelayedUnmount(condition, 200ms)` pattern keeps the element mounted for 200ms after `buildInfo?.error` clears.** During that window, the element renders but transitions out. If anything else in the file expected the error block to literally disappear from the DOM the moment the error clears (e.g., a sibling layout query), behavior changes by 200ms. Mitigation: skim the file for any DOM-presence checks; manual verification by triggering an error and clearing it.
- **`grid-template-rows` transitions are well-supported** in modern browsers (Chromium 117+, Firefox 124+, Safari 17.4+). Langflow's frontend already targets these via the `disclosure.tsx` precedent — no regression risk.
- **Test mock removal:** if other tests in the same file relied on `jest.mock("framer-motion", ...)` for downstream child components, removing the mock could break them. The test file is small; verify it still passes.

## Out-of-scope follow-ups

If migration uncovers a subtle behavior difference (e.g., `framer-motion`'s default `ease-out` vs. our `ease-in-out`, or a stagger pattern relied on elsewhere), capture it as a one-line tweak — don't expand scope.

## References

- `docs/superpowers/followups.md` — the four entries to flip.
- `src/frontend/src/components/ui/disclosure.tsx:150` — established CSS-only pattern.
- `src/frontend/src/utils/useDelayedUnmount.ts` — drop-in `<AnimatePresence>` exit-gating hook.
- `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx` — the lone consumer.
- `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx` — test mock to remove.
- `src/frontend/package.json` — dep entry to remove.
- Prior framer-motion commits: `83e9b10cf7` (Phase 7a), `7eb956edb6` (Phase 1+2), `8e7b84f7f8` (BorderTrail), `0c4ac8db8e` (TextShimmer), `ea5f6108d9` (animated-close), `820ae77865` (chakra).
