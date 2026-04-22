# Tailwind Maximization — Design Spec

**Date:** 2026-04-22
**Branch:** `platform-multi-tenant`
**Status:** Design approved; ready for implementation plan

## Goal

Reduce the frontend's custom-CSS and custom-component surface area so the codebase sits as close to stock Tailwind v4 + shadcn/Radix primitives as possible. The work is motivated by iteration speed: less custom surface means faster visual changes, fewer surprises in tests, and less bespoke code to keep in anyone's head.

The user experience stays materially the same. Colors may snap to the nearest stock Tailwind shade (within ~2%); nothing else is a design change.

## In scope

- `src/frontend/src/style/*.css` — theme tokens in `index.css`, `@apply` rules in `applies.css`, dead CSS in `classes.css`.
- `src/frontend/src/components/ui/` — decorative/duplicate primitives (`background-gradient`, `dot-background`, `text-loop`, `textAnimation`, `TextShimmer`, `animated-close`, `simple-sidebar`).
- `src/frontend/src/components/core/border-trail.tsx`.
- `src/frontend/src/components/core/accordionComponent/` — inline into direct `ui/accordion` use.
- Root `package.json` — remove unused styling dependencies.
- Call sites touched by any of the above (mechanical edits).

## Out of scope (in scope for Phase 7+ follow-on work, see below)

- `App.css` react-flow + ag-grid overrides — load-bearing, leave alone.
- `ag-theme-shadcn.css`, `custom-ace-overrides.css` — narrow, working, leave alone.
- Feature-specific `core/`/`common/` domain components (flow toolbar, playground, json editor, flow canvas controls, chat components, etc.) — not cleanup targets.
- Wholesale `framer-motion` removal — dependency stays; only decorative consumers are pruned in this effort.
- Inlining `shadTooltipComponent` and `genericIconComponent` / `renderIconComponent` — these wrappers stay for this effort.
- Any redesign or visual refresh.

## Success criteria

- `applies.css` shrinks by roughly half (keep only rules with ≥3 references).
- `style/index.css` `@theme` block has no alias-of-alias indirection and ≥20% fewer `--color-*` tokens.
- `style/classes.css` deleted (if confirmed dead) or its live selectors relocated.
- `@emotion/react`, `@emotion/styled`, `@chakra-ui/number-input`, `@chakra-ui/system` removed from `package.json` (if confirmed unused).
- 6 decorative `ui/` components deleted; `simple-sidebar.tsx` gone; `core/accordionComponent/` gone.
- After every phase: typecheck, jest, Playwright e2e, and production build all pass; the five anchor surfaces (flow canvas, playground, settings, admin users, admin organizations) show no visible drift.

## Posture and constraints

