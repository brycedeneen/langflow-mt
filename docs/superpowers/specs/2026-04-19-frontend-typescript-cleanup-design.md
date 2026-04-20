# Frontend TypeScript cleanup — production code

## Problem

After the Phase 2 dep-upgrade project (TypeScript 5 → 6), `tsc --noEmit` reports **262 pre-existing type errors across 90 files** in `src/frontend/`. Most (173) live in test files; **89 are in production code** — real type gaps that accumulated while the codebase ran with a half-strict tsconfig (`strict: true` but `noImplicitAny: false`).

The errors fall into recognizable patterns: `any[] | null` flowing into code that expects a narrow array type, test and caller stubs that weren't updated after component prop additions, property-access chains through incompletely-typed hooks. They are fixable with minimal typing changes, not refactors.

Additionally, tsconfig carries two options (`target: "es5"`, `baseUrl: "src"`) deprecated for removal in TypeScript 7.0, currently silenced via `ignoreDeprecations: "6.0"` added during the dep-upgrade project. Dropping those dependencies now avoids a future forced migration.

## Decision

Fix the 89 production type errors, then migrate away from the deprecated tsconfig options. Execute as a sequence of 7 commits on an isolated worktree, grouped by TS error code for pattern-driven efficiency.

**Tiering rule:**

- Production type errors → fix in this project, batched by error code.
- Tsconfig deprecated options → migrate in a final commit after the code is clean.
- **Test-file type errors (173)** → explicitly deferred to a standalone follow-up project.
- **`noImplicitAny: true` flip** → explicitly deferred (would surface 616+ new production errors; its own multi-week project).
- **Refactors surfaced during batch work** → note and file as follow-ups; do not expand batch scope.

## Scope

### In scope

**Production TS error batches** (commit per batch, 6 commits):

| Batch | TS code(s) | Production count | Pattern |
|---|---|---|---|
| 1 | TS2322 | ~30 | "not assignable" — missing narrowing, `any[] \| null` flow |
| 2 | TS2345 | ~15 | "argument not assignable" — often downstream of batch 1 |
| 3 | TS2339 | ~15 | "property doesn't exist" — incomplete hook return types |
| 4 | TS2741 + TS2739 | ~10 | "missing properties" — caller stubs vs. component interface |
| 5 | TS2554 | ~8 | "too many args" — signature drift |
| 6 | TS2352, TS2353, TS2556, TS2614, TS2722, TS2307, TS2820, TS2430 | ~11 | Misc long-tail |

(Exact per-code counts captured in Task 0 baseline; listed here from initial survey of `/tmp/ts-cleanup-errors.log`.)

**Tsconfig migration** (commit 7):

- `target: "es5"` → `target: "es2020"` (`lib` already carries `esnext`, so modern types already available — this is mostly a cleanup)
- Remove `baseUrl: "src"`; update `paths` from `"@/*": ["*"]` to `"@/*": ["./src/*"]` (and similarly for `@queries/*`)
- Remove `ignoreDeprecations: "6.0"` (no longer needed once `target` and `baseUrl` are migrated)
- `rootDir: "."` stays (added during Phase 2c dep-upgrade; still required)

### Out of scope

- **All 173 test-file errors** — deferred to a separate "Frontend test TypeScript cleanup" follow-up project. Fixing production types may incidentally surface more test errors (mock shape mismatches); the test error count is gated (must stay ≤ 173) but not driven down.
- **Flipping `noImplicitAny: true`** — deferred to its own project. Measured to surface 616 additional production errors (298 × TS7006, 206 × TS7031, 159 × TS7053, 10 × TS7008). Multi-week scope.
- **Any code refactor beyond a minimal typing fix** — if a batch reveals a shared hook needs a signature change affecting 30 callers, or a component interface needs reshaping, pause the batch and file a standalone follow-up spec rather than expanding scope.
- **Backend TypeScript** — none exists; langflow backend is Python.
- **The `strict: true` and other existing strict flags** — already on; not changing.

## Implementation

### Branching

