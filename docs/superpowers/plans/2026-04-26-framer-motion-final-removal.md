# framer-motion final removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the last remaining `framer-motion` consumer to CSS, uninstall the dep, and flip four resolved tailwind followups.

**Architecture:** Replace `<AnimatePresence>` + `<motion.div>` in `flowBuildingComponent/index.tsx` with the established `useDelayedUnmount` hook + `grid-template-rows: 0fr ↔ 1fr` Tailwind pattern (the same recipe used in `disclosure.tsx`). Remove the `jest.mock("framer-motion", ...)` from the test file. `npm uninstall framer-motion`. Audit and flip four `[ ]` → `[x]` entries in `docs/superpowers/followups.md` that prior commits silently completed.

**Tech Stack:** React 18, Tailwind v4 (CSS-first), Jest + Testing Library, Vite, Biome.

**Standing rules (apply throughout):**
- Never push to `langflow-ai/langflow` (origin). Push only to `brycedeneen/langflow-mt` (fork).
- User has authorized **autonomous commits** for this slice — do not pause to ask before each commit.
- All execution happens inside a worktree (`superpowers:using-git-worktrees`); the parent checkout has unrelated WIP.
- Subagents stage explicit paths only (no `git add -A`/`.`/`-a`).

**Reference spec:** `docs/superpowers/specs/2026-04-26-framer-motion-final-removal-design.md`

**Spec correction (note):** the spec wrote `const showError = useDelayedUnmount(!!buildInfo?.error, 200);` — the actual API is `const { shouldRender, isVisible, handleExitTransitionEnd } = useDelayedUnmount(visible)`. The plan uses the correct API; spec drift is cosmetic and not worth a re-commit.

---

## File Map

- **Modify** `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx` — migrate from framer-motion to CSS recipe.
- **Modify** `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx` — remove `jest.mock("framer-motion", ...)`.
- **Modify** `src/frontend/package.json` — remove `framer-motion` dependency entry.
- **Modify** `src/frontend/package-lock.json` — pruned by `npm uninstall`.
- **Modify** `docs/superpowers/followups.md` — flip 4 entries from `[ ]` to `[x]`.

---

## Task 0: Set up worktree

**Files:** none (creates a new worktree)

- [ ] **Step 1: Create worktree off `platform-multi-tenant`**

```bash
git worktree add .worktrees/framer-motion-final -b tailwind/framer-motion-final platform-multi-tenant
```

Expected: worktree created at `/Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final` on a new branch `tailwind/framer-motion-final`. (`/Users/brycedeneen/dev/langflow/.gitignore:301` already ignores `.worktrees/`, verified during the prior slice.)

- [ ] **Step 2: Install frontend deps in the worktree**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npm install 2>&1 | tail -10
```

Expected: completes in 60–120s; warnings allowed; no errors.

- [ ] **Step 3: Verify clean baseline**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final && git status && git log --oneline -3
```

Expected: working tree clean. HEAD at the spec commit `7ea262b23b docs(tailwind): spec for framer-motion final removal` (or whatever current `platform-multi-tenant` HEAD is).

- [ ] **Step 4: Run baseline tests for the target component**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npx jest src/pages/FlowPage/components/flowBuildingComponent --colors 2>&1 | tail -20
```

Expected: tests pass (count varies). If any pre-existing failures surface, capture the count to compare against post-migration.

---

## Task 1: Migrate `flowBuildingComponent` to CSS + remove test mock + uninstall framer-motion

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx` (lines 1, 216–252)
- Modify: `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx` (lines 6–20)
- Modify: `src/frontend/package.json` + `src/frontend/package-lock.json` (`npm uninstall`)

User said one commit covers the migration + uninstall.

- [ ] **Step 1: Drop the `framer-motion` import**

In `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx`, delete line 1:

```tsx
import { AnimatePresence, motion } from "framer-motion";
```

