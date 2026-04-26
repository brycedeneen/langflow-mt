# Tailwind Phase 7 — clear the deck — Design Spec

**Date:** 2026-04-26
**Branch:** `platform-multi-tenant`
**Status:** Design approved; ready for implementation plan
**Parent plan:** `docs/superpowers/plans/2026-04-22-tailwind-maximization.md` (Phase 7+ deferrals)

## Goal

Resolve the five Phase 7 deferrals (7a–7e) from the Tailwind Maximization plan in one coherent session. Each deferral becomes its own commit on a single shared branch, with one ff-merge into `platform-multi-tenant` at the end after a unified verification gate.

This is debt reduction, not feature work: shrink the custom-component / custom-utility surface so the codebase sits closer to stock Tailwind v4 + shadcn/Radix primitives, and reduce maintenance overhead from rarely-used wrappers.

## Non-goals

- Behavioral changes. Pixel parity is the bar; any "indistinguishable at a glance" CSS swap is acceptable, anything that changes interaction or layout is out of scope.
- Full removal of `framer-motion` from `package.json`. The `flowBuildingComponent` height-collapse block is load-bearing and stays on the deferral list.
- Aggressive palette consolidation. Token consolidation is conservative — only obvious duplicates with identical values and no role distinction. Anything that needs per-surface visual judgment is deferred.
- Touching `ForwardedIconComponent` itself or removing it. The wrapper stays in place for the 24 dynamic-name call sites that need it.
- Touching the 38 KEEP rules in `applies.css` (resolved by Phase 4).
- Migrating `chakra-ui/number-input`. That's a separate Phase 1 deferral and is out of scope for Phase 7.

## Audit snapshot (2026-04-26)

| Piece | Scope | Sub-categories |
|---|---|---|
| **7a** | 3 framer-motion importer files | `disclosure.tsx`, `animatedNumbers/index.tsx`, `flowBuildingComponent/index.tsx` |
| **7b** | 108 files reference `ShadTooltip` | one usage shape (props: `side`, `content`, optional `delayDuration`) |
| **7c** | 173 static-name + 24 dynamic-name `<ForwardedIconComponent name=...>` call sites | static → direct lucide; dynamic → keep wrapper |
| **7d** | 3 small wrappers in `components/ui/` | `refreshButton.tsx`, `dialog-with-no-close.tsx`, `disclosure.tsx`. Each: ~24-27 file references (raw count, includes substring matches; real count after audit will be lower). |
| **7e** | 125 `--color-*` tokens in `index.css` `@theme` block | most are role-distinct semantic tokens (status/note/flow/etc.); only a small subset are pure-duplicate consolidation candidates. |

The exact call-site counts in 7b/7c/7d will be re-derived from a precise audit at execution time (using the Python `\b`-aware pattern that worked for Phase 4, sorted longest-first to avoid the prefix-collision bug we hit there).

## Pipeline (5 commits on `tailwind/phase-7`)

Each commit is independently shippable. They run in this order, but failures in any commit's own verification gate stop the chain — earlier commits stay on the branch, later commits don't run.

### Commit 1 — 7a: framer-motion partial removal

**Files modified:** `components/ui/disclosure.tsx`, `components/common/animatedNumbers/index.tsx`, `pages/FlowPage/components/flowBuildingComponent/index.tsx`.

**Approach:**

- **`disclosure.tsx`:** the `motion.div` is decorative (open/close transition with `height: auto ↔ 0`). Replace with the grid-`fr` trick (`grid-template-rows: 0fr ↔ 1fr`) — same pattern we used for `AnimatedConditional` in the simple-sidebar work.
- **`animatedNumbers/index.tsx`:** numeric-tween animation. Replace with a CSS `transition` over a CSS custom property animated via `requestAnimationFrame` — or, simpler, just remove the easing and use the raw value (the visual difference for fast-changing numbers is minimal). Inspect the actual implementation at execution time and pick the simpler option.
- **`flowBuildingComponent/index.tsx`:** has multiple `motion.div` consumers. Convert the decorative ones (fade-in, opacity, transform) to CSS transitions. **Leave** the height-collapse block that animates `height: auto ↔ 0` for error display — that's the load-bearing site documented as deferred in the followups doc.

**Outcome:** framer-motion importer files 3 → 1 (only flowBuildingComponent retains, for one site). Dep stays installed.

**Verification (commit-local):** typecheck, jest, build, manual eyeball list (disclosure: any panel that opens/closes; animatedNumbers: any counter; flowBuildingComponent: build progress UI).

### Commit 2 — 7b: inline `shadTooltipComponent`

**Files modified:** ~108 caller files, plus deletion of `components/common/shadTooltipComponent/`.

**Approach:**

The shape is consistent across call sites:

