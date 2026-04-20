# Dependency Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the three-phase dependency refresh defined in `docs/superpowers/specs/2026-04-19-dependency-updates-design.md` as 13 reviewable sub-phase commits on an isolated worktree, merging each phase back to `platform-multi-tenant` after validation.

**Architecture:** Git worktree branched off `platform-multi-tenant`. Each sub-phase is one commit consisting of version-spec edits + lockfile regeneration + any required code migrations. Verification gates (install → lint → unit tests → build → smoke) run per sub-phase. Merge-back to `platform-multi-tenant` happens per phase (not per sub-phase).

**Tech Stack:** uv (Python), npm (Node), Make (orchestration), pytest (backend tests), Jest + Playwright + tsc (frontend tests).

**Standing rules (from user memory):**
- **NO git commits without explicit approval.** Every `git commit` step in this plan MUST pause and ask before executing.
- **NO upstream push or PR.** All work stays on local `platform-multi-tenant`.

---

## Pre-flight constants

**Dep spec files:**
- `pyproject.toml` (root workspace)
- `src/backend/base/pyproject.toml` (langflow-base)
- `src/lfx/pyproject.toml` (lfx)
- `src/frontend/package.json` (frontend)

**Lockfiles:**
- `uv.lock` (all Python workspaces — single lockfile at repo root)
- `src/frontend/package-lock.json`

**Working directory:** `.worktrees/deps-upgrade-2026-04/` (created in Task 0)

**Verification command cheatsheet (run from worktree root):**

```bash
# Backend
uv sync                          # install
make lint                        # mypy
make unit_tests                  # pytest
make run_clic                    # full clean build + run (smoke via port 7860)

# Frontend
cd src/frontend
npm install                      # install
npm run type-check               # tsc --noEmit + vite
npm test                         # jest
npm run build                    # vite build
```

**Approval gate phrasing (use at every commit step):**

> "Diff + verification results attached. Ready to commit? [awaits approval]"

---

## Task 0: Setup worktree and capture baseline

**Files:**
- Create: `.worktrees/deps-upgrade-2026-04/` (new worktree)

- [ ] **Step 0.1: Confirm current branch is `platform-multi-tenant` and clean**

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: on `platform-multi-tenant`; working tree clean (the pre-existing untracked `docs/superpowers/specs/2026-04-19-adp-sftp-template-design.md` is OK — it pre-exists this work).

- [ ] **Step 0.2: Create worktree**

```bash
git worktree add .worktrees/deps-upgrade-2026-04 -b deps/upgrade-2026-04
cd .worktrees/deps-upgrade-2026-04
```

Expected: new worktree on branch `deps/upgrade-2026-04` branched from `platform-multi-tenant`.

- [ ] **Step 0.3: Capture baseline test status in the worktree**

```bash
uv sync
make unit_tests 2>&1 | tee /tmp/deps-upgrade-baseline-backend.log
cd src/frontend && npm install && npm test 2>&1 | tee /tmp/deps-upgrade-baseline-frontend.log
```

Expected: both suites currently green. If anything is red at baseline, STOP — fix or triage before continuing. A red baseline makes it impossible to attribute breakage during upgrades.

- [ ] **Step 0.4: Record baseline hash**

```bash
git rev-parse HEAD > /tmp/deps-upgrade-baseline.sha
cat /tmp/deps-upgrade-baseline.sha
```

Expected: one SHA recorded. Used for `git diff <baseline>..HEAD` comparisons later.

---

# PHASE 1 — Non-breaking bumps (2 commits)

## Task 1 (Phase 1a): Backend non-breaking bumps — single commit

**Scope:** 77 non-breaking Python packages (17 core + 60 integration).

**Files:**
- Modify: `pyproject.toml`, `src/backend/base/pyproject.toml`, `src/lfx/pyproject.toml`
- Modify: `uv.lock` (regenerated)

