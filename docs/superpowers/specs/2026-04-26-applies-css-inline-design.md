# `applies.css` inline pass — Design Spec

**Date:** 2026-04-26
**Branch:** `platform-multi-tenant`
**Status:** Design approved; ready for implementation plan
**Parent plan:** `docs/superpowers/plans/2026-04-22-tailwind-maximization.md` (Phase 4 deferral)

## Goal

Drive `src/frontend/src/style/applies.css` from 687 lines down toward ~150-250 lines by deleting truly dead rules, inlining low-use rules at their call sites, and relocating cohesive decorative blocks to the components that consume them. Eliminate the bookkeeping cost of maintaining a custom-utility layer for rules that are used only once or twice.

The original Phase 4 followups item described this as "inline 51 low-use `@apply` rules." A fresh audit shows the actual shape is more nuanced: 109 classes/utilities defined, 14 dead, 54 with 1-2 references, 41 with ≥3 references — and a chunk of the low-use rules contain pseudo-elements, raw CSS, or cross-references to other applies.css rules that prevent a clean mechanical inline.

## Non-goals

- Touching the 41 KEEP rules (≥3 refs). Those have earned the abstraction; leave them.
- Migrating any rule out of CSS-first config into a different mechanism. Tailwind v4 `@utility` and plain `.class` rules both stay as appropriate; we're just reducing how many we have.
- Rewriting any rule's behavior. Pixel parity is the bar.
- Cleaning up `App.css` (react-flow / ag-grid overrides) — out of scope.
- Touching `index.css` `@theme` block — out of scope.
- Removing `framer-motion`, `chakra`, or any dependency. Out of scope.

## Audit data (snapshot 2026-04-26)

`/tmp/p4-applies-classes.txt` — 109 unique class/utility names from `applies.css` (extracted via both `^\s*\.<name>` selector pattern and `^@utility <name>` pattern).

`/tmp/p4-applies-usage.txt` — per-class external reference count from grep across `src/frontend/src/**/*.{ts,tsx,css}` excluding `applies.css` itself.

| Bucket | Criterion | Count |
|---|---|---|
| DEAD | ext=0 | 14 |
| INLINE | 1≤ext≤2 | 54 |
| KEEP | ext≥3 | 41 |

The plan's first task rebuilds these maps deterministically (the `/tmp/` files won't survive a fresh worktree). The plan does NOT depend on these specific filenames.

### Sub-bucketing

The audit step refines the buckets by computing two more signals per class:

- `int` — count of `@apply` directives inside `applies.css` that reference this class. Non-zero means the rule is used transitively by another applies.css rule, so deleting it without expanding the parent rule first would break the parent.
- `pure` — true when the rule body is *only* `@apply <utilities>` with no pseudo-elements (`::before`, `::after`, `&:hover`), no raw CSS declarations (`width: 50px`, `transform: rotate(...)`), and no nested selectors. Pure rules are mechanically inlinable as a className string. Non-pure rules need a different treatment.

Combining the three signals (ext, int, pure):

| Sub-bucket | Criterion | Treatment |
|---|---|---|
| **DEAD-leaf** | ext=0 ∧ int=0 | Delete the rule. |
| **DEAD-internal-only** | ext=0 ∧ int>0 | Expand the rule's contents into each parent rule's `@apply`, then delete this rule. |
| **INLINE-pure-leaf** | 1≤ext≤2 ∧ int=0 ∧ pure | Inline `@apply` utilities at the 1-2 call sites; delete the rule. |
| **INLINE-pure-non-leaf** | 1≤ext≤2 ∧ int>0 ∧ pure | Inline at external call sites; expand into parent rules' `@apply`; delete the rule. |
| **INLINE-complex** | 1≤ext≤2 ∧ ¬pure | Case-by-case: relocate to consumer's adjacent CSS file, or (if both relocation and inline are unreasonable) promote to KEEP. |
| **CLUSTER-relocate** | The 8 gradient classes (`gradient-bg`, `gradients-container`, `g1` … `g6`) | Move as one cohesive unit to `pages/MainPage/pages/emptyPage/gradient-bg.css`; import from `emptyPage/index.tsx`; delete from `applies.css`. |
| **KEEP** | ext≥3 | No change. |

