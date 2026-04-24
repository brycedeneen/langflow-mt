# Frontend npm upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring all 11 outdated npm packages in `src/frontend/` to their latest versions in a single, verified change set, ready for the user to manually test and then commit-and-push as one unit.

**Architecture:** Three sequential phases — (1) `tailwind-merge` 2 → 3 major bump with call-site scan, (2) `npm update` caret-range sweep for nine packages, (3) exact-pin bump for `@biomejs/biome`. Each phase runs `tsc --noEmit`, `npm run lint`, and `npm test` independently so a failure bisects cleanly. No commits are made during execution; the working tree is left staged-or-modified so the user can review the full diff before pushing.

**Tech Stack:** npm, Node ≥20.19, Vite 8, React 19, Tailwind v4, Biome 2, Jest 30, TypeScript 6.

**Branch:** work happens on the currently-checked-out branch (`platform-multi-tenant`, the effective main). No new branch or worktree.

**Source spec:** [`docs/superpowers/specs/2026-04-24-frontend-npm-upgrade-design.md`](../specs/2026-04-24-frontend-npm-upgrade-design.md)

**Verification bar (applies to every phase):**
- `tsc --noEmit --pretty --project tsconfig.json` → exit 0
- `npm run lint` → exit 0
- `npm test` → exit 0