**Package list (upgrade to latest available that satisfies current spec's lower bound):**

Core (17): `asyncer`, `fastmcp`, `filelock`, `mcp`, `opentelemetry-api`, `opentelemetry-exporter-otlp`, `opentelemetry-sdk`, `orjson`, `platformdirs`, `pydantic`, `pyjwt`, `pypdf`, `python-multipart`, `sentry-sdk`, `sqlalchemy`, `sqlmodel`, `tomli`.

Integration (60): `ag-ui-protocol`, `astra-assistants`, `astrapy`, `beautifulsoup4`, `boto3`, `chromadb`, `couchbase`, `coverage`, `cuga`, `ddgs`, `docling`, `docling-core`, `duckdb`, `faiss-cpu`, `faker`, `fastapi-pagination`, `fastavro`, `gitpython`, `google-api-python-client`, `greenlet`, `hypothesis`, `ibm-watsonx-ai`, `jaraco-context`, `langchain-sambanova`, `langchain-unstructured`, `langsmith`, `lark`, `litellm`, `locust`, `lxml`, `markdown`, `markupsafe`, `mcp-server-fetch`, `mlx`, `multiprocess`, `mypy`, `nltk`, `numexpr`, `onnxruntime`, `openinference-instrumentation-langchain`, `pymongo`, `pytest-cov`, `qdrant-client`, `requests`, `scrapegraph-py`, `sentence-transformers`, `spider-client`, `sseclient-py`, `supabase`, `torch`, `types-aiofiles`, `types-cachetools`, `types-google-cloud-ndb`, `types-markdown`, `types-python-jose`, `types-pywin32`, `types-pyyaml`, `types-requests`, `vulture`, `weaviate-client`.

- [ ] **Step 1.1: Edit version specs in all three pyproject.toml files**

For each package, bump the lower bound of the spec to the latest compatible version identified by `uv pip list --outdated`. Do NOT change the upper bound syntax (e.g., if spec is `>=X,<Y`, keep `<Y`; if spec is `>=X`, keep unbounded). Preserve extras like `[http2]`.

Example edit in `src/backend/base/pyproject.toml`:

```diff
- "orjson==3.10.15",
+ "orjson>=3.11.8,<4.0.0",
```

(Some packages are currently hard-pinned with `==`. Relax these to `>=X,<(major+1).0.0` for the 17 core non-breaking items; leave integration `==` pins alone if they have known compatibility reasons — the 60 integration items in this sub-phase are all non-`==` already per the spec's classification.)

Reference data: `/tmp/langflow-outdated/report.txt` (produced during spec exploration) lists old→new for each package.

- [ ] **Step 1.2: Regenerate uv lockfile**

```bash
uv lock
```

Expected: `uv.lock` updates. If resolver fails with a conflict, STOP and investigate — a "non-breaking" bump shouldn't produce resolver conflicts. Common culprit: a transitive dep with a tighter constraint than expected.

- [ ] **Step 1.3: Sync venv**

```bash
uv sync
```

Expected: packages install cleanly.

- [ ] **Step 1.4: Run lint gate**

```bash
make lint
```

Expected: PASS. If mypy surfaces new errors, they are likely type-stub bumps (`types-*`) being stricter. Fix them in this commit — they are type-only.

- [ ] **Step 1.5: Run unit tests**

```bash
make unit_tests
```

Expected: PASS. Compare against `/tmp/deps-upgrade-baseline-backend.log` — test counts should match.

- [ ] **Step 1.6: Run build smoke**

```bash
make run_clic
```

(This starts the server on :7860. Let it boot, then Ctrl-C. If `make run_clic` is not practical interactively, substitute: `uv run python -c "import langflow; import lfx; import langflow.main"` to at least confirm imports.)

Expected: boots without exception.

- [ ] **Step 1.7: Present diff + verification results to user**

```bash
git diff --stat
git diff pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml
git diff --stat uv.lock | head -5
```

Show the user:
- `git diff --stat` summary
- Per-pyproject diff
- Lockfile size delta
- Output of last mypy + pytest runs

Ask: "Phase 1a diff + verification attached. Ready to commit?"

- [ ] **Step 1.8: Commit (only after explicit approval)**

```bash
git add pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml uv.lock
git commit -m "chore(deps): bump backend non-breaking — phase 1a

- core (17): asyncer, fastmcp, filelock, mcp, opentelemetry-*, orjson,
  platformdirs, pydantic, pyjwt, pypdf, python-multipart, sentry-sdk,
  sqlalchemy, sqlmodel, tomli
- integration (60): full list in docs/superpowers/plans/2026-04-19-dependency-updates.md

All bumps are semver-compatible with existing upper bounds.
Verification: uv sync + make lint + make unit_tests + make run_clic all pass."
```

---

## Task 2 (Phase 1b): Frontend non-breaking bumps — single commit

**Scope:** 30 non-breaking frontend packages.

**Files:**
- Modify: `src/frontend/package.json`
- Modify: `src/frontend/package-lock.json` (regenerated)

**Package list (bump caret range to latest listed by `npm outdated`):**

`@biomejs/biome` 2.1.1→2.4.12, `@headlessui/react` 2.2.9→2.2.10, `@jest/types` 30.2.0→30.3.0, `@playwright/test` 1.58.2→1.59.1, `@storybook/addon-docs` / `@storybook/addon-links` / `@storybook/react` / `@storybook/react-vite` 10.2.13→10.3.5, `@swc/core` 1.15.17→1.15.30, `@tabler/icons-react` 3.37.1→3.41.1, `@tanstack/react-query` 5.90.21→5.99.2, `@types/lodash` 4.17.5→4.17.24, `@vitejs/plugin-react-swc` 4.2.3→4.3.0, `@xyflow/react` 12.10.1→12.10.2, `autoprefixer` 10.4.27→10.5.0, `axios` 1.13.6→1.15.1, `dompurify` 3.3.1→3.4.0, `fuse.js` 7.1.0→7.3.0, `jest` 30.2.0→30.3.0, `jest-environment-jsdom` 30.2.0→30.3.0, `lodash` 4.17.23→4.18.1, `nanoid` 5.1.6→5.1.9, `playwright` 1.58.2→1.59.1, `postcss` 8.5.6→8.5.10, `react` 19.2.4→19.2.5, `react-dom` 19.2.4→19.2.5, `react-hook-form` 7.71.2→7.72.1, `react-icons` 5.5.0→5.6.0, `storybook` 10.2.13→10.3.5, `ts-jest` 29.4.6→29.4.9.

- [ ] **Step 2.1: Edit `src/frontend/package.json`**

Bump each caret range. For `"@biomejs/biome": "2.1.1"` (no caret — pinned in current file), change to `"2.4.12"` keeping the pinned form, since the file declares it pinned intentionally. All other packages use `^X.Y.Z` ranges — update the `X.Y.Z` to the target.

- [ ] **Step 2.2: Regenerate lockfile**

```bash
cd src/frontend
npm install
```

Expected: `package-lock.json` updates.

- [ ] **Step 2.3: Run type-check gate**

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 2.4: Run unit tests**

```bash
npm test
```

Expected: PASS. Compare against `/tmp/deps-upgrade-baseline-frontend.log`.

- [ ] **Step 2.5: Run production build**

```bash
npm run build
```

Expected: clean build with no warnings beyond pre-existing ones.

- [ ] **Step 2.6: Present diff to user**

```bash
git diff --stat src/frontend/package.json
git diff src/frontend/package.json
```

Ask: "Phase 1b diff + verification attached. Ready to commit?"

- [ ] **Step 2.7: Commit (only after explicit approval)**

```bash
git add src/frontend/package.json src/frontend/package-lock.json
git commit -m "chore(deps): bump frontend non-breaking — phase 1b

30 packages bumped within their caret ranges. No code changes.
Verification: npm install + type-check + test + build all pass."
```

---

## Task 3: Validate Phase 1 end-to-end, then merge back

**Files:** none (process step)

- [ ] **Step 3.1: Full backend test run**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/deps-upgrade-2026-04
make unit_tests
```

Expected: PASS (same count as baseline).

- [ ] **Step 3.2: Full frontend test run**

```bash
cd src/frontend && npm test
```

Expected: PASS.

- [ ] **Step 3.3: Boot both services and smoke the app**

Terminal 1: `make backend`
Terminal 2: `cd src/frontend && npm start`

Manual smoke:
- Load `http://localhost:3000`
- Log in
- Open the flow list; open an existing flow
- Run one flow

Expected: everything works as on baseline.

- [ ] **Step 3.4: Present Phase 1 summary to user and request merge approval**

Show:
- 2 commits added (`git log platform-multi-tenant..HEAD --oneline`)
- Test counts pre/post
- Smoke results

Ask: "Phase 1 complete and validated. Ready to merge `deps/upgrade-2026-04` into `platform-multi-tenant`?"

- [ ] **Step 3.5: Merge back (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow   # switch to main worktree
git checkout platform-multi-tenant
git merge --ff-only deps/upgrade-2026-04 || git merge --no-ff deps/upgrade-2026-04 -m "merge: dependency updates phase 1"
cd .worktrees/deps-upgrade-2026-04   # return to worktree for Phase 2
```

Expected: clean merge. `deps/upgrade-2026-04` continues to exist; Phase 2 commits will land on it next.

---

# PHASE 2 — Frontend breaking bumps (7 sub-phase commits)

**General note for all Phase 2 tasks:** each sub-phase task follows the same pattern: read changelog, edit `package.json`, `npm install`, apply code migrations, run verification gates, present diff, commit on approval. Migration specifics are called out per task.

## Task 4 (Phase 2a): Build toolchain

**Scope:** `vite` 7→8, `esbuild` 0.25→0.28, `@swc/cli` 0.5→0.8, `vite-plugin-svgr` 4→5.

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: `src/frontend/vite.config.ts`, `src/frontend/scripts/*` (anything that invokes swc CLI)

- [ ] **Step 4.1: Read changelogs**
  - Vite 7→8: https://vite.dev/guide/migration
  - esbuild: https://github.com/evanw/esbuild/blob/main/CHANGELOG.md
  - @swc/cli 0.5→0.8: https://github.com/swc-project/swc/releases
  - vite-plugin-svgr 4→5: https://github.com/pd4d10/vite-plugin-svgr/releases

  Note any breaking changes affecting config or plugin APIs.

- [ ] **Step 4.2: Edit `src/frontend/package.json`**

```diff
-    "vite": "^7.3.1"
+    "vite": "^8.0.8"
```

Same pattern for `esbuild`, `@swc/cli`, `vite-plugin-svgr`.

- [ ] **Step 4.3: Install**

```bash
cd src/frontend && npm install
```

If install fails with peer-dep conflict between Vite 8 and `@vitejs/plugin-react-swc` or `vite-tsconfig-paths`, check their latest versions — they may need coordinated bumps. If so, add to this sub-phase.

- [ ] **Step 4.4: Apply vite config migrations**

Read `src/frontend/vite.config.ts`. Apply any Vite 8 config changes flagged by the changelog (e.g., deprecated options removed). Common items:
- Node.js version requirement (Vite 8 may require higher)
- `build.target` defaults changed
- `server.hmr` options

- [ ] **Step 4.5: Run type-check**

```bash
npm run type-check
```

Expected: PASS. The `type-check` script runs `tsc --noEmit` then `vite` — this exercises both.

- [ ] **Step 4.6: Run unit tests**

```bash
npm test
```

Expected: PASS.

- [ ] **Step 4.7: Run dev server manually**

```bash
npm start
```

Expected: Vite dev server starts on :3000 with no startup warnings (beyond pre-existing). Load `http://localhost:3000`, confirm HMR by saving a component file and seeing reload. Then Ctrl-C.

- [ ] **Step 4.8: Run production build**

```bash
npm run build
```

Expected: clean build. Inspect `dist/` — index.html + assets exist.

- [ ] **Step 4.9: Present diff + verification to user**

```bash
git diff --stat
git diff src/frontend/package.json src/frontend/vite.config.ts
```

Ask: "Phase 2a diff + verification attached. Ready to commit?"

- [ ] **Step 4.10: Commit (only after explicit approval)**

```bash
git add src/frontend/package.json src/frontend/package-lock.json src/frontend/vite.config.ts
git commit -m "chore(deps): bump frontend build toolchain — phase 2a

- vite 7→8
- esbuild 0.25→0.28
- @swc/cli 0.5→0.8
- vite-plugin-svgr 4→5

Verification: type-check + test + dev server + build all pass."
```

**Stop-the-line rule:** if vite config migration exceeds ~30 min, split vite into its own sub-phase.

---

## Task 5 (Phase 2b): Type definitions

**Scope:** `@types/node` 20→25, `@types/jest` 29→30, `@types/uuid` 9→10, `@types/axios` 0.14→0.9.

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: any TS file that surfaces new type errors after the bump

- [ ] **Step 5.1: Bump `@types/*` versions**

```diff
-    "@types/jest": "^29.5.12",
+    "@types/jest": "^30.0.0",
-    "@types/node": "^20.14.2",
+    "@types/node": "^25.6.0",
-    "@types/uuid": "^9.0.8"
+    "@types/uuid": "^10.0.0"
```

For `@types/axios`: current is `0.14.0`, latest is `0.9.36`. Note: `@types/axios` is deprecated — axios ships its own types since v0.14. **Remove `@types/axios` entirely** in this step and rely on axios's bundled types. Do not "downgrade" to `0.9.x`.

- [ ] **Step 5.2: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 5.3: Run tsc**

```bash
npm run type-check
```

Expected: may surface new errors from stricter `@types/node` 25 typings (e.g., Node globals, process.env, Buffer). Fix each error inline. Common patterns:
- `Buffer` usage needing explicit import from `'node:buffer'`
- `process.env.X` returning `string | undefined` (already-standard)
- New `setImmediate` / `clearImmediate` ambient shape

If Jest tests use `@types/jest` types in a way that broke (rare in 30.x), fix at call sites.

- [ ] **Step 5.4: Run tests**

```bash
npm test
```

Expected: PASS.

- [ ] **Step 5.5: Build**

```bash
npm run build
```

Expected: PASS.

- [ ] **Step 5.6: Present diff and commit (after approval)**

```bash
git add src/frontend/package.json src/frontend/package-lock.json
# plus any .ts files fixed
git commit -m "chore(deps): bump frontend type definitions — phase 2b

- @types/node 20→25
- @types/jest 29→30
- @types/uuid 9→10
- @types/axios removed (axios ships its own types)

<summarize any type fix-ups>"
```

---

## Task 6 (Phase 2c): TypeScript 5 → 6

**Scope:** `typescript` 5.9.3 → 6.0.3 (isolated).

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: `src/frontend/tsconfig.json`, many `.ts`/`.tsx` files

- [ ] **Step 6.1: Read TypeScript 6.0 release notes**

https://devblogs.microsoft.com/typescript/ (find the 6.0 release post)

Note removed APIs, stricter defaults, new errors.

- [ ] **Step 6.2: Bump version**

```diff
-    "typescript": "^5.4.5",
+    "typescript": "^6.0.3",
```

- [ ] **Step 6.3: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 6.4: Run tsc and capture errors**

```bash
npx tsc --noEmit 2>&1 | tee /tmp/ts6-errors.log
wc -l /tmp/ts6-errors.log
```

Expected: some new errors. Common TS 6 items:
- Stricter unknown-handling in catch blocks
- New `noImplicitOverride` defaults
- `useUnknownInCatchVariables` changes
- Deprecated lib updates

- [ ] **Step 6.5: Fix errors iteratively**

Work file-by-file, smallest-blast-radius first. Don't broad-silence errors with `any` or `// @ts-ignore` — fix the underlying typing. If an error reveals a genuine bug, fix the bug in the same commit.

If the error count exceeds ~100 or a specific migration pattern repeats dozens of times, consider invoking stop-the-line: split this task into a separate tracked spec + plan.

- [ ] **Step 6.6: Run `npm run type-check` to final-verify**

Expected: PASS.

- [ ] **Step 6.7: Run `npm test` and `npm run build`**

Expected: PASS.

- [ ] **Step 6.8: Present diff and commit (after approval)**

```bash
git add src/frontend/package.json src/frontend/package-lock.json src/frontend/tsconfig.json
# plus all fixed .ts/.tsx files
git commit -m "chore(deps): bump typescript 5→6 — phase 2c

<summarize the categories of type fix-ups made>"
```

---

## Task 7 (Phase 2d): Routing / state / forms

**Scope:** `react-router-dom` 6→7, `zustand` 4→5, `@hookform/resolvers` 3→5.

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: router setup (`src/frontend/src/routes/**/*`, `src/frontend/src/main.tsx`), zustand stores (`src/frontend/src/stores/**/*`), form setup.

- [ ] **Step 7.1: Read changelogs**
  - React Router 6→7: https://reactrouter.com/upgrading/v6
  - Zustand 4→5: https://github.com/pmndrs/zustand/releases/tag/v5.0.0
  - @hookform/resolvers 3→5: https://github.com/react-hook-form/resolvers/releases

- [ ] **Step 7.2: Bump versions**

```diff
-    "react-router-dom": "^6.23.1",
+    "react-router-dom": "^7.14.1",
-    "zustand": "^4.5.2",
+    "zustand": "^5.0.12",
-    "@hookform/resolvers": "^3.6.0",
+    "@hookform/resolvers": "^5.2.2",
```

- [ ] **Step 7.3: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 7.4: Run `@react-router/dev migrate` if available**

The React Router 7 project ships an automated codemod:

```bash
npx @react-router/dev migrate || true
```

Review the produced diff. If the codemod doesn't cover the codebase style, proceed manually.

- [ ] **Step 7.5: Apply router 7 migrations manually**

Key items (consult changelog for full list):
- `Routes`/`Route` still work, but data-router APIs (`createBrowserRouter` vs `BrowserRouter`) are the recommended path. Pick one and stick to it — don't mix.
- Deprecated APIs (e.g., `useMatch` variants) removed.
- `Link` / `NavLink` may have prop changes.

- [ ] **Step 7.6: Apply Zustand 5 migrations**

Key items:
- `create` signature: `create<T>()` (note the parens) is now required for TypeScript-typed stores — already the pattern in most codebases, but audit.
- Subscribe selector signature changes.
- Default equality function changed to `Object.is` (was shallow in some helpers).

Grep for `create(` and `useStore(` patterns:

```bash
grep -rn "create(" src/frontend/src/stores/ | head
```

Fix each store type signature as needed.

- [ ] **Step 7.7: Apply @hookform/resolvers 5 migrations**

Key items: import paths remained the same; zod resolver signature may require `zod` 3.x compatibility mode when paired with `zod` 4 (see Phase 2e). If Phase 2e hasn't run yet (and it hasn't — 2e is the next task), don't worry about zod compatibility here; just verify forms still build.

- [ ] **Step 7.8: Run type-check**

```bash
npm run type-check
```

Fix new type errors. Most will be router/zustand API renames.

- [ ] **Step 7.9: Run tests**

```bash
npm test
```

Expected: PASS.

- [ ] **Step 7.10: Run dev server and smoke routes + stores + forms**

```bash
npm start
```

Manual:
- Load `http://localhost:3000`
- Log in (exercises routing + forms)
- Navigate: flow list → flow editor → settings → back (exercises router)
- Open a form-heavy panel (exercises forms)
- Interact with a feature backed by a zustand store (flow editing, assist panel)

Expected: every route loads; no console errors; state updates visible.

- [ ] **Step 7.11: Build**

```bash
npm run build
```

- [ ] **Step 7.12: Present diff and commit (after approval)**

```bash
git add src/frontend/package.json src/frontend/package-lock.json
# plus all migrated router/store/form files
git commit -m "chore(deps): bump routing/state/forms — phase 2d

- react-router-dom 6→7 (data router consolidation)
- zustand 4→5 (create() signature + Object.is equality)
- @hookform/resolvers 3→5

<summarize migration touches>"
```

---

## Task 8 (Phase 2e): Zod 3 → 4

**Scope:** `zod` 3.25.76 → 4.3.6 (isolated).

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: every file that uses `z.` from `zod` (forms validators, API response parsers)

- [ ] **Step 8.1: Read Zod 4 changelog**

https://zod.dev/v4

Key breaking items (as of 4.x release):
- Some schema methods renamed / signatures changed
- Error map API reshaped
- `.strict()` / `.passthrough()` defaults may differ
- `z.string().email()` and some refinements changed

- [ ] **Step 8.2: Find all zod call sites**

```bash
grep -rn "from \"zod\"" src/frontend/src | wc -l
grep -rn "z\." src/frontend/src | grep -v node_modules | head -30
```

Get a sense of scale.

- [ ] **Step 8.3: Bump version**

```diff
-    "zod": "^3.23.8",
+    "zod": "^4.3.6",
```

- [ ] **Step 8.4: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 8.5: Run type-check; fix errors**

```bash
npm run type-check 2>&1 | tee /tmp/zod4-errors.log
```

Fix each error. Common patterns:
- `ZodError.issues` access shape may differ
- Custom error messages passed as strings vs. `{ message: ... }`
- Async refinements signature

- [ ] **Step 8.6: Run tests**

```bash
npm test
```

Expected: PASS. If tests use Zod schemas directly, they may need updates.

- [ ] **Step 8.7: Smoke error paths**

Start dev server. Trigger a form validation error (submit a login form with invalid email). Verify the error renders correctly — Zod errors drive form error UI.

- [ ] **Step 8.8: Build + present + commit (after approval)**

```bash
npm run build
git diff --stat
# approval gate
git add <all touched files>
git commit -m "chore(deps): bump zod 3→4 — phase 2e

<summarize schema API migrations made>"
```

**Coordination note:** `@hookform/resolvers` (bumped in Task 7) must be compatible with Zod 4. If it isn't, this task must pre-install the resolver package's zod4-compat path (see resolver docs — typically `@hookform/resolvers/zod4` or similar).

---

## Task 9 (Phase 2f): UI libs

**Scope:** `ag-grid-community` + `ag-grid-react` 32→35, `framer-motion` 11→12, `lucide-react` 0.5→1, `react-markdown` 9→10, `react-pdf` 9→10, `vanilla-jsoneditor` 2→3.

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: any file using these UI libs (grep per lib)

- [ ] **Step 9.1: Read each changelog, note breaking items**
  - ag-Grid 32→35: https://www.ag-grid.com/changelog/ (column API, theme system changed across 33, 34, 35)
  - framer-motion 11→12: https://github.com/framer/motion/releases
  - lucide-react 0.5→1: https://github.com/lucide-icons/lucide/releases
  - react-markdown 9→10: https://github.com/remarkjs/react-markdown/releases
  - react-pdf 9→10: https://github.com/wojtekmaj/react-pdf/releases
  - vanilla-jsoneditor 2→3: https://github.com/josdejong/svelte-jsoneditor/blob/main/CHANGELOG.md

- [ ] **Step 9.2: Bump all 7 packages in package.json**

(Seven because ag-grid ships community + react as separate packages.)

```diff
-    "@xyflow/react": "^12.3.6",  # not in this batch
-    "ag-grid-community": "^32.3.9",
+    "ag-grid-community": "^35.2.1",
-    "ag-grid-react": "^32.3.9",
+    "ag-grid-react": "^35.2.1",
-    "framer-motion": "^11.2.10",
+    "framer-motion": "^12.38.0",
-    "lucide-react": "^0.575.0",
+    "lucide-react": "^1.8.0",
-    "react-markdown": "^9.1.0",
+    "react-markdown": "^10.1.0",
-    "react-pdf": "^9.0.0",
+    "react-pdf": "^10.4.1",
-    "vanilla-jsoneditor": "^2.3.3",
+    "vanilla-jsoneditor": "^3.12.0",
```

- [ ] **Step 9.3: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 9.4: Apply ag-grid migrations**

Grep for ag-grid usage:

```bash
grep -rn "ag-grid" src/frontend/src | head -30
```

Common changes across 32→35:
- Column API renamed (`api.setColumnDefs` → `api.setGridOption('columnDefs', ...)`)
- Theme system: legacy themes → new "Quartz" theme system (may need CSS changes)
- Module registration model

- [ ] **Step 9.5: Apply framer-motion 12 migrations**

Usually backward-compatible but check: `motion` vs `m` imports, layout animations.

- [ ] **Step 9.6: Apply lucide-react 1.0 migrations**

Major version: some icon names renamed. Grep for all icon imports:

```bash
grep -rn "from \"lucide-react\"" src/frontend/src | head
```

Run `npm run type-check` to surface removed icon exports, then fix imports.

- [ ] **Step 9.7: Apply react-markdown 10 migrations**

Check: new plugin API, `components` prop shape stable.

- [ ] **Step 9.8: Apply react-pdf 10 migrations**

Check: worker URL setup, rendering API.

- [ ] **Step 9.9: Apply vanilla-jsoneditor 3 migrations**

Props or CSS changes per changelog.

- [ ] **Step 9.10: Type-check + tests**

```bash
npm run type-check && npm test
```

- [ ] **Step 9.11: Dev server smoke**

Boot `npm start`. Exercise:
- A page with ag-grid (file/log viewer, flow history, whichever uses the grid)
- A sheet/dialog (framer-motion)
- Any lucide icons visible in sidebar / toolbar
- Chat or assist render (react-markdown, react-pdf if PDF rendered)
- Open the JSON editor (vanilla-jsoneditor) — flow import/export or any settings form

- [ ] **Step 9.12: Build + present + commit (after approval)**

```bash
npm run build
git diff --stat
# approval gate
git commit -m "chore(deps): bump UI libs — phase 2f

- ag-grid-community + ag-grid-react 32→35 (column API, theme system)
- framer-motion 11→12
- lucide-react 0→1
- react-markdown 9→10
- react-pdf 9→10
- vanilla-jsoneditor 2→3

<summarize migration touches>"
```

**Stop-the-line rule:** ag-grid alone may swallow the whole sub-phase. If it does, split ag-grid into its own commit and land the other 5 as a separate commit.

---

## Task 10 (Phase 2g): Utility libs

**Scope:** `uuid` 10→14, `dotenv` 16→17, `web-vitals` 4→5, `ua-parser-js` 1→2, `moment-timezone` 0.5→0.6, `react-cookie` 7→8, `react-error-boundary` 4→6, `react-hotkeys-hook` 4→5, `p-debounce` 4→5, `elkjs` 0.9→0.11, `openseadragon` 4→6.

**Files:**
- Modify: `src/frontend/package.json`
- Possibly modify: call sites of each lib

- [ ] **Step 10.1: Read each changelog** (11 packages; 2-3 min each to skim)

- [ ] **Step 10.2: Bump all 11 packages in package.json**

(Follow the same caret-bump pattern. Reference version numbers in § Scope above.)

- [ ] **Step 10.3: Install**

```bash
cd src/frontend && npm install
```

- [ ] **Step 10.4: Apply per-package migrations**

Spot per-lib:
- `uuid` 10→14: import path may have changed (`import { v4 } from 'uuid'` still works; ESM-only). Verify jest setup still resolves.
- `ua-parser-js` 1→2: API stabilized to `UAParser` instance; call sites may need small fixes.
- `react-error-boundary` 4→6: `FallbackComponent` prop still works; check `onReset` signature.
- `react-hotkeys-hook` 4→5: `useHotkeys` options arg reshape.
- `moment-timezone` 0.5→0.6: should be backward-compatible (`moment` itself is deprecated upstream but we keep it).
- `openseadragon` 4→6: two major bumps; OSD viewer options may have changed.
- `dotenv` 16→17: mostly bug fixes.
- `p-debounce` 4→5: ESM-only — verify jest is configured for ESM or use dynamic import.

- [ ] **Step 10.5: Type-check + tests + build**

```bash
npm run type-check && npm test && npm run build
```

- [ ] **Step 10.6: Smoke affected features**

Boot dev server. Check:
- Hotkey combinations still fire (press a known shortcut)
- Cookies persist across reload
- Error boundary catches a deliberately thrown error (if a dev toggle exists)
- UUID generation still works (create a new flow — ID generation path)
- OpenSeadragon viewer opens (wherever images are deep-zoomed)

- [ ] **Step 10.7: Present + commit (after approval)**

```bash
git commit -m "chore(deps): bump frontend utility libs — phase 2g

<list all 11 with versions>

<summarize migration touches>"
```

---

## Task 11: Validate Phase 2 end-to-end, merge back

**Files:** none (process step)

- [ ] **Step 11.1: Full frontend test run**

```bash
cd src/frontend && npm test
```

- [ ] **Step 11.2: Full backend test run (should be untouched but verify)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/deps-upgrade-2026-04
make unit_tests
```

- [ ] **Step 11.3: Run Playwright e2e if practical**

```bash
make tests_frontend
```

Expected: PASS (or skip if the suite is too slow locally; document the skip).

- [ ] **Step 11.4: Full app smoke test**

Boot both services. Exercise:
- Login flow (auth, forms, zod validation)
- Flow list (routing, react-query)
- Flow editor (xyflow, zustand, ag-grid if flow-data panel open)
- Run a flow (end-to-end data path)
- Open assist / chat (react-markdown)
- Settings pages (forms, stores)

- [ ] **Step 11.5: Present Phase 2 summary, request merge approval**

```bash
git log platform-multi-tenant..HEAD --oneline
```

Expect: 7 Phase-2 commits (2a–2g).

Ask: "Phase 2 complete and validated. Ready to merge `deps/upgrade-2026-04` into `platform-multi-tenant`?"

**Important follow-up flag:** after this merge, the next priority per the spec is the Tailwind CSS 3→4 migration. Open `docs/superpowers/specs/YYYY-MM-DD-tailwind-4-migration-design.md` as a new brainstorming session.

- [ ] **Step 11.6: Merge back (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git checkout platform-multi-tenant
git merge --no-ff deps/upgrade-2026-04 -m "merge: dependency updates phase 2"
cd .worktrees/deps-upgrade-2026-04
```

---

# PHASE 3 — Backend core-infra breaking bumps (4 sub-phase commits)

## Task 12 (Phase 3a): Web framework

**Scope:** `fastapi` 0.135→0.136, `uvicorn` 0.41→0.44, `gunicorn` 22→25, `typer` 0.19→0.24, `rich` 13→15.

**Files:**
- Modify: `pyproject.toml`, `src/backend/base/pyproject.toml`, `src/lfx/pyproject.toml`
- Modify: `uv.lock`
- Possibly modify: anything using `typer` CLI decorators or `rich` Console API

- [ ] **Step 12.1: Read each changelog**
  - FastAPI 0.135→0.136: https://fastapi.tiangolo.com/release-notes/
  - Uvicorn 0.41→0.44: https://github.com/encode/uvicorn/releases
  - Gunicorn 22→25: https://docs.gunicorn.org/en/stable/news.html (three majors; Python 3.7 support dropped, etc.)
  - Typer 0.19→0.24: https://typer.tiangolo.com/release-notes/
  - Rich 13→15: https://github.com/Textualize/rich/blob/master/CHANGELOG.md

- [ ] **Step 12.2: Edit spec upper bounds**

Many specs use `<24.0.0`-style upper bounds that exclude the new versions. Widen them:

```diff
- "gunicorn>=22.0.0,<23.0.0",
+ "gunicorn>=25.0.0,<26.0.0",

- "typer>=0.13.0,<1.0.0",       # already OK, but set floor higher
+ "typer>=0.24.0,<1.0.0",

- "uvicorn>=0.30.0,<1.0.0",
+ "uvicorn>=0.44.0,<1.0.0",

- "rich>=13.7.0,<14.0.0",
+ "rich>=15.0.0,<16.0.0",

- "fastapi>=0.135.0,<1.0.0",
+ "fastapi>=0.136.0,<1.0.0",
```

Apply the same changes in all three pyproject files that declare each package.

- [ ] **Step 12.3: Regenerate lockfile**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/deps-upgrade-2026-04
uv lock
uv sync
```

- [ ] **Step 12.4: Apply code migrations**

- **Typer:** recent versions stabilized some options. Grep for `typer.Option(` / `typer.Argument(` and verify signatures.
- **Rich:** theme / console APIs — verify `Console()` construction and any `Table` usage.
- **Gunicorn:** worker config; ensure `wsgi` / `asgi` patterns in `Dockerfile` / deployment scripts still apply.

Files likely touched:
- `src/backend/base/langflow/__main__.py` (Typer entry)
- `src/lfx/src/lfx/cli/**/*.py` (lfx Typer CLI)
- Any `rich.console` / `rich.table` usage

- [ ] **Step 12.5: Run lint**

```bash
make lint
```

- [ ] **Step 12.6: Run unit tests**

```bash
make unit_tests
```

- [ ] **Step 12.7: Boot server + smoke**

```bash
make backend
```

In another shell:
```bash
curl -s http://localhost:7860/health
# exercise a route that streams (/api/v1/run/*)
```

Expected: server boots, `/health` returns 200, streaming endpoint emits chunks.

- [ ] **Step 12.8: Test `lfx` CLI**

```bash
uv run lfx --help
```

Expected: CLI renders correctly (Typer + Rich integration).

- [ ] **Step 12.9: Present + commit (after approval)**

```bash
git diff --stat
git commit -m "chore(deps): bump backend web framework — phase 3a

- fastapi 0.135→0.136
- uvicorn 0.41→0.44
- gunicorn 22→25
- typer 0.19→0.24
- rich 13→15

<summarize migration touches>"
```

---

## Task 13 (Phase 3b): Security / auth

**Scope:** `bcrypt` 4→5, `cryptography` 43→46 (isolated — high risk).

**Files:**
- Modify: `src/backend/base/pyproject.toml`, `src/lfx/pyproject.toml`
- Modify: `uv.lock`
- Possibly modify: auth modules (`src/backend/base/langflow/services/auth/**/*`)
- Possibly modify: cryptography users (`src/lfx/src/lfx/services/secret_store/**/*`, any encryption utilities)

- [ ] **Step 13.1: Read changelogs**
  - bcrypt 4→5: https://github.com/pyca/bcrypt/blob/main/CHANGELOG.rst — note hash compatibility notes for versions stored by 4.x
  - cryptography 43→46: https://cryptography.io/en/latest/changelog/ — scan for removed algorithms and API changes across three majors

- [ ] **Step 13.2: Identify bcrypt call sites**

```bash
grep -rn "bcrypt\|passlib" src/backend/base/langflow src/lfx/src | grep -v "\.pyc" | head -30
```

Common call site: password hashing at `src/backend/base/langflow/services/auth/utils.py` (or similar). Note the hashing scheme in use (bcrypt direct vs passlib's CryptContext wrapping bcrypt).

- [ ] **Step 13.3: Identify cryptography call sites**

```bash
grep -rn "from cryptography" src/backend/base src/lfx/src | head -30
```

Note modules using `Fernet`, `hazmat`, or specific ciphers. Check the changelog for any of those with removal markers.

- [ ] **Step 13.4: Edit specs**

```diff
- "bcrypt==4.0.1",
+ "bcrypt>=5.0.0,<6.0.0",

- "cryptography>=43.0.1,<44.0.0",
+ "cryptography>=46.0.7,<47.0.0",
```

(Apply in both `src/backend/base/pyproject.toml` and `src/lfx/pyproject.toml` as applicable.)

- [ ] **Step 13.5: Regenerate lockfile**

```bash
uv lock
uv sync
```

- [ ] **Step 13.6: Apply cryptography migrations**

For each call site identified in 13.3, verify the imported name still exists in 46.x. Common patterns:
- `Fernet` — stable
- `hazmat.primitives.asymmetric.padding` — check deprecations
- `x509` — stable across 43-46

- [ ] **Step 13.7: Apply bcrypt migrations**

If `passlib.CryptContext(schemes=["bcrypt"], ...)` is used, passlib handles bcrypt version compat internally. Check passlib + bcrypt 5 compatibility — if passlib doesn't support bcrypt 5, we need passlib upgraded too (or pin bcrypt).

If direct `bcrypt.hashpw` / `bcrypt.checkpw` is used, v5 should still verify hashes produced by v4 — but confirm with a test.

- [ ] **Step 13.8: Run lint**

```bash
make lint
```

- [ ] **Step 13.9: Write backward-compat test for password verification**

Add to `src/backend/tests/unit/services/test_auth.py` (or closest existing auth test module):

```python
def test_bcrypt_5_verifies_bcrypt_4_hash():
    """A hash produced by bcrypt 4 must verify under bcrypt 5."""
    # Hash produced by bcrypt 4.0.1 on password "test123"
    # (Generate once locally, paste the hash literal below)
    legacy_hash = b"$2b$12$<literal-hash-generated-under-bcrypt-4>"
    from langflow.services.auth.utils import verify_password  # adjust to real path
    assert verify_password("test123", legacy_hash.decode())
```

To generate the legacy hash, either check one out of an existing dev database or run a one-off: `pip install 'bcrypt==4.0.1' && python -c "import bcrypt; print(bcrypt.hashpw(b'test123', bcrypt.gensalt()).decode())"` (in a disposable venv — don't mix with the repo venv).

- [ ] **Step 13.10: Run the new test**

```bash
uv run pytest src/backend/tests/unit/services/test_auth.py::test_bcrypt_5_verifies_bcrypt_4_hash -v
```

Expected: PASS. If FAIL, bcrypt 5 is incompatible with 4-era hashes and we need a rehash-on-login path in the auth service — add it in this commit:

```python
# In auth service: after successful password verification, if the hash is a
# legacy format, re-hash and update the stored password.
if legacy_hash_format(stored):
    new_hash = hash_password(plaintext)
    await user_service.update_password_hash(user.id, new_hash)
```

Then re-run the test and confirm PASS.

- [ ] **Step 13.11: Run full unit tests**

```bash
make unit_tests
```

- [ ] **Step 13.12: Smoke the login flow**

```bash
make backend
```

In another shell or browser:
- Log in with an existing user that was created before this upgrade.
- Expected: 200 OK, session established.
- Then log out, log in again (ensures rehash-on-login path works on second login if it was triggered).

- [ ] **Step 13.13: Test webhook API key + JWT flows**

The webhook API key path uses cryptography for signing. Hit:
```bash
# create/run a webhook-triggered flow through the UI, dispatch with its key
curl -H "x-api-key: <key>" -X POST http://localhost:7860/api/v1/webhook/<flow_id>/run -d '{}'
```

Expected: 200.

- [ ] **Step 13.14: Present + commit (after approval)**

```bash
git commit -m "chore(deps): bump security — phase 3b

- bcrypt 4→5 (verified hash forward-compat, added regression test)
- cryptography 43→46 (three majors; verified Fernet/hazmat usage)

<summarize any code migration or rehash path added>"
```

---

## Task 14 (Phase 3c): Pillow 11 → 12

**Scope:** `pillow` 11.3.0 → 12.2.0 (isolated).

**Files:**
- Modify: `src/backend/base/pyproject.toml`, `src/lfx/pyproject.toml`
- Modify: `uv.lock`
- Possibly modify: image-handling components

- [ ] **Step 14.1: Read Pillow 12 changelog**

https://pillow.readthedocs.io/en/stable/releasenotes/12.0.0.html — list of removed/deprecated APIs.

- [ ] **Step 14.2: Identify Pillow call sites**

```bash
grep -rn "from PIL\|import PIL" src/backend/base src/lfx/src | head -30
```

Flag files that use Pillow directly.

- [ ] **Step 14.3: Edit specs**

```diff
- "pillow>=11.1.0,<12.0.0",
+ "pillow>=12.2.0,<13.0.0",
```

- [ ] **Step 14.4: Regenerate lockfile + sync**

```bash
uv lock && uv sync
```

- [ ] **Step 14.5: Apply migrations**

Run `make lint` and `make unit_tests` first — let the compiler / test failures tell you what broke. Common Pillow-12 issues:
- Removed deprecated `Image.ANTIALIAS` constants (use `Image.Resampling.LANCZOS`)
- `Image.textlength` / `textbbox` signature stability
- Removed `ImageDraw.getmask` deprecations

Fix each call site.

- [ ] **Step 14.6: Smoke image components**

Boot `make backend` + `make frontend`. Open a flow with an image input component. Upload an image, run the flow. Verify output contains the image or its derived artifact.

- [ ] **Step 14.7: Present + commit (after approval)**

```bash
git commit -m "chore(deps): bump pillow 11→12 — phase 3c

<summarize any API migration touches>"
```

---

## Task 15 (Phase 3d): Misc small backend breaking bumps

**Scope:** `aiofiles` 24→25, `chardet` 5→7, `docstring-parser` 0.17→0.18, `json-repair` 0.30→0.59, `prometheus-client` 0.24→0.25, `validators` 0.34→0.35.

**Files:**
- Modify: `src/backend/base/pyproject.toml`, `src/lfx/pyproject.toml` (as applicable)
- Modify: `uv.lock`
- Possibly modify: call sites

- [ ] **Step 15.1: Read changelogs** (six packages; quick skim each)

- [ ] **Step 15.2: Edit specs for all 6 packages**

```diff
- "aiofiles>=24.1.0,<25.0.0",
+ "aiofiles>=25.1.0,<26.0.0",

- "chardet>=5.2.0,<6.0.0",
+ "chardet>=7.4.3,<8.0.0",

- "docstring-parser>=0.16,<1.0.0",  # already permissive; ensure 0.18 resolves
+ "docstring-parser>=0.18,<1.0.0",

- "json-repair>=0.30.3,<1.0.0",  # already permissive
+ "json-repair>=0.59.4,<1.0.0",

- "prometheus-client>=0.20.0,<1.0.0",
+ "prometheus-client>=0.25.0,<1.0.0",

- "validators>=0.34.0,<1.0.0",
+ "validators>=0.35.0,<1.0.0",
```

Apply in both `src/backend/base/pyproject.toml` and `src/lfx/pyproject.toml` as applicable per spec.

- [ ] **Step 15.3: Regenerate lockfile + sync**

```bash
uv lock && uv sync
```

- [ ] **Step 15.4: Run lint + tests + build**

```bash
make lint && make unit_tests && make run_clic
```

If any fails, investigate the culprit. Each of these libs has a narrow surface, so fixes are usually small.

- [ ] **Step 15.5: Present + commit (after approval)**

```bash
git commit -m "chore(deps): bump backend misc breaking — phase 3d

- aiofiles 24→25
- chardet 5→7 (two majors)
- docstring-parser 0.17→0.18
- json-repair 0.30→0.59
- prometheus-client 0.24→0.25
- validators 0.34→0.35

<summarize any touches>"
```

---

## Task 16: Validate Phase 3 end-to-end, merge back

**Files:** none (process step)

- [ ] **Step 16.1: Full backend test run**

```bash
make unit_tests
```

- [ ] **Step 16.2: Full build + run**

```bash
make run_clic
```

Exercise:
- Login
- Flow list / open a flow / run a flow
- Webhook endpoint dispatch (exercises cryptography + fastapi)
- Streaming endpoint (exercises uvicorn + fastapi)
- Image component (exercises Pillow)
- Typer CLI (`uv run lfx --help`, `uv run langflow --help`)

- [ ] **Step 16.3: Present Phase 3 summary, request merge approval**

```bash
git log platform-multi-tenant..HEAD --oneline
```

Expect: 4 Phase-3 commits (3a–3d).

Ask: "Phase 3 complete and validated. Ready to merge `deps/upgrade-2026-04` into `platform-multi-tenant`?"

- [ ] **Step 16.4: Merge back (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git checkout platform-multi-tenant
git merge --no-ff deps/upgrade-2026-04 -m "merge: dependency updates phase 3"
```

- [ ] **Step 16.5: Clean up worktree**

```bash
git worktree remove .worktrees/deps-upgrade-2026-04
git branch -d deps/upgrade-2026-04
```

(Use `-D` instead of `-d` only if the branch is refusing to delete — which shouldn't happen after a merge.)

---

## Task 17: Final handoff — queue the Tailwind 4 follow-up

**Files:**
- None edited here; this is a handoff step.

- [ ] **Step 17.1: Confirm 13 commits are on `platform-multi-tenant`**

```bash
git log --oneline platform-multi-tenant | grep "chore(deps):" | head -15
```

Expected: 13 commits visible (2 Phase-1 + 7 Phase-2 + 4 Phase-3), plus 3 merge commits.

- [ ] **Step 17.2: Remind user of deferred follow-ups**

Summarize:
- ✅ Phase 1 / 2 / 3 complete and merged
- ⏭️ **Next priority: Tailwind CSS 3 → 4** — kick off a new brainstorming session to produce `docs/superpowers/specs/YYYY-MM-DD-tailwind-4-migration-design.md`. Start with `npx @tailwindcss/upgrade` spike.
- 📋 Further deferred: LangChain 0.3 → 1.x ecosystem; Pandas 2 → 3. Each gets its own spec when prioritized.

- [ ] **Step 17.3: Update the original spec with a completion stamp (optional)**

Append to `docs/superpowers/specs/2026-04-19-dependency-updates-design.md`:

```markdown
## Status

**Shipped 2026-MM-DD** — all 13 sub-phase commits landed on `platform-multi-tenant`. Deferred follow-ups (Tailwind 4, LangChain 1.x, Pandas 3) remain open.
```

---

## Self-review notes

- **Spec coverage:** every item in the spec's in-scope lists maps to a task (Phase 1a/b → Tasks 1-2, Phase 2a-g → Tasks 4-10, Phase 3a-d → Tasks 12-15). Deferred items tracked in Task 17.
- **Approval gates:** every commit step includes an explicit "wait for approval" pause, per user memory.
- **Merge strategy:** per-phase, not per-sub-phase, per the spec.
- **Stop-the-line rules:** called out in Tasks 4, 6, 9 where migration may exceed scope.
- **Baseline comparison:** Task 0 records baselines used by later verification steps.
- **No placeholders:** all package names and version targets are concrete; commit messages are templates with `<summarize ...>` placeholders because migration specifics depend on what the engineer finds — that's expected and not a planning failure.