`useDelayedUnmount` is already imported at line 11. `cn` is already imported at line 12. No new imports needed.

- [ ] **Step 2: Hook the unmount-gating state**

Inside the `FlowBuildingComponent` function body, add (place it near the other hooks — after the existing `useFlowStore` selectors and before the `useMemo`/`useEffect` blocks; e.g., right after line 30 where `buildFlow` is destructured):

```tsx
  const {
    shouldRender: shouldRenderError,
    isVisible: isErrorVisible,
    handleExitTransitionEnd: handleErrorTransitionEnd,
  } = useDelayedUnmount(!!buildInfo?.error);
```

- [ ] **Step 3: Replace the `<AnimatePresence>`/`<motion.div>` block**

Replace the JSX block at lines 216–252:

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
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ node, ...props }) => (
                          <a
                            {...props}
                            target="_blank"
                            className="underline"
                            rel="noopener noreferrer"
                          >
                            {props.children}
                          </a>
                        ),
                        p({ node, ...props }) {
                          return (
                            <span className="inline-block w-fit max-w-full align-text-top truncate-doubleline">
                              {props.children}
                            </span>
                          );
                        },
                      }}
                    >
                      {buildInfo?.error?.join("\n")}
                    </Markdown>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
```

With:

```tsx
            {shouldRenderError && (
              <div
                className={cn(
                  "grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-in-out",
                  isErrorVisible
                    ? "grid-rows-[1fr] opacity-100"
                    : "grid-rows-[0fr] opacity-0",
                )}
                onTransitionEnd={handleErrorTransitionEnd}
              >
                <div className="min-h-0 overflow-hidden">
                  <div className="my-1.5 align-text-top truncate-doubleline">
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ node, ...props }) => (
                          <a
                            {...props}
                            target="_blank"
                            className="underline"
                            rel="noopener noreferrer"
                          >
                            {props.children}
                          </a>
                        ),
                        p({ node, ...props }) {
                          return (
                            <span className="inline-block w-fit max-w-full align-text-top truncate-doubleline">
                              {props.children}
                            </span>
                          );
                        },
                      }}
                    >
                      {buildInfo?.error?.join("\n")}
                    </Markdown>
                  </div>
                </div>
              </div>
            )}
```

The Markdown rendering code is character-for-character identical to the original. Only the wrapping animation changes:
- `<AnimatePresence>` + `<motion.div initial/animate/exit>` → `{shouldRenderError && <div className="...transition...">...</div>}`
- The outer `<div>` provides the `grid-template-rows: 0fr ↔ 1fr` track animation.
- The middle `<div className="min-h-0 overflow-hidden">` is the inner row that collapses to 0 when the parent track is `0fr` (required by the recipe — without `min-h-0`, the row's intrinsic min-content prevents the collapse).
- The innermost `<div className="my-1.5 align-text-top truncate-doubleline">` is the original wrapper around the `Markdown` element, preserved so visual margins and truncation stay identical.
- `onTransitionEnd={handleErrorTransitionEnd}` triggers the unmount when the exit animation finishes.

- [ ] **Step 4: Remove the framer-motion test mock**

In `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx`, delete lines 6–20:

```tsx
// Mock dependencies
jest.mock("framer-motion", () => {
  const React = require("react");
  return {
    AnimatePresence: ({ children }: any) => <div>{children}</div>,
    motion: {
      div: React.forwardRef(
        ({ children, className, ...props }: any, ref: any) => (
          <div ref={ref} className={className} {...props}>
            {children}
          </div>
        ),
      ),
    },
  };
});
```

Leave the comment `// Mock dependencies` if it precedes other mocks naturally; if it leaves an orphan comment with nothing after it, delete the comment line too. Do NOT touch the other `jest.mock(...)` blocks (`react-markdown`, `remark-gfm`, `format-run-time`, `genericIconComponent`).