- Git worktree at `.worktrees/ts-cleanup-2026-04/` on branch `ts-cleanup/production-2026-04`, branched from `platform-multi-tenant`.
- 7 commits land on that branch.
- Merge back to `platform-multi-tenant` via `--no-ff` at project end (not per batch).
- No upstream push.
- No commit without explicit user approval per batch (standing rule).

### Baseline capture (Task 0)

Run inside the worktree, save outputs:

```bash
cd src/frontend

# Production TS error baseline
npx tsc --noEmit 2>&1 | tee /tmp/ts-cleanup-baseline.log
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-baseline.log \
  | grep -vE "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-baseline-prod-errors.txt
wc -l /tmp/ts-cleanup-baseline-prod-errors.txt    # target: 89

# Test TS error count baseline (for gate: must stay ≤ this number)
grep -E "error TS[0-9]+:" /tmp/ts-cleanup-baseline.log \
  | grep -E "__tests__|\.test\.|\.spec\." \
  | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
  > /tmp/ts-cleanup-baseline-test-errors.txt
wc -l /tmp/ts-cleanup-baseline-test-errors.txt    # target: 173

# Test suite baseline
npm test -- --ci 2>&1 | tee /tmp/ts-cleanup-baseline-tests.log
# Build baseline
npm run build 2>&1 | tee /tmp/ts-cleanup-baseline-build.log
```

### Per-batch workflow

Repeated for each of batches 1–6:

1. Filter current `tsc` output to production files for the batch's TS code(s).
2. Group the remaining errors by **sub-pattern** within the code. Fix each pattern at all sites before moving to the next sub-pattern.
3. Fix minimally: add annotations, narrow with type guards, tighten a hook return type. **No refactors.**
4. Prefer real typing over `as any` / `// @ts-ignore`. Each escape hatch requires a one-line justification comment. If a batch accumulates > 5 escape hatches, pause and re-plan.
5. Re-run the gates (below). All four must pass.
6. Present diff + gate outputs for approval. On approval, commit with message:
   ```
   fix(types): clear TS<code> in production — batch <N>

   <short summary of sub-patterns addressed>
   Before: <N> production errors. After: 0.
   ```

### Tsconfig migration commit (commit 7)

1. Edit `tsconfig.json`:
   ```diff
   -    "target": "es5",
   -    "ignoreDeprecations": "6.0",
   +    "target": "es2020",
        "rootDir": ".",
        ...
   -    "baseUrl": "src"
        "paths": {
   -      "@/*": ["*"],
   -      "@queries/*": ["controllers/API/queries/*"]
   +      "@/*": ["./src/*"],
   +      "@queries/*": ["./src/controllers/API/queries/*"]
        }
   ```
2. Re-run all four gates. Commit if clean.
3. Commit message:
   ```
   build(tsconfig): drop deprecated target=es5 / baseUrl; prepare for TS 7.0

   - target "es5" -> "es2020" (lib already carried esnext)
   - baseUrl removed; paths updated to use ./src/* directly
   - ignoreDeprecations removed (no longer needed)
   ```

### Verification gates (all four per commit)

1. **Production tsc delta** = 0 — the set of production errors after the commit is a subset of the batch-start set and excludes nothing outside that set.
   ```bash
   npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" \
     | grep -vE "__tests__|\.test\.|\.spec\." \
     | sed 's/\x1b\[[0-9;]*m//g' | sort -u \
     > /tmp/ts-cleanup-current-prod.txt
   # New errors (present now, not in baseline):
   comm -13 /tmp/ts-cleanup-baseline-prod-errors.txt /tmp/ts-cleanup-current-prod.txt
   # Target count after each batch: baseline minus batch's TS code population.
   ```
2. **Test tsc count** ≤ 173 — production fixes may surface test errors; gate prevents silent growth.
   ```bash
   grep -E "error TS[0-9]+:" <tsc-output> \
     | grep -E "__tests__|\.test\.|\.spec\." \
     | wc -l
   ```
3. **Unit tests:** 2834 / 2834 passing (`npm test -- --ci`).
4. **Build:** `npm run build` exits 0 with no new warnings relative to `/tmp/ts-cleanup-baseline-build.log`.

**Stop-the-line triggers:**