```tsx
// Before
<ShadTooltip side="bottom" content="Save" delayDuration={300}>
  <Button>...</Button>
</ShadTooltip>

// After
<Tooltip delayDuration={300}>
  <TooltipTrigger asChild>
    <Button>...</Button>
  </TooltipTrigger>
  <TooltipContent side="bottom">Save</TooltipContent>
</Tooltip>
```

Imports change from `@/components/common/shadTooltipComponent` to `@/components/ui/tooltip`. A `TooltipProvider` is needed somewhere up the tree — `ui/sidebar`'s `SidebarProvider` already wraps with one; for any surface NOT under that provider, we add a `TooltipProvider` at a sensible parent (most likely `App.tsx` or similar). Audit at execution time.

**Subagent-driven:** group call sites by surface area into 6-8 bundles; one parallel subagent per bundle. Each subagent only edits JSX/TSX call sites; the controller handles the wrapper-component deletion at the end.

**Edge cases caught at audit time:**
- `ShadTooltip` callsite that uses `content={JSX}` — a JSX fragment as content. The new pattern handles this via `TooltipContent` children — same shape, just preserve the JSX subtree.
- Any consumer that passes `delayDuration={0}` while the surrounding `TooltipProvider` has a different default — preserve the per-tooltip override.
- Any `forwardRef` patterns — preserve the ref forwarding through `TooltipTrigger asChild`.

**Outcome:** `components/common/shadTooltipComponent/` directory deleted. Bundle size win from removing the wrapper's memoization layer (Radix is already optimized).

### Commit 3 — 7c: static-name icon inlines

**Files modified:** ~150-170 caller files (the static-name subset of the 197 call sites).

**Approach:**

For each `<ForwardedIconComponent name="X" {...other props}/>` where `X` is a string literal:
1. Identify the lucide-react export name for `X` (e.g., `name="ChevronDown"` → `ChevronDown` from `lucide-react`).
2. Add `import { ChevronDown } from "lucide-react";` to the file (deduped against existing imports).
3. Replace the JSX with `<ChevronDown {...other props}/>`. Preserve every other prop verbatim (className, size, strokeWidth, etc.).
4. If the file has zero remaining `<ForwardedIconComponent ...>` calls, remove the import.

**Dynamic-name sites stay as-is** — `<ForwardedIconComponent name={iconName} />` and similar. The wrapper exists for those.

**Subagent-driven:** group static-name sites by surface area into ~8 bundles; parallel subagents.

**Edge cases:**
- `name="X"` where `X` is not a stock lucide icon (some app-specific names map to custom icons inside `forwardRef`-wrapped components in `src/icons/`). For these, leave as `ForwardedIconComponent` — the lookup is what the wrapper does.
- An audit step pre-builds the static-name → lucide-export map and flags any mismatches before subagent dispatch.

**Outcome:** ~170 call sites convert to direct lucide imports. Tree-shaking lets unused icons drop out of the bundle.

### Commit 4 — 7d: small-wrapper audit

**Files modified:** depends on per-wrapper audit results.

**Per-wrapper procedure:**