- [ ] **Step 5: Run the component test before uninstalling**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npx jest src/pages/FlowPage/components/flowBuildingComponent --colors 2>&1 | tail -20
```

Expected: same pass/fail count as the Task 0 baseline. The test was previously mocking `framer-motion` to render plain `<div>`s; the migrated code emits real `<div>`s with the same children, so the test's DOM expectations should still match.

- [ ] **Step 6: Uninstall framer-motion**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npm uninstall framer-motion 2>&1 | tail -5
```

Expected: `removed N packages` in the output. `package.json` no longer lists `framer-motion` under `dependencies`. `package-lock.json` is pruned. `node_modules/framer-motion` is gone.

- [ ] **Step 7: Verify zero residual `framer-motion` references**

```bash
grep -rn "framer-motion" /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend/src
```

Expected matches (historical comments — keep them):
- `src/frontend/src/utils/useDelayedUnmount.ts:4`
- `src/frontend/src/components/ui/disclosure.tsx:150`

Any *import* or *jest.mock* hit is a regression — fix before continuing.

```bash
grep -E '"framer-motion"' /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend/package.json
```

Expected: 0 matches.

- [ ] **Step 8: Run typecheck**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npx tsc --noEmit 2>&1 | tail -10
```

Expected: 0 new errors. The 2 pre-existing errors (`use-add-flow.ts:126`, `use-handle-duplicate.ts:24`) may still be present — those are unrelated and acceptable.

- [ ] **Step 9: Run a wider test sanity pass**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npx jest src/pages/FlowPage src/components/ui --colors 2>&1 | tail -20
```

Expected: same pre-existing failure count as elsewhere in the app (the 14 `SaveAsTemplateModal` failures observed during the prior slice are not in the test paths we just ran here, so total counts should be clean).

- [ ] **Step 10: Run lint on the touched files**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/src/frontend && npx @biomejs/biome lint \
  src/pages/FlowPage/components/flowBuildingComponent/index.tsx \
  src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx \
  package.json 2>&1 | tail -10
```

Expected: no new errors. Pre-existing warnings (e.g., `noExplicitAny` in the test file for `({ ...props }: any)` patterns) are acceptable.

- [ ] **Step 11: Commit (autonomous — user authorized)**

```bash
git add src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx \
        src/frontend/src/pages/FlowPage/components/flowBuildingComponent/__tests__/index.test.tsx \
        src/frontend/package.json \
        src/frontend/package-lock.json
git commit -m "$(cat <<'EOF'
chore(frontend): drop final framer-motion consumer + uninstall dep

Migrates the lone <AnimatePresence>+<motion.div> in
flowBuildingComponent (error-message height/opacity transition) to the
established CSS recipe used in disclosure.tsx — useDelayedUnmount for
exit-gating + grid-template-rows: 0fr↔1fr Tailwind classes for the
height animation. Test mock removed; framer-motion uninstalled from
package.json + package-lock.json. Closes the Phase 7+ followup that
dropped to 1 consumer after Phase 7a.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Verify with `git log -1 --oneline` and `git show --stat HEAD`. Expected: 4 files in the diff (index.tsx, test file, package.json, package-lock.json).

---

## Task 2: Flip four resolved tailwind followups

**Files:**
- Modify: `docs/superpowers/followups.md` — four entries.

The four flips are:

| Followup heading | Old bullet | New bullet | Resolved by |
|---|---|---|---|
| `## 2026-04-24 — Tailwind Maximization Phase 1 deferrals` → `### Chakra number-input replacement` (line 174) | `- [ ] **\`@chakra-ui/number-input\` is still consumed.** ...` | Flip to `- [x] **RESOLVED (2026-04-26 by 820ae77865):** \`@chakra-ui/number-input\` replaced with stock \`<input type="number">\`. ...` | `820ae77865` |
| `## 2026-04-24 — Tailwind Maximization Phase 2 deferrals` → `### animated-close (AnimatedConditional) — blocked by simple-sidebar` (line 194) | `- [ ] **\`src/components/ui/animated-close.tsx\` exports \`AnimatedConditional\`...** ...` | Flip to `- [x] **RESOLVED (2026-04-26 by ea5f6108d9):** \`animated-close.tsx\` deleted as part of the simple-sidebar→resizable-sidebar rename. ...` | `ea5f6108d9` |
| `## 2026-04-24 — Tailwind Maximization Phase 2 deferrals` → `### border-trail` (line 198) | `- [ ] **\`src/components/core/border-trail.tsx\` uses framer-motion...** ...` | Flip to `- [x] **RESOLVED (2026-04-26 by 8e7b84f7f8):** \`border-trail\` framer-motion wrapper dropped (decorative effect removed). ...` | `8e7b84f7f8` |
| `## 2026-04-24 — Tailwind Maximization Phase 7+ deferrals (post-plan)` → `### 7a — Full \`framer-motion\` removal` (line 246) | `- [ ] **framer-motion import count is currently 14**...` | Flip to `- [x] **RESOLVED (2026-04-26 by this slice):** \`framer-motion\` fully uninstalled from \`package.json\`. Last consumer (\`flowBuildingComponent/index.tsx\`) migrated to CSS via the \`disclosure.tsx\` recipe. ...` | This slice |

For each, **preserve the original detail text below the lead sentence** so the historical context is retained for traceability — only the leading sentence gets the `[x] RESOLVED (...)` prefix and a one-line summary of the outcome.

- [ ] **Step 1: Apply the four edits**

Open `docs/superpowers/followups.md` and apply each flip. Use precise old/new strings since the bullets contain backticks; the Edit tool's `old_string` must match exactly.

For Line 174 — find:

```markdown
- [ ] **`@chakra-ui/number-input` is still consumed.** Call sites: `src/components/core/parameterRenderComponent/components/floatComponent/index.tsx:7` and `.../intComponent/index.tsx:7`. Removing the dep requires replacing the `<NumberInput>` primitive with either a plain `<input type="number">` + Tailwind styling, or a Radix-based equivalent. Plan Phase 1 opted to delete only the fully-unused Chakra dep (`@chakra-ui/system`) and leave this one until the two call sites can be migrated.
```

Replace with:

```markdown
- [x] **RESOLVED (2026-04-26 by `820ae77865`):** `@chakra-ui/number-input` replaced with stock `<input type="number">`; both call sites (`floatComponent`, `intComponent`) migrated; chakra dep fully gone from `package.json`. Original context: removing the dep required replacing the `<NumberInput>` primitive with either a plain `<input type="number">` + Tailwind styling, or a Radix-based equivalent. Plan Phase 1 opted to delete only the fully-unused Chakra dep (`@chakra-ui/system`) and leave this one until the two call sites could be migrated — that migration shipped under commit `820ae77865`.
```

For Line 194 — find:

```markdown
- [ ] **`src/components/ui/animated-close.tsx` exports `AnimatedConditional`, consumed by `ui/simple-sidebar.tsx`, playground `chat-header.tsx`, and `flow-page-sliding-container.tsx`.** Because Phase 1 deferred `simple-sidebar.tsx` removal (it has unique resize/drag features vs. `ui/sidebar`), we can't fully delete `animated-close` without also rewriting `simple-sidebar`. The component animates `width: 0 → auto`, which CSS can't do with a single `transition-[width]` — needs a `grid-template-columns: 0fr → 1fr` trick (Tailwind arbitrary) or a JS width-measurement helper. Bundle this with the simple-sidebar resolution.
```

Replace with:

```markdown
- [x] **RESOLVED (2026-04-26 by `ea5f6108d9`):** `animated-close.tsx` deleted as part of the simple-sidebar→resizable-sidebar rename + cleanup commit. The `AnimatedConditional` consumers were migrated alongside the rename. Original context: the component animated `width: 0 → auto`, which CSS can't do with a single `transition-[width]` — required a `grid-template-columns: 0fr → 1fr` trick or JS width-measurement helper. The simple-sidebar→resizable-sidebar work supplied the migration; `animated-close.tsx` is gone.
```