**What this plan does NOT do:**
- Commit anything (user will commit manually once they've manually tested)
- Run Playwright, Storybook, or `npm start`
- Touch `docs/` or `scripts/aws/` package.json files
- Modify the `overrides` block in `src/frontend/package.json`

**Failure protocol:** If any verification step fails, stop immediately, report the failure, and ask before attempting a fix that goes beyond trivial type/import adjustments.

---

## Task 1: Preflight — confirm baseline

**Files:** none modified

- [x] **Step 1: Confirm working directory and baseline**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && pwd && node -v && npm -v
```
Expected: path ends in `src/frontend`, Node ≥ v20.19, npm ≥ 10.

- [x] **Step 2: Capture the current outdated list as a reference**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm outdated
```
Expected: 11 packages listed — `@biomejs/biome`, `@tailwindcss/vite`, `@tanstack/react-query`, `axios`, `dompurify`, `lucide-react`, `react-hook-form`, `react-router-dom`, `tailwind-merge`, `tailwindcss`, `vite`.

If the set doesn't match, stop and report — the baseline has drifted since the spec was written.

- [x] **Step 3: Confirm clean-ish working tree for the frontend**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && git status --porcelain src/frontend/package.json src/frontend/package-lock.json
```
Expected: no output (neither file is modified).

If either file is already dirty, stop and ask — we don't want to mix this upgrade with unrelated in-flight changes.

---

## Task 2: Phase 1 — tailwind-merge 2.6.1 → 3.5.0 (major bump)

**Files:**
- Modify: `src/frontend/package.json` (dependency range)
- Modify: `src/frontend/package-lock.json` (auto)
- Potentially modify: `src/frontend/src/utils/utils.ts` (only if v3 breaks the call)

**Context:** The only call site is `src/frontend/src/utils/utils.ts:38-40`:
```ts
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```
This is the standard shadcn `cn()` helper using the default `twMerge` export with no custom config. v3 keeps this signature; the expected change set is zero code edits. We still scan first in case something has been added since the plan was written.

- [x] **Step 1: Verify call-site scan is still a single file**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && grep -rn --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' -E "twMerge|extendTailwindMerge|from ['\"]tailwind-merge" src/frontend/src
```
Expected output (exact):
```
src/frontend/src/utils/utils.ts:10:import { twMerge } from "tailwind-merge";
src/frontend/src/utils/utils.ts:39:  return twMerge(clsx(inputs));
```

If additional matches appear — especially any `extendTailwindMerge` or `createTailwindMerge` call — stop and inspect them before proceeding. Those APIs changed shape in v3 (top-level `classGroups` / `conflictingClassGroups` moved under `extend` / `override`, validator names renamed).

- [x] **Step 2: Bump the `tailwind-merge` range in `package.json`**

Edit `src/frontend/package.json`. Change:
```json
    "tailwind-merge": "^2.3.0",
```
to:
```json
    "tailwind-merge": "^3.5.0",
```

- [x] **Step 3: Install**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm install
```
Expected: exit 0. `package-lock.json` updates to resolve `tailwind-merge@3.5.0` (or the latest 3.x).

If npm prints `ERESOLVE` peer-dep errors, stop and report — do NOT use `--legacy-peer-deps` or `--force` without asking.

- [x] **Step 4: Type-check**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit --pretty --project tsconfig.json
```
Expected: exit 0, no output.

If tsc fails inside `utils.ts` or a consumer of `cn()`, that means the v3 type signature moved — likely fixable with a narrow type import. Stop and report the error message before touching code.

- [x] **Step 5: Lint**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm run lint
```
Expected: exit 0.

- [x] **Step 6: Jest**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- --ci
```
Expected: exit 0, all test suites pass.

- [x] **Step 7: Record Phase 1 versions**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm ls tailwind-merge --depth=0
```
Expected: single line showing `tailwind-merge@3.5.0` (or newer 3.x). Save this output for the final summary.

**Do NOT commit. Continue to Task 3.**

---

## Task 3: Phase 2 — caret-range sweep (nine packages)

**Files:**
- Modify: `src/frontend/package-lock.json` (auto — `package.json` ranges already accept these)

**Packages this phase bumps:** `@tailwindcss/vite` 4.2.2→4.2.4, `tailwindcss` 4.2.2→4.2.4, `@tanstack/react-query` 5.99.2→5.100.1, `axios` 1.15.1→1.15.2, `dompurify` 3.4.0→3.4.1, `lucide-react` 1.8.0→1.9.0, `react-hook-form` 7.72.1→7.73.1, `react-router-dom` 7.14.1→7.14.2, `vite` 8.0.8→8.0.10.

- [x] **Step 1: Run `npm update` to pull caret-range bumps**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm update
```
Expected: exit 0. Output lists packages moved; `package.json` is untouched, `package-lock.json` updates.

- [x] **Step 2: Confirm the nine packages moved**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm ls --depth=0 @tailwindcss/vite tailwindcss @tanstack/react-query axios dompurify lucide-react react-hook-form react-router-dom vite
```
Expected: each row shows the latest versions listed above (or newer patch).

If any row is still on the pre-bump version, stop — there may be a peer-dep block.

- [x] **Step 3: Type-check**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit --pretty --project tsconfig.json
```
Expected: exit 0.

- [x] **Step 4: Lint**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm run lint
```
Expected: exit 0.

- [x] **Step 5: Jest**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- --ci
```
Expected: exit 0.

**Do NOT commit. Continue to Task 4.**

---

## Task 4: Phase 3 — exact-pin bump (`@biomejs/biome`)

**Files:**
- Modify: `src/frontend/package.json` (dev-dependency version)
- Modify: `src/frontend/package-lock.json` (auto)

**Context:** `@biomejs/biome` is pinned at exact `2.4.12` (no caret) in `devDependencies`, so `npm update` does not move it. It's the linter and formatter, so the verification bar is just lint + jest (no separate tsc run after the others already passed).

- [x] **Step 1: Edit the pin**

Edit `src/frontend/package.json`. In the `devDependencies` block, change:
```json
    "@biomejs/biome": "2.4.12",
```
to:
```json
    "@biomejs/biome": "2.4.13",
```

Keep the exact pin — do NOT add a caret.

- [x] **Step 2: Install**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm install
```
Expected: exit 0.

- [x] **Step 3: Confirm biome bumped**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx @biomejs/biome --version
```
Expected: output includes `2.4.13`.

- [x] **Step 4: Lint (biome is the linter — this is the real test)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm run lint
```
Expected: exit 0.

If 2.4.13 introduced a new lint rule and a file now fails, stop and report. Options will be: (a) fix the code, (b) disable the new rule in `biome.json`, (c) defer the biome bump. Ask before choosing.

- [x] **Step 5: Jest (confirms no regression from biome's internal changes)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- --ci
```
Expected: exit 0.

**Do NOT commit. Continue to Task 5.**

---

## Task 5: Final verification and summary

**Files:** none modified

- [x] **Step 1: Confirm `npm outdated` is clean**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm outdated; echo "exit=$?"
```
Expected: exit=0 and empty output (no packages listed), OR exit=1 with only in-`overrides` entries (`tar`, `tar-fs`, `glob`, `test-exclude`) — which are intentionally pinned and out of scope.

If any of the 11 original packages still shows up, stop and report.

- [x] **Step 2: Show the diff the user is about to review**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && git diff --stat src/frontend/package.json src/frontend/package-lock.json && echo "---" && git diff src/frontend/package.json
```
Expected: stat shows both files modified; `package.json` diff shows the two manual edits (`tailwind-merge` range, `@biomejs/biome` exact) and nothing else.

- [x] **Step 3: Produce the final summary report**

Format:
```
Frontend npm upgrade — summary

Phase 1 (major):
  tailwind-merge  2.6.1 → <resolved>   | tsc ✓  lint ✓  jest ✓

Phase 2 (caret sweep):
  @tailwindcss/vite   4.2.2 → <resolved>
  tailwindcss         4.2.2 → <resolved>
  @tanstack/react-query 5.99.2 → <resolved>
  axios               1.15.1 → <resolved>
  dompurify           3.4.0 → <resolved>
  lucide-react        1.8.0 → <resolved>
  react-hook-form     7.72.1 → <resolved>
  react-router-dom    7.14.1 → <resolved>
  vite                8.0.8 → <resolved>
                                        | tsc ✓  lint ✓  jest ✓

Phase 3 (exact pin):
  @biomejs/biome      2.4.12 → 2.4.13   | lint ✓  jest ✓

Files modified:
  src/frontend/package.json
  src/frontend/package-lock.json
Code edits beyond manifests: <none | describe>

Uncommitted — ready for manual UI testing.
```

- [x] **Step 4: Hand off to user**

Say, verbatim or close to it:

> "All three phases complete, all verification green. Two files modified (`package.json`, `package-lock.json`). Nothing committed. Ready for your manual UI testing — open a browser, run `npm start` from `src/frontend/`, and click through the flows you care about. Let me know when you want to commit, and I'll stage and draft the message for your approval."

Do NOT stage, commit, or push. Per project memory, `git commit` requires explicit user permission.

---

## Self-review notes

Covered against spec:
- Scope: `src/frontend/` only ✓ (Tasks 2-4 all scoped to that directory)
- All 11 packages accounted for ✓ (Phase 1: 1, Phase 2: 9, Phase 3: 1)
- Verification bar (tsc + lint + jest) runs per phase ✓
- No commits during execution ✓ (handoff step explicit)
- `overrides` block untouched ✓ (not referenced anywhere)
- tailwind-merge v3 known-risk areas enumerated ✓ (Task 2 Step 1 context)
- Failure handling: every verify step has an "expected" and a stop-on-failure note ✓
- Rollback is inherent (no commits made — just revert the two files)