The CLUSTER-relocate carve-out is justified: the 8 classes form a single decorative animated background (radial gradients with keyframe motion, embedded base64 SVG mask) used at exactly one call site (`emptyPage/index.tsx`). Inlining 8 separate ~15-line CSS rules into JSX className strings is impossible without the rules collapsing into one giant arbitrary-value blob; relocating them to a co-located CSS file keeps them as a coherent unit while still removing them from the global applies.css.

## Pipeline

The work runs in stages, ordered by risk. Each stage's verification has to pass before the next starts. The whole pipeline produces one commit at the end.

### Stage 0 — Worktree + audit

Branch `tailwind/applies-inline` from `platform-multi-tenant` in `.worktrees/tailwind-applies-inline`. `npm install`. Run a fresh audit script that produces:
- `/tmp/p4-audit.tsv` — `<name>\t<ext>\t<int>\t<pure>\t<bucket>`
- Capture baseline `applies.css` line count (~687) and a baseline grep count for orphan-class detection.

### Stage 1 — DEAD-leaf deletes + CLUSTER-relocate (single subagent, low risk)

One subagent owns this stage. Tasks:
1. Delete every DEAD-leaf rule from `applies.css`.
2. Create `src/frontend/src/pages/MainPage/pages/emptyPage/gradient-bg.css` containing the 8 gradient rules verbatim (preserve everything: base64 SVG, keyframes references, CSS variables).
3. Add `import "./gradient-bg.css";` to `pages/MainPage/pages/emptyPage/index.tsx`.
4. Delete the 8 gradient rules from `applies.css`.
5. Verify `npm run type-check` and `npm run build` still pass.

Expected `applies.css` line drop after Stage 1: ~50-100 lines (depends on rule body sizes).

### Stage 2 — INLINE-pure-leaf in parallel batches (high churn, parallel-friendly)

Group the INLINE-pure-leaf rules by surface area for parallel dispatch. Surface areas observed in the audit:
- `form-modal-*` (chat / send button / markdown / play icon clusters)
- `dropdown-component-*` and related (`dropdown-component-false-outline`, `dropdown-component-options`, etc.)
- `error-build-*` and `success-alert-*`
- `langflow-chat-*`
- `skeleton-card-*`
- `input-component-*`, `input-file-component`, `input-slider-text`
- Other singletons (group as a "misc" bucket if too small to merit their own group)

One subagent per surface-area group. Each subagent receives:
- The list of rules in its group, with their `@apply` utility list pre-extracted by the controller.
- The list of call sites (file + line) for each rule, pre-computed by the controller.
- Hard constraint: only modify JSX/TSX call sites. **Do not touch `applies.css`.**

After a subagent reports done, the controller (me) deletes the corresponding rules from `applies.css`. This avoids parallel writes to `applies.css` and centralizes the bookkeeping.

After all subagents finish, the controller runs `npm run type-check` and `npm run build` on the combined state.

Expected `applies.css` line drop after Stage 2: another ~150-250 lines.

### Stage 3 — INLINE-pure-non-leaf and INLINE-complex (sequential, controller-driven)

The cross-rule and complex cases are handled sequentially by the controller because:
- Non-leaf inlines require expanding the rule's contents into parent rules — touching `applies.css` AND call sites in coordinated edits.
- Complex inlines need case-by-case judgment (relocate to adjacent CSS vs. promote to KEEP), which a generic subagent prompt can't capture without per-rule briefing.