- A batch's error set grows rather than shrinks after a fix attempt (indicates a cascading pattern).
- A batch exceeds 1.5× its initial error count during work (fixing one error spawned more).
- Fixing requires a shared refactor affecting > 10 call sites (exit the batch; file a follow-up).
- `> 5` escape hatches (`as any` / `// @ts-ignore`) accumulated in a batch.
- Test tsc count grows past 173.

In any stop-the-line, present findings and either split the sub-phase into its own follow-up spec or step back the affected fix.

## Risks

- **Risk 1 — `target` change surfaces new errors.** Moving `target` from es5 to es2020 shifts which stdlib types TS assumes. Because `lib` already carries `esnext`, expected impact is minimal, but possible. **Mitigation:** tsconfig commit is last. Any new errors appear in isolation, diagnosable against commit 7's scope only.
- **Risk 2 — `baseUrl` removal breaks imports.** Survey showed zero non-`@/` baseUrl-relative imports (`grep` across `src/` returned 0). Risk low. **Mitigation:** verified up front.
- **Risk 3 — Test error count rises.** Tightening a production type may surface test-file type errors through mocks. **Mitigation:** per-commit gate enforces `test errors ≤ 173`. If exceeded, fix the specific test file in the same commit (small), or pause to reassess.
- **Risk 4 — Batch 1 (TS2322) is larger than expected** if the `any[] | null` pattern recurs systemically through a shared hook. **Mitigation:** stop-the-line rule triggers at 1.5× growth or >10-site refactor requirement. Refactor gets its own spec.
- **Risk 5 — Mock-shape fixes bleed into test-file scope.** TS2741/TS2739 fixes often imply updating mocks. Since tests are out of scope, we accept the new test errors (gated, but counted). **Mitigation:** test-file cleanup is explicit follow-up; any fixes made here to test mocks happen only if the fix lives in a shared test fixture visible from the production code commit.

## Rollback

- Per-batch commits are small and self-contained. `git revert <sha>` is the primary rollback.
- If a batch's merge to `platform-multi-tenant` surfaces downstream issues, revert the project merge commit.
- Worktree can be discarded without affecting `platform-multi-tenant` until project merge.

## Follow-ups

Documented here so future sessions can pick them up in priority order.

| Follow-up | Priority | Planned spec path |
|---|---|---|
| Frontend test TypeScript cleanup | After this project validates. 173 test errors across ~30 files, dominated by caller-stub drift. Mechanical once production types stabilize. | `docs/superpowers/specs/YYYY-MM-DD-frontend-test-typescript-cleanup-design.md` |
| Frontend `noImplicitAny: true` flip | After test cleanup. 616 new production errors (TS7006 / TS7031 / TS7053 / TS7008). Decompose by module. | `docs/superpowers/specs/YYYY-MM-DD-frontend-no-implicit-any-design.md` |
| Thread `Variables` / `Data` generics through `useMutationFunctionType` / `useQueryFunctionType` | Discovered during Batch 3. `src/frontend/src/types/api/index.ts` currently drops the mutation `Variables` and query `Data` generics at the options boundary, so `onSuccess` / `onSettled` / `refetchInterval` callbacks see `void` / `unknown` and require localized casts at every consumer. A proper fix threading the generics through surfaces ~70 new errors across 65 call sites — its own refactor project. Currently papered over with tactical `as T | undefined` casts in 6 hooks. | `docs/superpowers/specs/YYYY-MM-DD-react-query-hook-generics-design.md` |
| Remove remaining `ignoreDeprecations: "6.0"` from tsconfig | Discovered during Task 7. `ts-jest` internally uses `moduleResolution: "node10"` when compiling test files, which TS 6 flags as deprecated. Without the silencer, every test suite fails to compile. `target`/`baseUrl` were successfully migrated; this single remaining silencer is gated on `ts-jest` upstream exposing a config knob or switching default. TS 7.0 will force our hand. | `docs/superpowers/specs/YYYY-MM-DD-ts-jest-moduleresolution-design.md` |

Any refactor needs surfaced by stop-the-line rules during execution will be listed here.