| Dimension | Call |
|---|---|
| Delivery shape | Phased rollout — one phase per PR-equivalent commit series; each independently shippable and reversible. |
| Visual fidelity | "Close enough" — identical at a glance. Custom colors may snap to stock Tailwind shades when within ~2%. |
| `framer-motion` | Prune decorative consumers in this effort; full removal deferred to Phase 7a. |
| `applies.css` trim rule | Inline any rule with <3 references; keep rules with ≥3 references (they've earned the abstraction). |
| Theme cleanup | Flatten alias-of-alias indirection first (zero call-site churn); snap-to-Tailwind later. |
| Wrapper cleanup | Delete dead (`simple-sidebar.tsx`) + inline the small one (`accordionComponent`). Tooltip and icon wrappers deferred. |
| Verification bar | Per-phase: typecheck + jest + Playwright + prod build + eyeball five anchor surfaces. Phase 6 adds 12-screen walkthrough. |
| Branch target | `platform-multi-tenant`. No upstream PR. |
| Commit cadence | Pause and ask before every `git commit`, per user preference. Each phase lands as its own commit(s) after explicit approval. |

## Phase sequence

Ordered risk-ascending so momentum builds on boring, reversible wins before touching call sites.

### Phase 1 — Dead code & unused styling deps

**Why it's first:** Near-zero risk. Pure deletion.

**Changes:**
- Grep imports of `@emotion/react`, `@emotion/styled`, `@chakra-ui/number-input`, `@chakra-ui/system`. For any that have zero usage, remove from `package.json` and `package-lock.json`.
- Audit `src/frontend/src/style/classes.css`: grep every selector defined in it against the codebase. If no references exist anywhere, delete the file and remove its import from `src/frontend/src/index.tsx`. If references exist, split selectors into "dead" (delete) and "alive" (relocate into `App.css` if react-flow/ag-grid-related, otherwise into the single consuming component's local styles).
- Delete `src/frontend/src/components/ui/simple-sidebar.tsx` and remove its imports (confirmed duplicate of `sidebar.tsx`).

**Acceptance:**
- Typecheck, jest, Playwright e2e, and `npm run build` all pass.
- Bundle size did not grow.
- No references remain to any removed symbol.

**Expected churn:** Small. One file deletion, one audit with likely full deletion, four dep removals.

### Phase 2 — Decorative framer-motion purge

**Why second:** UI toys with few call sites. Low blast radius.

**Changes:**
- Delete `src/frontend/src/components/ui/background-gradient.tsx`, `ui/dot-background.tsx`, `ui/text-loop.tsx`, `ui/textAnimation.tsx`, `ui/TextShimmer.tsx`, `ui/animated-close.tsx`, and `src/frontend/src/components/core/border-trail.tsx`.
- For each existing call site, replace with either (a) nothing (if it was purely decorative), (b) the underlying plain element with a Tailwind transition class, or (c) a short inline equivalent. No new wrapper components.
- `framer-motion` stays in `package.json` — other files still use it. Full removal is Phase 7a.

**Acceptance:**
- Typecheck, jest, Playwright e2e, production build all pass.
- Manual eyeball of any page that historically used these components (typically assistant/onboarding surfaces) shows no broken layouts.
- `grep -r "framer-motion" src/frontend/src | wc -l` decreases measurably from baseline.

**Expected churn:** Small. 7 component deletions plus ≤2 call-site edits per component on average.

### Phase 3 — Theme indirection flatten

**Why third:** Pure mechanical refactor. Zero call-site churn. Exposes which tokens are actually distinct values vs. aliases, informing Phase 6.

**Changes:**
- Walk the `@theme` block in `src/frontend/src/style/index.css`. For every `--color-foo: var(--foo)` alias, resolve `--foo` to its ultimate literal value (or the single HSL pair it references) and inline that value.
- Remove any now-orphaned CSS variables defined elsewhere in the file whose only purpose was to feed a `--color-*` alias.
- **No JSX/TSX changes in this phase.** Pure `index.css` refactor.

**Acceptance:**
- Typecheck, jest, Playwright e2e, production build all pass.
- Snapshot the computed value of every `--color-*` token before and after the change; diff must be empty (no numerical change to any token).
- Manual spot-check of the five anchor surfaces shows no visible drift.

**Expected churn:** Moderate in `index.css` only (~100 lines touched). No other files.

### Phase 4 — `applies.css` trim

**Why fourth:** Largest diff of any phase; benefits from clean theme done first (easier visual comparison).

**Changes:**
- Build a usage map: for each class defined in `src/frontend/src/style/applies.css`, count references across `src/frontend/src/**/*.{ts,tsx,css}`.
- For every class with **<3 references**: at each call site, replace `className="the-custom-class"` with an inlined version of the Tailwind utilities from the `@apply` rule. Then delete the rule from `applies.css`.
- Classes with **≥3 references** stay in `applies.css` — they've earned the abstraction.
- After the pass, the file should be roughly half its current size.

**Acceptance:**
- Typecheck, jest, Playwright e2e, production build all pass.
- Every class remaining in `applies.css` has ≥3 references in the codebase (verify with a grep script run at the end of the phase).
- Manual eyeball of the five anchor surfaces shows no drift.

**Expected churn:** Large diff, mechanical edits across many files.

### Phase 5 — `accordionComponent` inline

**Why fifth:** Focused wrapper cleanup. Concentrates visual review on one primitive.

**Changes:**
- Replace every import of `src/frontend/src/components/core/accordionComponent/` with direct use of `ui/accordion`. Carry forward any non-trivial default behavior from the wrapper (e.g., default expanded state, custom trigger styling) as inline props at each call site — not as a new wrapper.
- Delete the `accordionComponent/` directory.

**Acceptance:**
- Typecheck, jest, Playwright e2e, production build all pass.
- Eyeball every accordion surface (sidebar categories, settings panels, admin organization detail, component details, etc.) for behavior parity.

**Expected churn:** Medium. Dozens of call-site edits, one directory deletion.

### Phase 6 — Theme token snap-to-Tailwind

**Why sixth:** Highest churn across visual tokens. Lands last so earlier mechanical cleanup hasn't been confounded with visual adjustments.

**Changes:**
- For every remaining `--color-*` in `src/frontend/src/style/index.css`, compare against stock Tailwind v4 shades. If the token is within ~2% of a stock shade **and** is not semantically app-specific (see "keep list" below), delete the token and migrate call sites from `bg-custom-token` / `text-custom-token` to the stock Tailwind utility name (`bg-zinc-700`, `text-slate-500`, etc.).
- **Keep list (do not snap):**
  - `--adp-red` (brand).
  - `--color-status-{blue,green,red,yellow,gray}` (semantic status).
  - `--color-datatype-*` (node datatype coloring).
  - `--color-note-{amber,neutral,rose,blue,lime}` (note node palette).
  - `--color-chat-{send,bot-icon,user-icon,trigger,trigger-disabled}` (chat surface).
  - `--color-flow-icon`, `--color-component-icon`, `--color-build-trigger`, `--color-connection`, `--color-node-selected`, `--color-node-ring` (flow canvas roles).
  - `--color-selected`, `--color-hover`, `--color-ring`, `--color-border`, `--color-input`, `--color-background`, `--color-foreground`, `--color-placeholder*` (shadcn base tokens — these stay).
  - Anything else whose name makes its semantic role obvious and load-bearing.

**Acceptance:**
- Typecheck, jest, Playwright e2e, production build all pass.
- The `@theme` block has ≥20% fewer `--color-*` tokens than the pre-Phase-1 baseline.
- Walkthrough of 12 surface screens with before/after side-by-side shows no user-perceivable drift:
  1. Flow canvas (dark mode)
  2. Flow canvas (light mode)
  3. Node details sidebar
  4. Playground chat
  5. Playground file upload
  6. Settings → general
  7. Settings → API keys
  8. Admin users page
  9. Admin organizations list
  10. Admin organization detail
  11. Component Assist popover
  12. Note nodes

**Expected churn:** Large. Call-site edits across JSX and CSS.

## Phase 7+ — Deferred follow-ons

These were explicitly scoped out of the initial six phases but remain work items to revisit. Each is actionable on its own.

### 7a — Full `framer-motion` removal

**Goal:** Remove `framer-motion` from `package.json`.

**Prerequisite:** Phase 2 complete.

**Changes:** Replace every remaining `framer-motion` consumer (~12 files after Phase 2) with `tw-animate-css` utilities or hand-rolled CSS transitions. Remove the dependency.

**Acceptance:** Zero `framer-motion` imports remain; bundle size decreases; Playwright e2e passes; the surfaces that used gesture/physics animations (node drag, assistant reveal, chat stream) still feel right.

**Why deferred:** Larger blast radius than decorative purge; some consumers use physics or gesture features that need thoughtful replacement.

**Expected churn:** Medium-large — per-consumer rewrites.

### 7b — Inline `shadTooltipComponent`

**Goal:** Remove `src/frontend/src/components/core/shadTooltipComponent/`; every call site uses `ui/tooltip` directly.

**Changes:** Hundreds of call-site edits across the app. Drop the memoization wrapper (Radix is already optimized).

**Acceptance:** Wrapper directory deleted; no regressions in tooltip behavior; typecheck/jest/Playwright pass.

**Why deferred:** High call-site volume for low per-site gain; worth deferring until base Tailwind posture is established.

**Expected churn:** Very large diff, low per-site complexity.

### 7c — Inline icon wrappers (`genericIconComponent`, `renderIconComponent`)

**Goal:** Remove both icon wrapper components; call sites import lucide icons (and `@tabler/icons-react` where applicable) directly.

**Changes:** Audit every call site; replace `<GenericIconComponent name="foo" />` with direct `<FooIcon />` imports. Consolidate size/stroke defaults into a single shared constant or a thin `iconClass` helper if standardization is still desired.

**Acceptance:** Wrapper files deleted; icon rendering visually identical; bundle size decreases from tree-shakable direct imports.

**Why deferred:** These wrappers provide consistent size/stroke defaults, which is a legitimate (if thin) abstraction. Worth a focused pass rather than bundling with unrelated cleanup.

**Expected churn:** Very large diff.

### 7d — Remaining decorative consolidation

**Goal:** Audit `refreshButton`, `dialog-with-no-close`, `disclosure` after phases 1–6 land. If any are still unused or thin, delete.

**Acceptance:** Each file either has a justifying usage site or is deleted.

**Expected churn:** Small.

### 7e — Semantic palette lean-out

**Goal:** Revisit every `--color-*` token that survived Phase 6 because it's semantic. Identify opportunities to collapse near-duplicates (e.g., multiple "medium" grays that only differ by alpha) into a leaner semantic palette.

**Acceptance:** Reduced token count in the `@theme` block; documentation of the intentional semantic palette.

**Expected churn:** Medium, concentrated in `index.css` with some call-site follow-through.

## Verification bar (per phase)

Every in-scope phase must pass all of the following before commit:

1. `npx tsc --noEmit` clean.
2. `npm run test` (jest) green.
3. `make tests_frontend` (Playwright e2e) green.
4. `npm run build` produces a production bundle without errors.
5. Manual eyeball on the five anchor surfaces: flow canvas, playground, settings page, admin users page, admin organizations page.

Phase 6 additionally requires the 12-screen walkthrough listed in its section.

## Rollback strategy

- Each phase lands as one focused commit (or a small commit series) on `platform-multi-tenant` that can be reverted as a unit.
- Because the ordering is risk-ascending, reverting phase N does not invalidate phases 1..N-1.
- No upstream PR is created (per the user's standing preference).

## Open questions

None. All posture questions were resolved during brainstorming.
