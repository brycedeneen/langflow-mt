# Tailwind Maximization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the frontend's custom-CSS and custom-component surface area so it sits as close to stock Tailwind v4 + shadcn/Radix as possible, in 6 independently-shippable phases, without user-perceivable visual regressions.

**Architecture:** Six risk-ascending phases, each landing as its own commit series on `platform-multi-tenant`. Every phase has a discovery step (grep-based usage maps), an implementation step, and a verification gate (typecheck + jest + Playwright + production build + eyeball the five anchor surfaces) before commit. No upstream PR.

**Tech Stack:** React 19, TypeScript, Tailwind v4 (CSS-first config in `src/frontend/src/style/index.css`), shadcn primitives wrapping Radix, Jest for unit tests, Playwright for e2e, Biome for lint/format, `tw-animate-css` for animation utilities.

**Spec:** `docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md`

**Standing instructions (from user's memory / AGENTS.md):**
- **Never `git commit` without asking.** Every commit step in this plan has an explicit "pause and ask" instruction — honor it literally.
- **Stage explicit file paths.** Never use `git add -A`, `git add .`, or `git commit -a`. The repo has unrelated WIP (see `git status`); always `git add <specific/paths>`.
- **No upstream PRs.** All work lands on `platform-multi-tenant` (the effective main for this fork).
- **Jest, not Vitest.** Frontend tests run with `npm run test` (jest).

---

## Pre-flight — Baseline captures

Before any phase starts, capture baseline numbers so later phases can prove they moved the needle.

**Files:**
- Read-only during this task. No writes.

- [x] **Step 1: Confirm working tree state**

Run: `git status --short`
Expected: You should see pre-existing modified files from other in-progress work (platform-multi-tenant, tools modal, etc.) — that's fine, it's WIP from the user. **Do not touch or stage any of those files.** Only stage files you explicitly modify as part of this plan.

- [x] **Step 2: Capture baseline metrics to a scratch file**

Run (from repo root):
```bash
mkdir -p /tmp/tailwind-max-baseline
cd src/frontend
wc -l src/style/index.css src/style/applies.css src/style/classes.css src/style/App.css > /tmp/tailwind-max-baseline/css-line-counts.txt
grep -c "^\s*--color-" src/style/index.css > /tmp/tailwind-max-baseline/color-token-count.txt
grep -rn "framer-motion" src --include="*.ts" --include="*.tsx" | wc -l > /tmp/tailwind-max-baseline/framer-motion-import-count.txt
ls src/components/ui/ > /tmp/tailwind-max-baseline/ui-primitives-list.txt
cd ../..
```

Expected: files created with numbers. These are the "before" measurements referenced in phase acceptance criteria.

- [x] **Step 3: Confirm baseline test suite passes**

Run: `cd src/frontend && npm run type-check && npm run test -- --passWithNoTests --silent`
Expected: Typecheck clean. Jest passes. If jest has any pre-existing failures, record them in `/tmp/tailwind-max-baseline/preexisting-jest-failures.txt` so later phases don't get blamed for them.

- [x] **Step 4: Confirm the dev server builds**

Run: `cd src/frontend && npm run build`
Expected: Production bundle builds without errors. Note the output bundle size to `/tmp/tailwind-max-baseline/bundle-size.txt` (grep the vite build output for the final asset sizes).

- [x] **Step 5: Run Playwright e2e baseline**

Run: `make tests_frontend` (from repo root)
Expected: Suite passes. If any pre-existing failures, log to `/tmp/tailwind-max-baseline/preexisting-playwright-failures.txt` and continue. Later phase verification will ignore pre-existing failures but flag any new ones.

---

## Phase 1 — Dead code & unused styling deps

**Purpose:** Remove unused/duplicated code with zero call-site risk. Warm-up phase; builds confidence before anything with churn.

**Expected diff shape:** One file deletion, one dep removal, possibly one file-audit result. No component call-site edits expected.

### Task 1.1 — Audit `@emotion/*` and `@chakra-ui/*` usage

**Files:**
- Read-only: `src/frontend/src/**/*.{ts,tsx}`

- [x] **Step 1: Grep for emotion imports**

Run (from repo root):
```bash
grep -rn "from ['\"]@emotion/react['\"]" src/frontend/src --include="*.ts" --include="*.tsx"
grep -rn "from ['\"]@emotion/styled['\"]" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: likely zero results. If zero, `@emotion/*` is unused and safe to remove.

- [x] **Step 2: Grep for chakra imports**

Run:
```bash
grep -rn "@chakra-ui" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: possibly 1–2 usages. Record every file path found — those are the call sites that need to be migrated before the dep can be removed.

- [x] **Step 3: Record findings**

Write a short note to `/tmp/tailwind-max-baseline/dep-audit.txt` with one section per package: `unused` or `used-at: <paths>`. This drives the decisions in Task 1.2.

### Task 1.2 — Remove confirmed-unused styling deps

**Files:**
- Modify: `src/frontend/package.json`
- Modify: `src/frontend/package-lock.json` (via `npm install`)

- [x] **Step 1: Remove unused deps from `package.json`**

Edit `src/frontend/package.json`. Remove any of `@emotion/react`, `@emotion/styled`, `@chakra-ui/number-input`, `@chakra-ui/system` that the Task 1.1 audit marked `unused`. Do NOT remove packages still in use — those become follow-up work (see Task 1.2 Step 4 below).

- [x] **Step 2: Re-install to update lockfile**

Run: `cd src/frontend && npm install`
Expected: lockfile updates, no errors. Node modules shrinks.

- [x] **Step 3: Typecheck still passes**

Run: `cd src/frontend && npm run type-check`
Expected: Pass.

- [x] **Step 4: If any dep was still used, document for follow-up**

If Task 1.1 found real usage of any of these packages, append to `docs/superpowers/followups.md` a one-line entry: `- Migrate <package> call site at <path> and remove dep (discovered during Tailwind Maximization Phase 1, 2026-04-22).` Do NOT attempt to migrate the call site in this phase.

### Task 1.3 — Audit `src/frontend/src/style/classes.css`

**Files:**
- Read-only: `src/frontend/src/style/classes.css`, plus grep the rest of frontend.

- [x] **Step 1: Extract every selector defined in `classes.css`**

Run (from repo root):
```bash
grep -E "^\.[a-zA-Z]" src/frontend/src/style/classes.css | sed 's/^\.//' | awk '{print $1}' | sed 's/[:,{].*$//' | sort -u > /tmp/tailwind-max-baseline/classes-css-selectors.txt
wc -l /tmp/tailwind-max-baseline/classes-css-selectors.txt
```
Expected: a list of class names, one per line.

- [x] **Step 2: For each selector, check if it's referenced anywhere**

Run (from repo root):
```bash
cd src/frontend
while read -r selector; do
  count=$(grep -rn "\b${selector}\b" src --include="*.ts" --include="*.tsx" --include="*.css" --include="*.html" 2>/dev/null | grep -v "src/style/classes.css" | wc -l | tr -d ' ')
  echo "${count} ${selector}"
done < /tmp/tailwind-max-baseline/classes-css-selectors.txt | sort -n > /tmp/tailwind-max-baseline/classes-css-usage.txt
cd ../..
```
Expected: a usage-count table. Selectors with count `0` are dead.

- [x] **Step 3: Decide fate of `classes.css`**

Inspect `/tmp/tailwind-max-baseline/classes-css-usage.txt`:
- If **every** selector has count 0: the file is fully dead → Task 1.4 will delete it.
- If some selectors are live: record the live selectors and which files use them → Task 1.4 will relocate live selectors into either `App.css` (if they're react-flow / ag-grid overrides) or the single consuming component's adjacent `.css` file, then delete `classes.css`.

Write the decision + live-selector relocation targets to `/tmp/tailwind-max-baseline/classes-css-plan.txt`.

### Task 1.4 — Act on `classes.css` audit result

**Files:**
- Delete: `src/frontend/src/style/classes.css` (if fully dead, OR after relocating live selectors)
- Modify: `src/frontend/src/index.tsx:7` (remove the import line)
- Modify (conditional): `src/frontend/src/App.css` or specific consuming component's CSS (if any selectors were live)

- [x] **Step 1: Relocate any live selectors**

If `/tmp/tailwind-max-baseline/classes-css-plan.txt` lists live selectors, for each one:
- Copy the full CSS rule (selector + declarations) from `classes.css` to the target file identified in the plan.
- Preserve the rule verbatim. Do not re-tailwindify it — that's Phase 4 / Phase 6's job.

- [x] **Step 2: Delete `classes.css`**

Run (from repo root):
```bash
git rm src/frontend/src/style/classes.css
```
Expected: file removed.

- [x] **Step 3: Remove the import from `index.tsx`**

Edit `src/frontend/src/index.tsx`. Delete the line `import "./style/classes.css";`.

- [x] **Step 4: Typecheck + build**

Run:
```bash
cd src/frontend && npm run type-check && npm run build
```
Expected: Both pass. If build errors mention missing CSS, you missed a live selector — back out the deletion, re-audit, relocate, retry.

### Task 1.5 — Delete `simple-sidebar.tsx`

**Files:**
- Delete: `src/frontend/src/components/ui/simple-sidebar.tsx`
- Modify: any file importing it.

- [x] **Step 1: Find every import site**

Run (from repo root):
```bash
grep -rn "simple-sidebar" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: a list of imports. For each, note whether it imports `simple-sidebar` or the real `sidebar`.

- [x] **Step 2: Migrate every `simple-sidebar` import to `sidebar`**

For every file that imports from `ui/simple-sidebar`, change the import to `ui/sidebar` and verify the API it was calling (`SidebarProvider`, `SidebarTrigger`, etc.) exists in `ui/sidebar`. The two are near-duplicates; if a prop or export name differs, update the call site to match the `ui/sidebar` API.

If any usage depends on behavior unique to `simple-sidebar` that `sidebar` doesn't provide, stop and escalate — don't force the migration. In that case, leave `simple-sidebar.tsx` in place and record the blocking reason in `/tmp/tailwind-max-baseline/simple-sidebar-blocker.txt`, then skip Step 3.

- [x] **Step 3: Delete the file**

Run (from repo root):
```bash
git rm src/frontend/src/components/ui/simple-sidebar.tsx
```

- [x] **Step 4: Typecheck + jest + build**

Run: `cd src/frontend && npm run type-check && npm run test -- --silent && npm run build`
Expected: All pass.

### Task 1.6 — Phase 1 verification gate

**Files:** None modified this task.

- [x] **Step 1: Full per-phase verification bar**

Run all of the following, all must pass:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: Clean across the board (ignoring any pre-existing failures logged in pre-flight Step 5).

- [x] **Step 2: Manual eyeball of the five anchor surfaces**

Start the dev server: `make frontend` (vite on port 3000, backend on 7860).

Visit and verify no obvious breakage:
1. Flow canvas (`/flows/<any>`) — flow loads, nodes render, connections draw.
2. Playground (open a flow, click Playground) — chat input renders, messages display.
3. Settings page (`/settings/general`) — layout intact.
4. Admin → Users page — table renders.
5. Admin → Organizations page — list renders.

No pixel-perfect comparison needed — just no broken layouts, missing components, or console errors.

- [x] **Step 3: Pause and ask for commit permission**

Write a short summary of what changed in Phase 1 (which deps were removed, whether `classes.css` was fully dead or partially relocated, whether `simple-sidebar.tsx` was deletable). Then ask the user: *"Phase 1 complete and verified. OK to commit?"*

**Do NOT commit without explicit approval.**

- [x] **Step 4: Commit (after approval)**

Stage only the files this phase modified. Example (adjust paths to match reality):
```bash
git add src/frontend/package.json src/frontend/package-lock.json \
        src/frontend/src/index.tsx \
        src/frontend/src/style/classes.css \
        src/frontend/src/components/ui/simple-sidebar.tsx
# plus any migrated call sites / relocated-selector targets
```

Do NOT use `git add -A` or `git add .`. Only stage files explicitly touched by Phase 1.

Commit with a descriptive message:
```bash
git commit -m "$(cat <<'EOF'
chore(frontend): tailwind-max phase 1 — dead code and unused styling deps

- remove unused @emotion/*, @chakra-ui/* deps (if confirmed)
- audit and delete/relocate src/style/classes.css
- delete duplicate ui/simple-sidebar.tsx, migrate to ui/sidebar

Phase 1 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Phase 2 — Decorative framer-motion purge

**Purpose:** Delete UI decorative primitives that use framer-motion for low-value visual flourishes. Keep `framer-motion` in `package.json` for now (other consumers remain).

**Expected diff shape:** 7 component files deleted; ≤2 call-site edits per component on average.

### Task 2.1 — Enumerate call sites per decorative component

**Files:**
- Read-only.

For each of these seven components:
- `src/frontend/src/components/ui/background-gradient.tsx`
- `src/frontend/src/components/ui/dot-background.tsx`
- `src/frontend/src/components/ui/text-loop.tsx`
- `src/frontend/src/components/ui/textAnimation.tsx`
- `src/frontend/src/components/ui/TextShimmer.tsx`
- `src/frontend/src/components/ui/animated-close.tsx`
- `src/frontend/src/components/core/border-trail.tsx`

- [x] **Step 1: Grep each for import sites**

Run (from repo root):
```bash
for f in background-gradient dot-background text-loop textAnimation TextShimmer animated-close border-trail; do
  echo "=== $f ==="
  grep -rn "$f" src/frontend/src --include="*.ts" --include="*.tsx" | grep -v "src/frontend/src/components/ui/$f\|src/frontend/src/components/core/$f"
done > /tmp/tailwind-max-baseline/decorative-call-sites.txt
cat /tmp/tailwind-max-baseline/decorative-call-sites.txt
```
Expected: for each component, a list of call sites (possibly zero).

### Task 2.2 — Replace each call site with a stock-Tailwind equivalent

**Files:**
- Modify: every file listed in `/tmp/tailwind-max-baseline/decorative-call-sites.txt`.

For every call site, decide the replacement using these rules:

| Original component | Replacement |
|---|---|
| `<BackgroundGradient />` | delete the element (it was a pure decorative wrapper), OR replace with a plain `<div>` keeping any non-visual children. |
| `<DotBackground />` | delete, or replace with a plain `<div>` keeping children. |
| `<TextLoop>...</TextLoop>` | if a single static string works visually, replace with that string. Otherwise, replace with a plain element cycling via `setInterval` in a `useEffect` — only if the call site genuinely needs rotation. Don't write a new wrapper. |
| `<TextAnimation>text</TextAnimation>` | replace with the raw `text` wrapped in `<span className="...animate-in fade-in duration-500">` (tw-animate-css). |
| `<TextShimmer>text</TextShimmer>` | replace with plain `<span>text</span>` unless the shimmer was load-bearing UX feedback (rare). |
| `<AnimatedClose />` | replace with a plain `<X className="h-4 w-4 transition-transform hover:rotate-90" />` (lucide icon + Tailwind transition). |
| `<BorderTrail />` | delete or replace with a plain border + Tailwind transition if the element needs emphasis. |

- [x] **Step 1: Do one component at a time**

For each of the 7 components, make the call-site edits, then run `cd src/frontend && npm run type-check`. If typecheck passes, move to the next. If it fails, fix the call site — don't batch mistakes.

- [x] **Step 2: After all 7 are done, delete the components**

Run (from repo root):
```bash
git rm src/frontend/src/components/ui/background-gradient.tsx \
       src/frontend/src/components/ui/dot-background.tsx \
       src/frontend/src/components/ui/text-loop.tsx \
       src/frontend/src/components/ui/textAnimation.tsx \
       src/frontend/src/components/ui/TextShimmer.tsx \
       src/frontend/src/components/ui/animated-close.tsx \
       src/frontend/src/components/core/border-trail.tsx
```

- [x] **Step 3: Confirm framer-motion import count dropped**

Run (from repo root):
```bash
grep -rn "framer-motion" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
```
Compare to `/tmp/tailwind-max-baseline/framer-motion-import-count.txt`. The new count should be lower; if it equals the baseline, one of the 7 components wasn't actually deleted or the call-site migration left a straggler import.

### Task 2.3 — Phase 2 verification gate

**Files:** None modified this task.

- [x] **Step 1: Full per-phase verification bar**

Run:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: All pass.

- [x] **Step 2: Manual eyeball of the five anchor surfaces + any surface that used deleted components**

Review `/tmp/tailwind-max-baseline/decorative-call-sites.txt` — the files listed tell you which pages used the deleted components. Visit each one in the running dev server and confirm no broken layout. Also re-check the five anchor surfaces.

- [x] **Step 3: Pause and ask for commit permission**

Summarize: which 7 components deleted, how many call sites migrated, whether the framer-motion import count dropped as expected. Ask the user: *"Phase 2 complete and verified. OK to commit?"*

- [x] **Step 4: Commit (after approval)**

Stage only this phase's files:
```bash
git add src/frontend/src/components/ui/background-gradient.tsx \
        src/frontend/src/components/ui/dot-background.tsx \
        src/frontend/src/components/ui/text-loop.tsx \
        src/frontend/src/components/ui/textAnimation.tsx \
        src/frontend/src/components/ui/TextShimmer.tsx \
        src/frontend/src/components/ui/animated-close.tsx \
        src/frontend/src/components/core/border-trail.tsx
# plus every call-site file from decorative-call-sites.txt
```

Commit:
```bash
git commit -m "$(cat <<'EOF'
chore(frontend): tailwind-max phase 2 — delete decorative framer-motion primitives

Deletes 7 UI decorative components and migrates their call sites to plain
Tailwind + tw-animate-css equivalents. framer-motion dep stays (other
consumers remain); full removal deferred to Phase 7a per the spec.

Phase 2 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Phase 3 — Theme indirection flatten

**Purpose:** Mechanical refactor of `src/frontend/src/style/index.css` so `--color-*` tokens point at literal values (or a single HSL pair) instead of alias-of-alias chains. No JSX/TSX changes; no call-site churn.

**Expected diff shape:** Changes concentrated in `index.css` only, ~100 lines touched.

### Task 3.1 — Snapshot computed color values before the change

**Files:**
- Read-only.

- [x] **Step 1: Extract every `--color-*` token and its current right-hand side**

Run (from repo root):
```bash
grep -E "^\s*--color-" src/frontend/src/style/index.css | sed 's/^\s*//' | sort > /tmp/tailwind-max-baseline/color-tokens-before.txt
wc -l /tmp/tailwind-max-baseline/color-tokens-before.txt
```
Expected: ~189 lines (per survey). The file captures the pre-phase state.

- [x] **Step 2: Build a reference file of computed values**

For each token, trace the chain: if the RHS is `var(--foo)`, look up `--foo` elsewhere in `index.css` (in the `:root` / `.dark` / `html` blocks outside `@theme`) and record its value. For tokens wrapped in `hsl(var(--foo))`, record the full HSL triple plus `hsl(...)` wrapper.

Save as `/tmp/tailwind-max-baseline/color-tokens-resolved-before.txt`, one per line: `<token-name> <ultimate-value>`.

This step is the contract for Task 3.3's diff check.

### Task 3.2 — Flatten the `@theme` block

**Files:**
- Modify: `src/frontend/src/style/index.css` (`@theme` block only)

- [x] **Step 1: Replace alias RHS with literal value**

For each `--color-*: var(--foo);` line in the `@theme` block, replace `var(--foo)` with the ultimate value you recorded in Task 3.1 Step 2. Preserve any `hsl(...)`, `rgb(...)`, or `rgba(...)` wrapper that was there — only collapse the `var()` indirection.

Example before:
```css
--color-medium-gray: var(--medium-gray);
```
Example after:
```css
--color-medium-gray: hsl(240, 4%, 46%);   /* whatever --medium-gray resolved to */
```

Do this for **all** `--color-*` tokens in the `@theme` block. The `:root` / `.dark` / `html` blocks are unchanged in this task.

- [x] **Step 2: Identify now-orphaned CSS variables**

Any CSS variable defined in `:root` / `.dark` / `html` that existed only to feed a `--color-*` alias is now unused. Grep to confirm zero remaining references, then delete them.

Run (from repo root):
```bash
grep -rn "var(--medium-gray)" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css"
```
(Replace `--medium-gray` with each candidate name.)

If grep returns zero results: delete the variable definition from the `:root` / `.dark` block. If it returns results: the variable is still load-bearing somewhere outside `@theme` — leave it alone in this phase. Any live `var(--foo)` call-site cleanup is Phase 6's problem.

- [x] **Step 3: Verify no syntax errors in the file**

Run: `cd src/frontend && npm run build`
Expected: Build succeeds. Vite parses the CSS; a syntax error will fail the build immediately.

### Task 3.3 — Verify no computed value changed

**Files:** Read-only.

- [x] **Step 1: Re-extract resolved values**

Repeat Task 3.1 Step 2 against the modified `index.css`. Save as `/tmp/tailwind-max-baseline/color-tokens-resolved-after.txt`.

- [x] **Step 2: Diff before vs after**

Run:
```bash
diff /tmp/tailwind-max-baseline/color-tokens-resolved-before.txt \
     /tmp/tailwind-max-baseline/color-tokens-resolved-after.txt
```
Expected: **empty output**. Any non-empty diff means a token's final computed value changed — Phase 3 violates its "no numerical change" acceptance criterion. Back out the change, fix, retry.

### Task 3.4 — Phase 3 verification gate

**Files:** None modified this task.

- [x] **Step 1: Full per-phase verification bar**

Run:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: All pass.

- [x] **Step 2: Manual eyeball of the five anchor surfaces**

Visual spot-check — since Task 3.3's diff check confirmed zero numerical change, there should be no visual drift. But verify the five anchor surfaces render as expected as a sanity check.

- [x] **Step 3: Pause and ask for commit permission**

Summarize: number of alias tokens flattened, number of orphaned vars deleted, `diff` output (should be empty). Ask the user: *"Phase 3 complete and verified. OK to commit?"*

- [x] **Step 4: Commit (after approval)**

```bash
git add src/frontend/src/style/index.css
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 3 — flatten @theme indirection

Collapses alias-of-alias chains in the @theme block so every --color-*
token points at a literal value (or a single hsl(...) pair). No computed
value changes; no JSX call-site changes. Orphaned CSS variables whose
only purpose was feeding an alias are removed.

Phase 3 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Phase 4 — `applies.css` trim

**Purpose:** Reduce `src/frontend/src/style/applies.css` by inlining every `@apply` rule with <3 references. Rules with ≥3 references stay.

**Expected diff shape:** Largest diff of any phase. Touches many files across `src/frontend/src`. The `applies.css` file itself roughly halves in size.

### Task 4.1 — Build the `applies.css` usage map

**Files:**
- Read-only.

- [x] **Step 1: Extract every class defined in `applies.css`**

Run (from repo root):
```bash
grep -E "^\.[a-zA-Z]" src/frontend/src/style/applies.css | \
  sed -E 's/^\.([a-zA-Z0-9_-]+).*/\1/' | sort -u > /tmp/tailwind-max-baseline/applies-css-classes.txt
wc -l /tmp/tailwind-max-baseline/applies-css-classes.txt
```
Expected: ~200–349 class names (depending on how many classes share a rule block).

- [x] **Step 2: Count references for each class**

Run:
```bash
cd src/frontend
while read -r cls; do
  count=$(grep -rn "\b${cls}\b" src --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null | grep -v "src/style/applies.css" | wc -l | tr -d ' ')
  echo "${count} ${cls}"
done < /tmp/tailwind-max-baseline/applies-css-classes.txt | sort -n > /tmp/tailwind-max-baseline/applies-css-usage.txt
cd ../..
```
Expected: per-class usage count. Rules with count `0` are dead. Count `1` or `2` are inline candidates. Count `≥3` stays.

- [x] **Step 3: Bucket the classes**

Split `/tmp/tailwind-max-baseline/applies-css-usage.txt` into three files:
```bash
awk '$1 == 0 {print $2}' /tmp/tailwind-max-baseline/applies-css-usage.txt > /tmp/tailwind-max-baseline/applies-dead.txt
awk '$1 >= 1 && $1 < 3 {print $2}' /tmp/tailwind-max-baseline/applies-css-usage.txt > /tmp/tailwind-max-baseline/applies-inline.txt
awk '$1 >= 3 {print $2}' /tmp/tailwind-max-baseline/applies-css-usage.txt > /tmp/tailwind-max-baseline/applies-keep.txt
wc -l /tmp/tailwind-max-baseline/applies-dead.txt /tmp/tailwind-max-baseline/applies-inline.txt /tmp/tailwind-max-baseline/applies-keep.txt
```
Expected: three files. The "inline" bucket drives Task 4.3. The "keep" bucket is untouched.

### Task 4.2 — Delete dead `applies.css` rules

**Files:**
- Modify: `src/frontend/src/style/applies.css`

- [x] **Step 1: For each class in `applies-dead.txt`, remove its rule from `applies.css`**

A "rule" means: the selector line + the full `{ ... }` block. Be careful with rules that define multiple selectors (`.foo, .bar { @apply ... }`) — if only `.foo` is dead, remove only `.foo` from the selector list; don't delete the whole rule.

- [x] **Step 2: Build and typecheck still pass**

Run: `cd src/frontend && npm run type-check && npm run build`
Expected: Both pass. No JSX changes were made in this task; anything breaking indicates a grep miss in Task 4.1 (the class is used but wasn't detected).

### Task 4.3 — Inline low-use `applies.css` rules

**Files:**
- Modify: `src/frontend/src/style/applies.css` (remove inlined rules)
- Modify: each call-site file listed in the per-class grep

For each class in `/tmp/tailwind-max-baseline/applies-inline.txt`:

- [x] **Step 1: Capture the class's `@apply` utilities**

Look up the class definition in `applies.css`. Copy the exact list of Tailwind utilities from the `@apply` directive.

Example — if `applies.css` has:
```css
.primary-input {
  @apply rounded-md border border-input bg-background px-3 py-2 text-sm;
}
```
Capture: `rounded-md border border-input bg-background px-3 py-2 text-sm`.

- [x] **Step 2: Find the call sites**

Run (from repo root):
```bash
grep -rn "primary-input" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css" | grep -v "src/style/applies.css"
```

- [x] **Step 3: Inline at each call site**

At each call site, replace the custom class name with the Tailwind utilities.

Before:
```tsx
<input className="primary-input h-8" />
```
After:
```tsx
<input className="rounded-md border border-input bg-background px-3 py-2 text-sm h-8" />
```

If the call site uses template literals or `cn(...)` / `clsx(...)`, inline inside the existing composition — don't restructure.

If the Tailwind string becomes very long (>12 classes), consider using the `cn()` helper that's already in the codebase to keep it readable, but don't introduce any new abstraction — we're trying to remove them.

- [x] **Step 4: Remove the rule from `applies.css`**

Delete the class's full rule block from `applies.css`.

- [x] **Step 5: After each class, run typecheck**

Run: `cd src/frontend && npm run type-check`
Expected: Pass. Do one class at a time and typecheck between to isolate any mistake.

**Progress discipline:** This task is repetitive. After every 20 classes processed, take a snapshot:
- Save progress: `cp src/frontend/src/style/applies.css /tmp/tailwind-max-baseline/applies-css-snapshot-$(date +%H%M).css`
- Run: `cd src/frontend && npm run test -- --silent`
- If jest fails unexpectedly, compare to the most recent snapshot to find the regression.

### Task 4.4 — Confirm the "keep" bucket is intact and earns its ≥3-use status

**Files:**
- Read-only.

- [x] **Step 1: Re-run the usage map against the reduced `applies.css`**

Run the Task 4.1 Step 2 script again. Every remaining class should have count ≥3.

- [x] **Step 2: Confirm `applies.css` shrank**

Run: `wc -l src/frontend/src/style/applies.css`
Expected: roughly half the baseline recorded in `/tmp/tailwind-max-baseline/css-line-counts.txt`. If it's less than 40% reduction, re-check the "inline" bucket — some rules may have been skipped. If it's more than 70% reduction, the "keep" threshold may be wrong — double-check that remaining rules really do have ≥3 references.

### Task 4.5 — Phase 4 verification gate

**Files:** None modified this task.

- [x] **Step 1: Full per-phase verification bar**

Run:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: All pass.

- [x] **Step 2: Manual eyeball of the five anchor surfaces + broader sampling**

Given this phase's diff is large, spot-check more broadly than the five anchors:
1. Flow canvas
2. Playground
3. Settings → general
4. Settings → API keys
5. Admin → Users
6. Admin → Organizations
7. Component details sidebar
8. Any `core/` component that appeared most often in the inline grep output (sample 2–3)

Watch for alignment shifts, missing borders, color drift. If anything looks off, identify which call site regressed and fix the inline utility list.

- [x] **Step 3: Pause and ask for commit permission**

Summarize: how many rules deleted, how many inlined, how many kept, line-count reduction in `applies.css`, any surfaces with notable drift. Ask the user: *"Phase 4 complete and verified. OK to commit?"*

- [x] **Step 4: Commit (after approval)**

Stage explicitly:
```bash
git add src/frontend/src/style/applies.css
# plus every .tsx / .ts / .css file modified by Tasks 4.2 and 4.3
```

Do NOT `git add -A`. This phase touches many files; list them deliberately or use `git add src/frontend/src/` only if you're confident no unrelated WIP lives under that tree (check `git status` first).

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 4 — trim applies.css

Inlines @apply rules with <3 references directly into their call-site
className strings; deletes dead rules; keeps rules with ≥3 references
as shared utilities. applies.css roughly halves.

Phase 4 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Phase 5 — `accordionComponent` inline

**Purpose:** Remove the `src/frontend/src/components/core/accordionComponent/` wrapper by inlining its callers into direct `ui/accordion` use.

**Expected diff shape:** Dozens of call-site edits; one directory deletion.

### Task 5.1 — Understand the wrapper's API

**Files:**
- Read-only: `src/frontend/src/components/core/accordionComponent/**`

- [x] **Step 1: Read the wrapper's public API**

Read every file in `src/frontend/src/components/core/accordionComponent/` (likely `index.tsx` plus possibly a types file). Record:
- The exported component name(s) and props signature.
- Any default state management (e.g., default-open behavior).
- Any custom trigger/content styling applied.

Save as `/tmp/tailwind-max-baseline/accordion-wrapper-api.txt`.

- [x] **Step 2: Read the underlying `ui/accordion` API**

Read `src/frontend/src/components/ui/accordion.tsx`. Record its exported pieces: `Accordion`, `AccordionItem`, `AccordionTrigger`, `AccordionContent`, and their props.

This tells you what the direct-use API looks like; Task 5.3 bridges the wrapper's API to it at each call site.

### Task 5.2 — Enumerate call sites

**Files:**
- Read-only.

- [x] **Step 1: Grep for every importer**

Run (from repo root):
```bash
grep -rn "from [\"']@/components/core/accordionComponent" src/frontend/src --include="*.ts" --include="*.tsx" > /tmp/tailwind-max-baseline/accordion-call-sites.txt
grep -rn "from [\"'].*accordionComponent" src/frontend/src --include="*.ts" --include="*.tsx" >> /tmp/tailwind-max-baseline/accordion-call-sites.txt
sort -u /tmp/tailwind-max-baseline/accordion-call-sites.txt -o /tmp/tailwind-max-baseline/accordion-call-sites.txt
cat /tmp/tailwind-max-baseline/accordion-call-sites.txt
```
Expected: a list of files.

### Task 5.3 — Migrate each call site to direct `ui/accordion`

**Files:**
- Modify: every file in `accordion-call-sites.txt`.

For each call site:

- [x] **Step 1: Read the call site**

Identify how the wrapper is used: what props are passed, what children are supplied, what visual behavior the wrapper provides that the raw `ui/accordion` doesn't.

- [x] **Step 2: Rewrite with `ui/accordion` primitives**

Replace the wrapper's JSX with direct use of `Accordion`, `AccordionItem`, `AccordionTrigger`, `AccordionContent`. Apply any props/defaults the wrapper provided inline — don't introduce a new wrapper. If the wrapper's default behavior matters (e.g., default-open), express it via `defaultValue` on `Accordion`.

- [x] **Step 3: Update the import**

Replace:
```tsx
import AccordionComponent from "@/components/core/accordionComponent";
```
with:
```tsx
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
```
(Adjust the import path style to match what the file already uses — `@/` alias vs. relative.)

- [x] **Step 4: Typecheck after each file**

Run: `cd src/frontend && npm run type-check`
Expected: Pass. One file at a time.

### Task 5.4 — Delete the wrapper directory

**Files:**
- Delete: `src/frontend/src/components/core/accordionComponent/`

- [x] **Step 1: Confirm zero remaining imports**

Run (from repo root):
```bash
grep -rn "accordionComponent" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: zero results. If any remain, go back to Task 5.3 for that file.

- [x] **Step 2: Delete the directory**

```bash
git rm -r src/frontend/src/components/core/accordionComponent
```

- [x] **Step 3: Typecheck + build**

Run: `cd src/frontend && npm run type-check && npm run build`
Expected: Both pass.

### Task 5.5 — Phase 5 verification gate

- [x] **Step 1: Full per-phase verification bar**

Run:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: All pass.

- [x] **Step 2: Eyeball every accordion surface**

Visit each file from `accordion-call-sites.txt` in the running app. Common accordion surfaces:
- Flow sidebar category groups
- Settings panel sections
- Admin → Organizations detail tabs
- Component details panels

Confirm: accordions expand/collapse, default-expanded sections open as expected, trigger styling matches pre-phase behavior.

- [x] **Step 3: Pause and ask for commit permission**

Summarize: how many call sites migrated, whether wrapper API was fully preserved at each site, whether any surfaces needed extra care. Ask the user: *"Phase 5 complete and verified. OK to commit?"*

- [x] **Step 4: Commit (after approval)**

```bash
git add src/frontend/src/components/core/accordionComponent
# plus every file in accordion-call-sites.txt
```

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 5 — inline accordionComponent

Replaces the src/components/core/accordionComponent wrapper with direct
use of ui/accordion primitives across all call sites. Wrapper directory
removed.

Phase 5 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Phase 6 — Theme token snap-to-Tailwind

**Purpose:** For remaining `--color-*` tokens in `index.css`, snap to stock Tailwind v4 shades when within ~2% and not semantically app-specific. This is the highest-churn phase.

**Expected diff shape:** Large. Changes concentrated in `index.css` + JSX/CSS call sites that use the snapped token names.

### Task 6.1 — Build the token snap map

**Files:**
- Read-only during this task.

- [x] **Step 1: Extract all surviving `--color-*` tokens**

Run (from repo root):
```bash
grep -E "^\s*--color-" src/frontend/src/style/index.css | sed 's/^\s*//' > /tmp/tailwind-max-baseline/color-tokens-post-phase3.txt
wc -l /tmp/tailwind-max-baseline/color-tokens-post-phase3.txt
```

- [x] **Step 2: Apply the "keep list" from the spec**

Mark these as **keep** (do not snap):
- `--adp-red`
- `--color-status-{blue,green,red,yellow,gray}`
- `--color-datatype-*`
- `--color-note-{amber,neutral,rose,blue,lime}`
- `--color-chat-{send,bot-icon,user-icon,trigger,trigger-disabled}`
- `--color-flow-icon`, `--color-component-icon`, `--color-build-trigger`, `--color-connection`, `--color-node-selected`, `--color-node-ring`
- `--color-selected`, `--color-hover`, `--color-ring`, `--color-border`, `--color-input`, `--color-background`, `--color-foreground`, `--color-placeholder*`
- Any other token whose name makes a clear semantic/app-specific role obvious.

Everything else is a **snap candidate**.

Write `/tmp/tailwind-max-baseline/snap-candidates.txt` (one token per line) and `/tmp/tailwind-max-baseline/snap-keeps.txt`.

- [x] **Step 3: For each snap candidate, find the nearest stock Tailwind shade**

Tailwind v4 stock color shades: `slate-{50..950}`, `gray-{50..950}`, `zinc-{50..950}`, `neutral-{50..950}`, `stone-{50..950}`, `red-*`, `orange-*`, `amber-*`, `yellow-*`, `lime-*`, `green-*`, `emerald-*`, `teal-*`, `cyan-*`, `sky-*`, `blue-*`, `indigo-*`, `violet-*`, `purple-*`, `fuchsia-*`, `pink-*`, `rose-*`.

For each candidate, compute ΔE (perceptual distance) or approximate by comparing HSL values. A token is a snap match if the nearest stock shade is within **~2%** of each HSL channel (lightness being the most visually sensitive).

If unsure, use `convert <hex-from-token> -format '%[fx:r*255],%[fx:g*255],%[fx:b*255]' info:` (ImageMagick) or any color-distance tool, and compare to the Tailwind v4 palette hex values (check `node_modules/tailwindcss/lib/...` if needed, or reference `https://tailwindcss.com/docs/colors` in a browser).

Build `/tmp/tailwind-max-baseline/snap-map.txt` with one line per snap candidate:
```
<current-token-name>   <tailwind-shade>    <delta-notes>
--color-medium-gray    zinc-500            close (~1.2% L)
--color-dark-gray      zinc-700            close (~0.8% L)
--color-frosted-glass  (skip — has alpha)  keep custom
```

Tokens that don't snap cleanly (alpha channels, non-standard hues, >2% delta) stay as keeps; append them to `/tmp/tailwind-max-baseline/snap-keeps.txt`.

- [x] **Step 4: Review the snap map before acting**

Before proceeding, have the human review `/tmp/tailwind-max-baseline/snap-map.txt`. This is the last checkpoint before call-site churn. Pause and ask: *"Phase 6 snap map ready — N tokens will be deleted and their call sites migrated to stock Tailwind. See /tmp/tailwind-max-baseline/snap-map.txt. OK to proceed?"*

### Task 6.2 — Delete snapped tokens and migrate call sites

**Files:**
- Modify: `src/frontend/src/style/index.css` (delete snapped token definitions)
- Modify: every JSX/CSS file that uses a snapped token's utility name.

For each entry in `/tmp/tailwind-max-baseline/snap-map.txt`:

- [x] **Step 1: Find utility-class usages**

Tailwind generates utilities from `--color-*` tokens. `--color-medium-gray` produces `bg-medium-gray`, `text-medium-gray`, `border-medium-gray`, `ring-medium-gray`, `fill-medium-gray`, `stroke-medium-gray`, plus any other color-consuming utility. Also any direct `var(--color-medium-gray)` usage in CSS.

Run (for a token named `medium-gray` → Tailwind shade `zinc-500`):
```bash
grep -rn "\(bg\|text\|border\|ring\|fill\|stroke\|from\|to\|via\|outline\|divide\|decoration\|accent\|caret\|placeholder\|shadow\)-medium-gray" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css"
grep -rn "var(--color-medium-gray)" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css"
```

- [x] **Step 2: Replace at each call site**

`bg-medium-gray` → `bg-zinc-500`, `text-medium-gray` → `text-zinc-500`, etc. Preserve any modifier prefixes (`hover:`, `dark:`, etc.). Preserve any arbitrary-value suffixes.

For raw `var(--color-medium-gray)` in CSS: replace with the resolved Tailwind v4 value. (Tailwind v4's stock colors are also exposed as `--color-zinc-500` in the Tailwind-provided token namespace — check whether `index.css`'s `@theme` imports bring them in automatically or whether you need to write the literal value.)

- [x] **Step 3: Delete the token from `index.css`**

Remove the `--color-medium-gray: ...;` line from the `@theme` block.

- [x] **Step 4: Typecheck after each token**

Run: `cd src/frontend && npm run type-check`

For tokens with large call-site counts, run every 5 tokens at minimum rather than every token, but do not batch the full snap without intermediate typechecks.

**Progress discipline:** Periodically snapshot `index.css` and affected directories as in Task 4.3.

### Task 6.3 — Verify token count reduction target

**Files:** Read-only.

- [x] **Step 1: Count surviving `--color-*` tokens**

Run (from repo root):
```bash
grep -c "^\s*--color-" src/frontend/src/style/index.css > /tmp/tailwind-max-baseline/color-token-count-after.txt
cat /tmp/tailwind-max-baseline/color-token-count-after.txt
```

- [x] **Step 2: Compute reduction**

Compare against `/tmp/tailwind-max-baseline/color-token-count.txt` (from pre-flight).

Acceptance target: ≥20% fewer tokens. Compute: `(before - after) / before * 100`. If under 20%, revisit the keep list — likely too conservative. If over 40%, double-check that no semantic token was accidentally snapped.

### Task 6.4 — Phase 6 verification gate (enhanced)

Phase 6 adds a 12-screen walkthrough on top of the standard per-phase bar.

- [x] **Step 1: Full per-phase verification bar**

Run:
```bash
cd src/frontend && npm run type-check
cd src/frontend && npm run test -- --silent
cd src/frontend && npm run build
make tests_frontend
```
Expected: All pass.

- [x] **Step 2: 12-screen visual walkthrough**

Start the dev server (`make frontend`) and visit each of the 12 surfaces from the spec. For each, note whether it looks identical to baseline or has drift. If drift is user-perceivable (not just a hex-level pixel shift), identify which snap was responsible and consider rolling it back (add the token to the keep list).

1. Flow canvas (dark mode)
2. Flow canvas (light mode)
3. Node details sidebar
4. Playground chat
5. Playground file upload
6. Settings → general
7. Settings → API keys
8. Admin → Users page
9. Admin → Organizations list
10. Admin → Organization detail
11. Component Assist popover
12. Note nodes

- [x] **Step 3: Pause and ask for commit permission**

Summarize: how many tokens snapped vs kept, percent reduction achieved, whether any tokens were rolled back after visual review, any surfaces with residual drift. Ask the user: *"Phase 6 complete and verified. OK to commit?"*

- [x] **Step 4: Commit (after approval)**

Stage explicitly — this phase touches many files. Check `git status`; stage only the files modified by Tasks 6.2.

```bash
# example — adjust based on git status
git add src/frontend/src/style/index.css
# plus every .tsx / .ts / .css modified by the snap migration
```

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 6 — snap custom color tokens to stock Tailwind

Deletes custom --color-* tokens within ~2% of a stock Tailwind v4 shade and
migrates their utility-class call sites (bg-*, text-*, border-*, etc.) to
the stock Tailwind name. Preserves app-semantic tokens (status colors,
datatype palette, note colors, flow-canvas roles, --adp-red).

Phase 6 of docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md.
EOF
)"
```

---

## Post-plan — Record deferred follow-ons

After Phase 6 commit, record the Phase 7+ follow-ons from the spec in the repo's follow-ups log so they don't get forgotten.

### Task 7.1 — Append follow-ons to `docs/superpowers/followups.md`

**Files:**
- Modify: `docs/superpowers/followups.md`

- [x] **Step 1: Append a section for each deferred follow-on**

Add entries for:
- 7a — Full `framer-motion` removal
- 7b — Inline `shadTooltipComponent` wrapper
- 7c — Inline `genericIconComponent` / `renderIconComponent` wrappers
- 7d — Remaining decorative consolidation (`refreshButton`, `dialog-with-no-close`, `disclosure`)
- 7e — Semantic palette lean-out

Each entry should be a one-paragraph pointer to the spec section it came from, not a re-statement of the work.

Template:
```markdown
### Tailwind-max follow-up 7a — Full framer-motion removal (2026-04-22)

Phase 2 deleted decorative framer-motion consumers. Full removal from
`package.json` was deferred — about 12 consumers remain, some using
gesture/physics features that need thoughtful replacement.
Acceptance criteria and expected churn documented in
`docs/superpowers/specs/2026-04-22-tailwind-maximization-design.md`,
Phase 7a.
```

- [x] **Step 2: Pause and ask for commit permission**

Ask the user: *"Follow-ons recorded. OK to commit this final touch?"*

- [x] **Step 3: Commit (after approval)**

```bash
git add docs/superpowers/followups.md
git commit -m "docs: record tailwind-max phase 7+ follow-ons"
```

---

## Self-review checklist (for the implementing engineer)

Before declaring the entire plan complete, verify:

- [x] Every phase committed with user approval (no unauthorized commits).
- [x] Every phase left the working tree in a shippable state (typecheck, jest, Playwright, production build all green per-phase).
- [x] Bundle size at end of Phase 6 is ≤ bundle size at start of Phase 1 (no accidental bloat).
- [x] `applies.css` line count dropped by ≥40% from baseline.
- [x] `style/index.css` `--color-*` token count dropped by ≥20% from baseline.
- [x] Seven decorative components deleted in Phase 2; `simple-sidebar.tsx` deleted in Phase 1; `accordionComponent/` deleted in Phase 5.
- [x] `classes.css` deleted (or its live selectors relocated and the file deleted).
- [x] At least one unused styling dep removed in Phase 1.
- [x] Phase 7+ follow-ons recorded in `docs/superpowers/followups.md`.
- [x] No `git add -A` or `git commit -a` was ever used.
- [x] No upstream PR was created.