Per non-leaf rule:
1. Find every `@apply <ruleName> ...` directive in applies.css.
2. Replace `<ruleName>` with its expansion (the rule's own `@apply` list).
3. Inline at the 1-2 external call sites (same as INLINE-pure-leaf).
4. Delete the original rule.

Per complex rule:
1. If the rule has only 1 call site and the rule body is non-trivial CSS: relocate to a CSS file adjacent to the consumer (similar pattern to gradient-bg.css). Add an import in the consumer.
2. If the rule's body is small enough and the call site can absorb it via Tailwind arbitrary-value syntax (e.g. `[width:50px]`): inline.
3. Otherwise: promote to KEEP, leaving the rule intact and noting it in a follow-up.

### Stage 4 — Verification gate

The same five-step bar as the simple-sidebar work:
1. `cd src/frontend && npm run type-check` — only pre-existing TagRead errors allowed.
2. `cd src/frontend && npm run test -- --silent` — only pre-existing `SaveAsTemplateModal.test.tsx` failures allowed.
3. `cd src/frontend && npm run build` — production bundle succeeds.
4. `wc -l src/frontend/src/style/applies.css` — target ≤ 250 lines (~64% reduction from 687).
5. Grep sweep: every class name we deleted / inlined / relocated has zero references anywhere in `src/frontend/src` (excluding the relocated `gradient-bg.css` for the gradient names).

Manual eyeball — kicked off after commit, not before. The change is purely structural; the static checks are strong.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Grep-based usage count misses a dynamic class composition (`\`prefix-${variant}\``) and we delete a class that's actually live | Low-Medium | The build catches missing classes only at runtime, not compile-time, so this is the highest-risk failure mode. Mitigation: production build's `vite` step does NOT catch unused-but-referenced classes either. Stage 4 step 5's grep sweep is the only guard. Manual eyeball post-commit is the secondary guard. |
| Inlining a `@apply form-input ...` rule loses the `form-input` plugin class because the consumer doesn't realize it's a Tailwind plugin (from `@tailwindcss/forms`) | Low | When inlining, preserve `form-input` verbatim in the className. The subagent prompts must paste the @apply utility list character-for-character. |
| The `cn()` / `clsx()` composition at a call site already has a class that conflicts with the inlined utilities | Low | After inlining, run typecheck (won't catch this) and visual eyeball. The conflict produces a layout glitch, not a crash. |
| Relocated `gradient-bg.css` doesn't get loaded because Vite tree-shakes the import | Very Low | The import is side-effect-only (`import "./gradient-bg.css"`), Vite preserves these by default. The build step will fail if the import path is wrong. |
| A rule moved from KEEP-bucket to INLINE-bucket between audit and execution because someone deleted a call site in another branch | Very Low | Re-run the audit script before Stage 1 if the worktree is more than a day old. The audit is fast (~30s). |
| A rule's `@apply` references a `@utility` defined in `index.css` that I missed in the inventory | Low | The audit script captures both `^\s*\.<name>` and `^@utility <name>` patterns from `applies.css`. Anything in `index.css` is out of scope. If a rule's `@apply` includes such a name, the inline carries it through verbatim. |
| Subagent edits introduce a typo in a long Tailwind class string | Low | The plan paste-sends the `@apply` utility list verbatim from the audit script's output, so the subagent doesn't transcribe. Typecheck + build are the secondary catch. |

## Posture and constraints

| Dimension | Call |
|---|---|
| Delivery shape | Single coherent commit at the end. User opted for "ton of work before committing" cadence. |
| Branch target | `platform-multi-tenant`. No upstream PR (push to `fork`, fast-forward merge, push). |
| Worktree | `.worktrees/tailwind-applies-inline`. Standing user preference. |
| Commit hygiene | Stage explicit file paths only — never `git add -A`/`.`/`-a`. Pause and ask before commit. |
| Visual fidelity | "Indistinguishable at a glance." No design changes. |
| Testing | No new tests; rely on existing jest + Playwright (Playwright deferred to manual eyeball, same as last commit). |
| Subagent commit hygiene | Subagents never commit. Controller commits once at end. |
| Subagent file scope | Stage 2 subagents only touch JSX/TSX call sites. Controller mediates `applies.css` deletions. |

## Open questions

None. Bucketing rules, edge case treatments (gradient-bg cluster, case-by-case for complex), and pipeline structure are all resolved. Specific bucket assignments depend on the audit script run; the plan task list is structured to handle whatever the audit produces.