For Line 198 — find:

```markdown
- [ ] **`src/components/core/border-trail.tsx` uses framer-motion to animate `offsetDistance` along a rounded-rect `offsetPath`** (2 production consumers: `chatComponents/ContentBlockDisplay.tsx` and `pages/FlowPage/components/flowBuildingComponent/index.tsx`, plus `jest.mock` in the flowBuilding test). Pure CSS has no direct offset-path animation support; replacement options are (a) drop the effect entirely, (b) SVG-path alternative, (c) custom CSS keyframes mimicking the gradient around the border. All three need a design decision on whether the trail is decorative or status-bearing. Deferred.
```

Replace with:

```markdown
- [x] **RESOLVED (2026-04-26 by `8e7b84f7f8`):** `border-trail` decorative framer-motion wrapper dropped. The effect was decorative, not status-bearing, and was removed cleanly (option (a) from the original deferral). Both production consumers (`ContentBlockDisplay`, `flowBuildingComponent`) updated; jest mock removed alongside.
```

For Line 246 — find:

```markdown
- [ ] **framer-motion import count is currently 14** (was 19; TextShimmer turned out to already be CSS-only — see resolution above). Full removal from `package.json` requires handling the remaining 14 consumers under `src/frontend/src/**/*.tsx`: `AnimatedConditional` (3 call sites including the deferred `simple-sidebar.tsx`), `BorderTrail` (2 call sites), `disclosure`, `checkmark`, `xmark`, `animatedNumbers`, `chat-input` (IOModal + playground), `content-view`, `error-message`, `ContentBlockDisplay`, `InspectionPanel`, `UpdateAllComponents`, `flowBuildingComponent`. See the Phase 2 deferrals section above for per-component strategies. Once all consumers are migrated, `npm uninstall framer-motion` and confirm `grep -rn "framer-motion" src` returns zero.
```

Replace with:

```markdown
- [x] **RESOLVED (2026-04-26 by this slice):** `framer-motion` fully uninstalled from `src/frontend/package.json`. The 14-consumer count was stale by the time this loop closed — Phase 7a (`83e9b10cf7`), the `chore/framer-motion-removal` merge (`7eb956edb6`), and targeted commits for `BorderTrail` (`8e7b84f7f8`), `TextShimmer` (`0c4ac8db8e`), and `animated-close`/`simple-sidebar` (`ea5f6108d9`) collectively dropped the import count from 19 → 1. The lone holdout (`flowBuildingComponent/index.tsx`) was migrated to the `disclosure.tsx` CSS recipe (`useDelayedUnmount` + `grid-template-rows: 0fr↔1fr`) in this slice. `grep -rn "framer-motion" src` now returns only the historical comments in `useDelayedUnmount.ts:4` and `disclosure.tsx:150`.
```

- [ ] **Step 2: Verify the four flips landed**

```bash
grep -n "RESOLVED (2026-04-26" /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/docs/superpowers/followups.md | head -20
```

Expected: at least four lines, all with the new resolution prefix.

```bash
grep -c "^- \[x\]" /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final/docs/superpowers/followups.md
```

Expected: at least 4 more checked items than before. (Some `[x]` entries already existed from prior cleanups, so the count should INCREASE by 4.)

- [ ] **Step 3: Commit (autonomous)**

```bash
git add docs/superpowers/followups.md
git commit -m "$(cat <<'EOF'
docs: flip resolved tailwind followups (chakra, animated-close, border-trail, framer-motion)

Four entries that prior commits silently completed:
- chakra number-input — resolved by 820ae77865
- animated-close (AnimatedConditional) — resolved by ea5f6108d9
- border-trail framer-motion — resolved by 8e7b84f7f8
- framer-motion 14-consumer entry — resolved by this slice

Original context preserved beneath the new RESOLVED prefix for
traceability.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: ff-merge + push to fork + worktree cleanup

**Files:** none (git operations only).

- [ ] **Step 1: Verify the worktree branch is ready**

From the worktree:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final && git log --oneline platform-multi-tenant..HEAD
```

