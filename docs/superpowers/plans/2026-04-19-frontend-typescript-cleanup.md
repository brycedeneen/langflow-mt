# Frontend TypeScript Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive `npx tsc --noEmit` production errors from 89 to 0 in `src/frontend/`, then migrate the TypeScript-7.0-deprecated tsconfig options (`target: "es5"`, `baseUrl: "src"`, `ignoreDeprecations: "6.0"`) — executed as 6 error-code-batched commits + 1 tsconfig commit on an isolated worktree.

**Architecture:** Git worktree branched off `platform-multi-tenant`. Six batch commits, one per TypeScript error code (TS2322, TS2345, TS2339, TS2741/TS2739, TS2554, misc tail), plus a final tsconfig-migration commit. Per-batch gates: production tsc delta = 0 new errors, test tsc count ≤ 173 (deferred debt unchanged), `npm test` remains 198/2834 passing, `npm run build` clean. Merge back to `platform-multi-tenant` per-project (not per-batch).

**Tech Stack:** TypeScript 6.0.3, Vite 8, React 19, Jest 30, tsc `--noEmit` as sole correctness gate for types.

**Standing rules (from user memory):**

- **NO git commits without explicit approval.** Every commit step MUST pause and ask.
- **NO upstream push or PR.** All work stays on local `platform-multi-tenant`.

---

## Pre-flight constants

- **Spec:** `docs/superpowers/specs/2026-04-19-frontend-typescript-cleanup-design.md`
- **Worktree:** `.worktrees/ts-cleanup-2026-04/`
- **Branch:** `ts-cleanup/production-2026-04` (branched from `platform-multi-tenant`)
- **Target file for tsconfig migration:** `src/frontend/tsconfig.json`
- **All `npx tsc` / `npm` commands run from:** `.worktrees/ts-cleanup-2026-04/src/frontend/`
- **Production error baseline (must reach 0):** 89
- **Test error baseline (gate ≤ this):** 173
- **Unit test baseline:** 198 suites, 2834 passing
- **Build baseline:** `npm run build` succeeds, pre-existing "chunks > 500 kB" warning expected

### Helpers used throughout

**Produce a normalized production error list** (used as the diff basis for delta gating):

```bash
cd .worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS[0-9]+:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' \
  | sort -u
```

**Count test-file errors** (used for the ≤173 gate):

```bash
npx tsc --noEmit 2>&1 \
  | grep -E "error TS[0-9]+:" \
  | grep -E "__tests__|\.test\.|\.spec\." \
  | wc -l
```

**Approval gate phrasing (use at every commit step):**

> "Batch N diff + verification attached. Production tsc errors removed: X of Y. New errors: 0. Test count: Z (≤173). Tests: 198/2834. Build: clean. Ready to commit? [awaits approval]"

---

## Task 0: Setup worktree and capture baselines

**Files:** no source changes; only worktree creation + baseline log capture

- [ ] **Step 0.1: Verify starting state**

Run from `/Users/brycedeneen/dev/langflow`:

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: on `platform-multi-tenant`, clean or only unrelated WIP files uncommitted. The target branch `ts-cleanup/production-2026-04` must not exist yet.

- [ ] **Step 0.2: Create worktree**

```bash
git worktree add .worktrees/ts-cleanup-2026-04 -b ts-cleanup/production-2026-04
cd .worktrees/ts-cleanup-2026-04
```

Expected: new worktree checked out on new branch.

- [ ] **Step 0.3: Install frontend deps in worktree**

```bash
cd src/frontend
npm install
```

Expected: clean install. Pre-existing audit warnings are unchanged from the main worktree.

- [ ] **Step 0.4: Capture production-error baseline**

```bash
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-baseline.log
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-baseline.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-baseline-prod-errors.txt
wc -l /tmp/ts-cleanup-baseline-prod-errors.txt
```

Expected output: `89`. If the number is not 89, STOP and re-confirm the baseline with the controller — something changed since the spec was written.

- [ ] **Step 0.5: Capture per-code counts** (for batch planning)

```bash
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-baseline.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | grep -oE "TS[0-9]+" | sort | uniq -c | sort -rn \
  > /tmp/ts-cleanup-baseline-prod-by-code.txt
cat /tmp/ts-cleanup-baseline-prod-by-code.txt
```