1. **Real-caller audit** — for each wrapper, count files that ACTUALLY use the export (filter out `data-testid`, substring matches, and the wrapper's own internals).
2. **Decision matrix:**
   - `0 real callers` → DELETE the wrapper file.
   - `1-3 real callers` AND wrapper body has no behavior beyond styling a primitive → INLINE the styling at the call sites and delete the wrapper.
   - `>3 real callers` OR wrapper has real behavior (state, refs, complex composition) → KEEP and add a one-line comment if the role isn't obvious.

**`disclosure` interaction with 7a:** `disclosure.tsx` is also targeted by 7a. The 7a conversion happens FIRST (Commit 1); 7d's audit runs on the post-7a version. If the 7d audit decides DELETE or INLINE, the 7a conversion is moot — the file gets deleted in this commit.

**Outcome:** at least one of the three wrappers gets deleted (high probability based on raw counts — most thin wrappers in this codebase have been DEAD-leaf candidates), the others get a clear keep/inline decision documented.

### Commit 5 — 7e: conservative palette consolidation

**Files modified:** `src/frontend/src/style/index.css` only (or, if any consolidation requires call-site updates, those files too).

**Approach:**

1. **Audit:** for each `--color-*` token in the `@theme` block, resolve its final value (chase `var(--foo)` references through `:root` / `.dark` blocks). Group tokens by final value.
2. **Identify obvious duplicates:** pairs/triples of tokens with IDENTICAL final values AND no role distinction. Examples we'd consolidate:
   - Two tokens both resolving to the same `hsl(...)` value with names that differ only in synonyms (`--color-medium-gray-foo` and `--color-medium-gray-bar` if both resolve identically).
3. **Identify role-distinct tokens** (KEEP):
   - `--color-status-{blue,green,red,yellow,gray}` (semantic status)
   - `--color-note-{amber,neutral,rose,blue,lime}` (note node palette)
   - `--color-chat-{send,bot-icon,user-icon,trigger,trigger-disabled}` (chat surface)
   - `--color-flow-icon`, `--color-component-icon`, `--color-build-trigger`, `--color-connection`, `--color-node-selected`, `--color-node-ring` (flow canvas roles)
   - `--color-selected`, `--color-hover`, `--color-ring`, `--color-border`, `--color-input`, `--color-background`, `--color-foreground`, `--color-placeholder*` (shadcn base tokens)
   - `--color-datatype-*`, `--color-accent-*` (semantic palette role-distinct)
   - `--adp-red` (brand)
   - Anything with a clearly intentional name role.
4. **Consolidate the duplicates only:** delete the redundant token, replace its usages across `src/frontend/src/**/*.{ts,tsx,css}` with the kept token's name.
5. **Document the keep list** as a comment block at the top of the `@theme` block, so future audits don't re-flag these.

**Expected scale:** 5-15 token consolidations, NOT 50+. Anything that requires "are these visually equivalent in practice?" judgment is logged as a Phase 7e follow-up and not touched here.

**Outcome:** `--color-*` token count drops modestly (~10%); the kept palette is documented as intentional.

## Verification gate (single, end-of-chain)

After all 5 commits land on `tailwind/phase-7`, run once before ff-merge:

1. `cd src/frontend && npm run type-check` — only the 2 pre-existing TagRead errors.
2. `cd src/frontend && npm run test -- --silent` — only the 14 pre-existing `SaveAsTemplateModal.test.tsx` failures, ≥3105 pass.
3. `cd src/frontend && npm run build` — clean.
4. ORPHAN sweep: every removed/inlined identifier has zero residual references (run with the smart Python `\b`-aware scanner from Phase 4, accounting for `data-testid`, SVG `id`, prefix substring matches, and CSS variable name embeds).
5. Per-piece counters:
   - 7a: framer-motion file count 3 → 1 (verified by `grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include=*.ts --include=*.tsx | wc -l`)
   - 7b: zero `ShadTooltip` references; `components/common/shadTooltipComponent/` directory absent
   - 7c: static-name `<ForwardedIconComponent name="..."/>` count drops ≥150; dynamic-name count unchanged
   - 7d: wrapper files deleted/inlined per the audit decisions
   - 7e: `--color-*` token count drops ≥5 (modest by design)

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Subagent-induced visual regression in tooltips (e.g., default delay differs between `ShadTooltip` wrapper and bare `Tooltip`) | Medium | Audit step extracts `delayDuration` defaults; test surface includes the playground (heavy tooltip usage). |
| Lucide icon name doesn't match wrapper's `name` prop (e.g., `name="X"` is an app-specific icon, not lucide) | Medium | Pre-flight: build the static-name → lucide-export map; flag any name not in lucide's exports for manual review. |
| Audit's grep miscounts (substring/false-positive issue we hit in Phase 4) | Medium | Use the longest-first regex alternation pattern from Phase 4; cross-check with `data-testid` / `id="..."` filters. |
| 7e identifies "duplicates" that turn out to be visually distinct via a CSS variable that resolves differently in `.dark` mode | Medium | Resolve final values per `:root` AND `.dark` separately; only consolidate when BOTH resolve identically in BOTH modes. Phase 3 of the parent plan was skipped because of dark-mode dependency mismatches — same caveat applies here. |
| `flowBuildingComponent` partial conversion breaks the surrounding error-display layout | Low | Leave the height-collapse block strictly untouched. Manual eyeball the error-display surface post-commit-1. |
| Disclosure wrapper deletion in 7d (if audited as inline-able) breaks a behavior that the audit didn't catch | Low | Audit checks for state/refs/complex composition before flagging as inline-able. Worst case: the wrapper-deletion commit gets reverted and disclosure stays. |

## Posture and constraints

| Dimension | Call |
|---|---|
| Delivery shape | Single branch (`tailwind/phase-7`), 5 sequential commits, single ff-merge at end. |
| Branch target | `platform-multi-tenant`. No upstream PR — push to `fork` only (memory: never push to `langflow-ai/langflow`). |
| Worktree | `.worktrees/tailwind-phase-7`. |
| Commit cadence | Each piece commits when its commit-local verification passes. **Pause-and-ask for explicit user approval before each commit lands** (per user's standing rule). After all 5 commits, pause again before the ff-merge for smoke-test gating. |
| Visual fidelity | "Indistinguishable at a glance." Conservative defaults on 7a (leave the height-collapse block) and 7e (consolidate only obvious duplicates). |
| Subagent commit hygiene | Subagents never `git add` or commit. Controller stages explicit paths and commits per-piece. |
| Testing | No new tests. Existing jest + build + grep sweeps + manual eyeball post-merge. Playwright still deferred. |

## Open questions

None. Both conservative-vs-aggressive forks (7a flowBuildingComponent and 7e palette) resolved as conservative.