Expected: 2 commits — `chore(frontend): drop final framer-motion consumer + uninstall dep` and `docs: flip resolved tailwind followups ...`.

- [ ] **Step 2: Switch to the parent checkout**

`cd /Users/brycedeneen/dev/langflow`.

```bash
git rev-parse --abbrev-ref HEAD
```

Expected: `platform-multi-tenant`.

- [ ] **Step 3: Check parent's HEAD vs the rebase base**

```bash
git rev-parse HEAD
```

If the parent's `platform-multi-tenant` HEAD has advanced since the worktree was created (i.e., is newer than `7ea262b23b` or whatever you started from), rebase the worktree branch onto the new HEAD before merging. Pattern from the prior slice:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/framer-motion-final && git rebase platform-multi-tenant && cd /Users/brycedeneen/dev/langflow
```

Verify the rebase succeeded with `git log --oneline platform-multi-tenant..tailwind/framer-motion-final` from the worktree (should still show 2 commits, possibly with new SHAs).

- [ ] **Step 4: Fast-forward merge**

```bash
git merge --ff-only tailwind/framer-motion-final
```

Expected: `Updating <old>..<new>` and a `Fast-forward` line. If `--ff-only` refuses, the parent advanced again — re-rebase per Step 3.

- [ ] **Step 5: Push to fork (NOT origin)**

```bash
git push fork platform-multi-tenant
```

Expected: `<old>..<new>  platform-multi-tenant -> platform-multi-tenant`. **NEVER `git push origin`** — origin is `langflow-ai/langflow` and the standing rule forbids pushing there.

- [ ] **Step 6: Clean up the worktree**

```bash
git worktree remove .worktrees/framer-motion-final
git branch -d tailwind/framer-motion-final
```

Expected: branch deletion succeeds (`-d` is safety-checked — refuses if commits aren't merged). If `-d` complains, do NOT use `-D`; investigate first.

- [ ] **Step 7: Final sanity check**

```bash
git log --oneline -5
git worktree list
```

Expected: top of log shows the 2 new commits, then the spec commit, then prior history. Worktree list shows only the primary checkout.

---

## Self-Review Checklist (run after writing this plan)

1. **Spec coverage:**
   - Spec §"Scope > In" item 1 (migrate flowBuildingComponent) → Task 1 Steps 1–3. ✓
   - Spec §Scope item 2 (update test mock) → Task 1 Step 4. ✓
   - Spec §Scope item 3 (npm uninstall) → Task 1 Step 6. ✓
   - Spec §Scope item 4 (verify zero residual refs) → Task 1 Step 7. ✓
   - Spec §Scope item 5 (flip 4 followups) → Task 2 Steps 1–3. ✓
   - Spec §Test impact → Task 1 Steps 5, 9. ✓
   - Spec §Risks (200ms unmount window, grid-template-rows browser support, test mock removal) → covered in Task 1 narration + tests. ✓

2. **Placeholder scan:** No "TBD"/"TODO"/"appropriate"/"handle edge cases". All test code shown literally. All file paths are absolute or workspace-relative.

3. **Type consistency:** `useDelayedUnmount` signature matches the actual one (`{ shouldRender, isVisible, handleExitTransitionEnd }`) — corrected from the spec's compressed form. Variable names (`shouldRenderError`, `isErrorVisible`, `handleErrorTransitionEnd`) are consistent across Steps 2, 3, and the verification commands.

4. **Spec correction note** at the top of the plan calls out the API drift (spec wrote `useDelayedUnmount(condition, ms)` returning a single boolean; actual API returns an object). Plan uses the actual API. No re-spec-commit needed.