Expected roughly (from spec survey): `TS2322: ~30`, `TS2345: ~15`, `TS2339: ~15`, `TS2741+TS2739: ~10`, `TS2554: ~8`, misc tail ~11.

- [ ] **Step 0.6: Capture test-error baseline** (for ≤173 gate)

```bash
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-baseline.log \
  | grep -E "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-baseline-test-errors.txt
wc -l /tmp/ts-cleanup-baseline-test-errors.txt
```

Expected: `173`. Ceiling for the test-file gate throughout the project.

- [ ] **Step 0.7: Capture unit-test and build baselines**

```bash
npm test -- --ci 2>&1 | tee /tmp/ts-cleanup-baseline-tests.log
npm run build 2>&1 | tee /tmp/ts-cleanup-baseline-build.log
```

Expected: `198 suites, 2834 tests passed`; build succeeds with existing chunk-size warning.

- [ ] **Step 0.8: Report baseline to controller**

Present a 5-line summary:
- Worktree at `.worktrees/ts-cleanup-2026-04/` on `ts-cleanup/production-2026-04`
- Production errors: 89
- Test errors: 173
- Tests: 198/2834
- Build: clean

Proceed to Task 1.

---

## Task 1 (Batch 1): TS2322 — "not assignable"

**Scope:** approximately 30 production errors with code `TS2322`. Typical sub-patterns:

- `any[] | null` flowing into a parameter that expects `SomeType[] | undefined` — fix by narrowing (`?? undefined`) or by widening the destination type if legitimately nullable.
- Union assignment where source is broader than destination.
- `MetricType`-style type mismatches after library bumps that widened types.

**Files:** variable — only those flagged by tsc for TS2322 in production paths.

- [ ] **Step 1.1: Extract TS2322 production errors**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS2322:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task1-start.txt
wc -l /tmp/ts-cleanup-task1-start.txt
```

Expected: roughly 30. Record the number.

- [ ] **Step 1.2: Group errors by file + sub-pattern**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task1-start.txt \
  | sort | uniq -c | sort -rn
```

Expected: a handful of files dominate (e.g., `use-flow-version-sidebar.ts` had 5 in initial survey). Work one file at a time, smallest-blast-radius first.

- [ ] **Step 1.3: Fix errors iteratively**

For each file:
1. Open the file; read the offending line + 5 lines of context.
2. Identify the error cause: narrowing needed? Source type wrong? Destination type wrong?
3. Apply the minimal fix — prefer typing changes over logic changes.
4. If the fix would require > 10 call sites of ripple (shared hook signature change), STOP, present findings; this is a stop-the-line.
5. Rerun `npx tsc --noEmit` against that file to confirm the error is gone:
   ```bash
   npx tsc --noEmit 2>&1 | grep -E "<filepath>.*error TS2322"
   ```
   Expected: no output (all TS2322 errors in that file resolved) or fewer lines than before.

Escape-hatch rule: `// @ts-expect-error` or `as unknown as X` with a one-line justification comment; budget is **5 total across the batch**.

- [ ] **Step 1.4: Run full gate**

```bash
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task1-post.log

# Gate 1: production tsc — any TS2322 left in production?
grep -E "error TS2322:" /tmp/ts-cleanup-task1-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

# Gate 1b: any new production errors (across all codes) introduced?
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task1-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task1-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task1-current-prod.txt
# Expected: empty (no errors outside the baseline)

# Gate 2: test count unchanged/lower
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task1-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

# Gate 3: unit tests
npm test -- --ci 2>&1 | tee /tmp/ts-cleanup-task1-tests.log | tail -5
# Expected: 198 suites, 2834 passed

# Gate 4: build
npm run build 2>&1 | tee /tmp/ts-cleanup-task1-build.log | tail -5
# Expected: built in ~5s, clean
```

All four gates must pass. If any fails, iterate on fixes before proceeding.

- [ ] **Step 1.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 1 (TS2322) diff + verification attached. Production TS2322 errors removed: N of N (expected ~30). 0 new errors. Test count: M (≤173). Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 1.6: Commit (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git add -u
git commit -m "fix(types): clear TS2322 in production — batch 1

<short summary of sub-patterns addressed: e.g. 'narrow any[] | null
at use-flow-version-sidebar, tighten MetricType imports, widen N
acceptable nullable parameter types'>

Before: ~30 TS2322 production errors. After: 0.

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 2 (Batch 2): TS2345 — "argument not assignable"

**Scope:** approximately 15 production errors with code `TS2345`. These are often downstream of TS2322 (if the target parameter's type was fixed in batch 1, some TS2345 errors may already have gone). Re-snapshot before working.

**Files:** variable — only those flagged for TS2345 in production paths.

- [ ] **Step 2.1: Re-snapshot TS2345 production errors (post-batch-1 state)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS2345:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task2-start.txt
wc -l /tmp/ts-cleanup-task2-start.txt
```

Expected: approximately 15, possibly fewer if batch 1 resolved some cascades.

- [ ] **Step 2.2: Group by file**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task2-start.txt \
  | sort | uniq -c | sort -rn
```

- [ ] **Step 2.3: Fix iteratively**

Same process as Task 1 Step 1.3:
1. Read error + context.
2. Identify cause (wrong arg type, unnecessary union widening, unnarrowed null/undefined).
3. Apply minimal fix.
4. If fix requires > 10 call-site ripple, STOP.
5. Verify per-file with `grep TS2345`.

Escape-hatch budget: 5 total across this batch (separate from Task 1's budget).

- [ ] **Step 2.4: Run full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task2-post.log

# Gate 1a
grep -E "error TS2345:" /tmp/ts-cleanup-task2-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

# Gate 1b (no new production errors outside baseline)
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task2-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task2-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task2-current-prod.txt
# Expected: empty

# Gate 2
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task2-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

# Gate 3
npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

# Gate 4
npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 2.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 2 (TS2345) diff + verification attached. Production TS2345 errors removed: N of N. 0 new errors. Test count: M (≤173). Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 2.6: Commit (only after explicit approval)**

```bash
git add -u
git commit -m "fix(types): clear TS2345 in production — batch 2

<short summary of sub-patterns addressed>

Before: ~15 TS2345 production errors. After: 0.

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 3 (Batch 3): TS2339 — "property does not exist"

**Scope:** approximately 15 production errors with code `TS2339`. Typical sub-patterns:

- Accessing a property the inferred type doesn't include (often a hook return type with missing field).
- Narrowing a union incorrectly (e.g., property exists on one variant).
- Missing type assertion or guard at a boundary.

**Files:** variable.

- [ ] **Step 3.1: Re-snapshot TS2339 production errors**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS2339:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task3-start.txt
wc -l /tmp/ts-cleanup-task3-start.txt
```

- [ ] **Step 3.2: Group by file**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task3-start.txt \
  | sort | uniq -c | sort -rn
```

- [ ] **Step 3.3: Fix iteratively**

Same process as Task 1 Step 1.3. Escape-hatch budget: 5 total.

Common fix patterns for TS2339:
- Add missing property to the declared type at the source (often a hook's return type).
- Add a type guard (`if ('prop' in obj) { ... }`).
- Use optional chaining when the property is genuinely optional and the access is safe.

- [ ] **Step 3.4: Run full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task3-post.log

grep -E "error TS2339:" /tmp/ts-cleanup-task3-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task3-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task3-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task3-current-prod.txt
# Expected: empty

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task3-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 3.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 3 (TS2339) diff + verification attached. N of N errors cleared. 0 new errors. Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 3.6: Commit (only after explicit approval)**

```bash
git add -u
git commit -m "fix(types): clear TS2339 in production — batch 3

<short summary>

Before: ~15 TS2339 production errors. After: 0.

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 4 (Batch 4): TS2741 + TS2739 — "missing properties"

**Scope:** approximately 10 production errors combining `TS2741` and `TS2739`. Typical sub-patterns:

- Caller passes an object literal missing props that were added to the target interface.
- A factory returns a shape that no longer covers all required fields.
- A test fixture extracted into production code is missing fields present at production call sites.

**Files:** variable.

- [ ] **Step 4.1: Re-snapshot production errors for this batch**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS2741:|error TS2739:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task4-start.txt
wc -l /tmp/ts-cleanup-task4-start.txt
```

- [ ] **Step 4.2: Group by file + identify missing-props pattern**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task4-start.txt \
  | sort | uniq -c | sort -rn
```

For each error, the message shape is: `Type '{ a: X }' is missing the following properties from type 'T': b, c, d`. Identify whether:
- The caller should supply the missing props (add them at the call site), OR
- The target type should mark them optional (if they were never required), OR
- The function signature should evolve (stop-the-line if > 10 sites affected).

- [ ] **Step 4.3: Fix iteratively**

Same as Task 1 Step 1.3. Escape-hatch budget: 5 total.

**Common fix pattern for props added to a component but not to its call site stubs:** pass the missing props at the call site with a sensible value (often a default, `() => {}`, or an inferred constant). Do NOT use `as any` for missing-props errors — the fix is visible and auditable.

- [ ] **Step 4.4: Run full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task4-post.log

grep -E "error TS2741:|error TS2739:" /tmp/ts-cleanup-task4-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task4-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task4-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task4-current-prod.txt
# Expected: empty

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task4-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 4.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 4 (TS2741/TS2739) diff + verification attached. N of N errors cleared. 0 new errors. Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 4.6: Commit (only after explicit approval)**

```bash
git add -u
git commit -m "fix(types): clear TS2741/TS2739 in production — batch 4

<short summary, naming the component interfaces updated or the
callers that were missing props>

Before: ~10 TS2741+TS2739 production errors. After: 0.

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 5 (Batch 5): TS2554 — "too many arguments"

**Scope:** approximately 8 production errors with code `TS2554`. Typical sub-patterns:

- Caller passes more args than the function accepts — often a function signature was tightened, but a caller wasn't updated.
- A mock or wrapper calls a function with an old arity.

**Files:** variable.

- [ ] **Step 5.1: Re-snapshot**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS2554:" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task5-start.txt
wc -l /tmp/ts-cleanup-task5-start.txt
```

- [ ] **Step 5.2: Group by file**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task5-start.txt \
  | sort | uniq -c | sort -rn
```

- [ ] **Step 5.3: Fix iteratively**

For each error, determine whether:
- The extra argument was stale and should be removed from the call site.
- The function signature intentionally tightened and the caller's extra arg can be dropped.
- The function should accept the argument (expand signature) — stop-the-line if this affects > 10 call sites.

Escape-hatch budget: 5 total.

- [ ] **Step 5.4: Run full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task5-post.log

grep -E "error TS2554:" /tmp/ts-cleanup-task5-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task5-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task5-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task5-current-prod.txt
# Expected: empty

grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task5-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 5.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 5 (TS2554) diff + verification attached. N of N errors cleared. 0 new errors. Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 5.6: Commit (only after explicit approval)**

```bash
git add -u
git commit -m "fix(types): clear TS2554 in production — batch 5

<short summary of which functions' arity mismatches were resolved>

Before: ~8 TS2554 production errors. After: 0.

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 6 (Batch 6): Misc long-tail codes

**Scope:** approximately 11 production errors across `TS2352`, `TS2353`, `TS2556`, `TS2614`, `TS2722`, `TS2307`, `TS2820`, `TS2430`. Each has one-off fixes:

- **TS2352** — "conversion of type X to Y may be a mistake" — remove/rewrite the offending cast.
- **TS2353** — "object literal may only specify known properties" — drop the unknown property or add it to the type.
- **TS2556** — spread argument of wrong arity — reshape the tuple or relax the signature.
- **TS2614** — "module has no default export" — switch to named import.
- **TS2722** — "cannot invoke possibly undefined" — null-check the callable.
- **TS2307** — "cannot find module" — fix the import path (often relative `..` issues).
- **TS2820** — "did you mean X" — typo in property name.
- **TS2430** — "derived class incompatible with base class" — align the override signature.

**Files:** variable.

- [ ] **Step 6.1: Re-snapshot**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 \
  | grep -E "error TS(2352|2353|2556|2614|2722|2307|2820|2430):" \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task6-start.txt
wc -l /tmp/ts-cleanup-task6-start.txt
```

- [ ] **Step 6.2: Group by code + file**

```bash
awk -F'(' '{print $1}' /tmp/ts-cleanup-task6-start.txt \
  | sort | uniq -c | sort -rn
grep -oE "TS[0-9]+" /tmp/ts-cleanup-task6-start.txt | sort | uniq -c | sort -rn
```

- [ ] **Step 6.3: Fix one error at a time**

Each code has a distinct fix recipe; there are few repeats. Apply the per-code guidance from the scope above. Escape-hatch budget: 5 total.

- [ ] **Step 6.4: Run full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task6-post.log

# Must be zero remaining production errors across the batch codes
grep -E "error TS(2352|2353|2556|2614|2722|2307|2820|2430):" /tmp/ts-cleanup-task6-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

# Must be zero remaining production errors TOTAL
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task6-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0 (this is the milestone — production is now type-clean)

# No new errors outside baseline
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task6-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task6-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task6-current-prod.txt
# Expected: empty

# Test count gate
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task6-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 6.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff -- 'src/frontend/src/**/*.ts' 'src/frontend/src/**/*.tsx'
```

Ask: "Batch 6 (misc long-tail) diff + verification attached. N of N errors cleared. **Production tsc errors now 0.** 0 new errors. Tests: 198/2834. Build: clean. Ready to commit?"

- [ ] **Step 6.6: Commit (only after explicit approval)**

```bash
git add -u
git commit -m "fix(types): clear misc long-tail TS codes in production — batch 6

<short summary listing the codes addressed and any notable
call-site fixes>

Before: ~11 mixed-code production errors across TS2352, TS2353, TS2556,
TS2614, TS2722, TS2307, TS2820, TS2430. After: 0.

**Production tsc is now fully clean across all TS codes.**

No new production errors introduced; test error count unchanged;
npm test 198/2834; npm run build clean."
```

---

## Task 7: tsconfig migration — drop deprecated options

**Scope:** migrate `src/frontend/tsconfig.json` off the three options slated for removal in TypeScript 7.0, now safely silenced by `ignoreDeprecations: "6.0"`. Done after production code is clean so any new errors are isolated to this commit.

**Files:**

- Modify: `src/frontend/tsconfig.json`

- [ ] **Step 7.1: Read current tsconfig**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
cat src/frontend/tsconfig.json
```

Expected current `compilerOptions` block includes:

```
"target": "es5",
"ignoreDeprecations": "6.0",
"rootDir": ".",
...
"paths": {
  "@/*": ["*"],
  "@queries/*": ["controllers/API/queries/*"]
},
"baseUrl": "src"
```

- [ ] **Step 7.2: Apply migration**

Edit `src/frontend/tsconfig.json` to make the following changes in-place:

- Replace `"target": "es5"` with `"target": "es2020"`
- Delete the line `"ignoreDeprecations": "6.0",`
- Delete the line `"baseUrl": "src"`
- Change `"@/*": ["*"]` to `"@/*": ["./src/*"]`
- Change `"@queries/*": ["controllers/API/queries/*"]` to `"@queries/*": ["./src/controllers/API/queries/*"]`
- Keep `"rootDir": "."`, `"strict": true`, `"noImplicitAny": false` — all unchanged.

Result should look like:

```jsonc
{
  "compilerOptions": {
    "target": "es2020",
    "rootDir": ".",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noFallthroughCasesInSwitch": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "types": ["@storybook/react"],
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "noImplicitAny": false,
    "paths": {
      "@/*": ["./src/*"],
      "@queries/*": ["./src/controllers/API/queries/*"]
    }
  },
  "include": [
    "src",
    ...
  ]
}
```

- [ ] **Step 7.3: Run gates**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend

# Gate 1: no new production errors (any code)
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-task7-post.log
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task7-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0

# Gate 1b: baseline diff (expected empty after Task 6)
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task7-post.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-task7-current-prod.txt
comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-task7-current-prod.txt
# Expected: empty

# Gate 2: test errors
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-task7-post.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173

# Gate 3: unit tests
npm test -- --ci 2>&1 | tail -5
# Expected: 198/2834

# Gate 4: build
npm run build 2>&1 | tail -5
# Expected: clean
```

If `target: es2020` surfaces any new error (unlikely — `lib: ["...","esnext"]` already provides modern types), fix inline. Do not revert the migration unless the fix exceeds 5 files of changes; in that case stop and escalate.

- [ ] **Step 7.4: Smoke the Vite dev server**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
timeout 30 npm start 2>&1 | tee /tmp/ts-cleanup-task7-devserver.log || true
grep -E "(VITE|ready in|Local:)" /tmp/ts-cleanup-task7-devserver.log | head -5
```

Expected: Vite startup header, a `Local: http://localhost:3000/` line within ~5s. The 30-second `timeout` then kills the server. If no `ready` / `Local:` line appears, the server failed to start — investigate.

- [ ] **Step 7.5: Show diff and request approval**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git diff --stat
git diff src/frontend/tsconfig.json
```

Ask: "tsconfig migration diff attached. 0 new tsc errors. Tests: 198/2834. Build: clean. Dev server boots. Ready to commit?"

- [ ] **Step 7.6: Commit (only after explicit approval)**

```bash
git add src/frontend/tsconfig.json
git commit -m "build(tsconfig): drop deprecated target=es5 / baseUrl; prepare for TS 7.0

- target \"es5\" -> \"es2020\" (lib already carried esnext, so modern
  stdlib types were already available; this is a cleanup)
- baseUrl removed; paths now use \"./src/*\" and
  \"./src/controllers/API/queries/*\" directly
- ignoreDeprecations \"6.0\" removed (no longer needed)
- rootDir, strict, noImplicitAny all unchanged

Verification: tsc error set byte-identical (0 production errors,
test count unchanged); npm test 198/2834; npm run build clean;
vite dev server starts."
```

---

## Task 8: Final validation + merge back

**Files:** no source changes; process step.

- [ ] **Step 8.1: Full combined re-run**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-final-tsc.log
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-final-tsc.log \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
# Expected: 0 (production clean)
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-final-tsc.log \
  | grep -E "__tests__|\.test\.|\.spec\." | wc -l
# Expected: <= 173 (test count unchanged)

npm test -- --ci 2>&1 | tail -5
# Expected: 198 suites, 2834 tests

npm run build 2>&1 | tail -5
# Expected: clean
```

- [ ] **Step 8.2: Commit log check**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/ts-cleanup-2026-04
git log --oneline platform-multi-tenant..HEAD
```

Expected: 7 commits (6 fix commits + 1 tsconfig commit). No stray commits.

- [ ] **Step 8.3: Present final summary, request merge approval**

Show the user:
- Production tsc: **89 → 0**
- Test tsc: **173 → ≤173** (unchanged or improved)
- Tests: 198/2834 pass (matches baseline)
- Build: clean
- tsconfig migrated: `target`, `baseUrl`, `ignoreDeprecations` all cleaned
- 7 commits ready

Ask: "TypeScript cleanup complete and validated. Ready to merge `ts-cleanup/production-2026-04` into `platform-multi-tenant`?"

- [ ] **Step 8.4: Merge back (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git checkout platform-multi-tenant
git merge --no-ff ts-cleanup/production-2026-04 -m "merge: frontend TypeScript cleanup — production

7 commits from ts-cleanup/production-2026-04:
  <paste the 7 SHAs + titles from git log>

Production tsc 89 -> 0; tsconfig migrated off target=es5, baseUrl,
ignoreDeprecations. Test and build baselines unchanged."
```

- [ ] **Step 8.5: Clean up worktree**

```bash
git worktree remove .worktrees/ts-cleanup-2026-04
git branch -d ts-cleanup/production-2026-04
```

(If `-d` refuses, the branch was not fully merged — investigate before using `-D`.)

- [ ] **Step 8.6: Handoff — queue the next follow-ups**

Remind the user of the two deferred successor projects per the spec:

1. **Frontend test TypeScript cleanup** — 173 test errors, next in queue.
2. **Frontend `noImplicitAny: true` flip** — 616 new production errors, its own multi-week project.

Plus the dep-upgrade spec follow-ups still pending: bcrypt/passlib replacement, docling ecosystem bump, LangChain 1.x, Pandas 3, Tailwind 4.

---

## Self-review notes

**Spec coverage:** every in-scope item in the spec maps to a task. Batches 1–6 cover the 89 production errors grouped by code. Task 7 covers all three tsconfig migrations. Deferred work (tests, `noImplicitAny`) remains untouched as specified.

**Approval gates:** every `git commit` step includes an explicit pause, per the user's standing "no commits without permission" rule.

**Merge strategy:** per-project, not per-batch, matching the spec and the dep-upgrade precedent.

**Stop-the-line rules:** each batch carries the > 10 call-site ripple, > 5 escape hatches, and > 1.5× growth triggers explicitly in Step N.3.

**No placeholders:** target version numbers, file glob patterns, expected error counts, and exact commands are all concrete. The `<short summary>` tokens in commit messages are intentional parameterization — specifics depend on what the engineer finds during each batch.
