# Frontend npm upgrade — design

**Date:** 2026-04-24
**Scope:** `src/frontend/` only. `docs/` and `scripts/aws/` are explicitly out of scope.
**Owner:** bryced
**Branch:** `platform-multi-tenant` (effective main per project memory)

## Goal

Move every outdated npm package in `src/frontend/package.json` to its latest version in a single PR, with automated verification (`tsc`, lint, jest) and manual UI verification performed by the user.

## Packages in scope

Based on `npm outdated` run on 2026-04-24 from `src/frontend/`:

| Package | Current | Target | Manifest change needed? |
|---|---|---|---|
| `@tailwindcss/vite` | 4.2.2 | 4.2.4 | No (caret picks it up) |
| `tailwindcss` | 4.2.2 | 4.2.4 | No |
| `@tanstack/react-query` | 5.99.2 | 5.100.1 | No |
| `axios` | 1.15.1 | 1.15.2 | No |
| `dompurify` | 3.4.0 | 3.4.1 | No |
| `lucide-react` | 1.8.0 | 1.9.0 | No |
| `react-hook-form` | 7.72.1 | 7.73.1 | No |
| `react-router-dom` | 7.14.1 | 7.14.2 | No |
| `vite` | 8.0.8 | 8.0.10 | No |
| `@biomejs/biome` | 2.4.12 | 2.4.13 | Yes — exact pin, no caret |
| `tailwind-merge` | 2.6.1 | 3.5.0 | Yes — major bump, widen `^2.3.0` → `^3.5.0` |

## Execution plan

Three phases, verified independently so a failure bisects cleanly. All work happens in `src/frontend/`. Manual UI testing is out of scope for this plan — the user will perform it after the PR is prepared.

### Phase 1 — `tailwind-merge` 2 → 3 (major)

This is the only bump with meaningful breaking-change risk, so it goes first while the working tree is otherwise clean.

1. Enumerate every call site:
   ```
   grep -rn --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' \
     -E 'twMerge|extendTailwindMerge|from ["'\'']tailwind-merge' src/frontend/src
   ```
2. Cross-check each usage against the tailwind-merge v3 changelog. Known risk areas:
   - `extendTailwindMerge` config shape changed: top-level `classGroups` / `conflictingClassGroups` keys moved under `extend` / `override`.
   - Several validator names were renamed.
   - `twMerge` factory without a config argument is no longer supported.
3. Edit `src/frontend/package.json`: `"tailwind-merge": "^2.3.0"` → `"tailwind-merge": "^3.5.0"`.
4. Apply any code fixes the scan requires.
5. `npm install` inside `src/frontend/`.
6. Verify: `tsc --noEmit --pretty --project tsconfig.json`, `npm run lint`, `npm test`.
7. **Stop and report** if any verification step fails.

### Phase 2 — caret-range sweep

1. `npm update` inside `src/frontend/` — picks up the nine in-range bumps listed above.
2. Verify: `tsc --noEmit`, `npm run lint`, `npm test`.
3. Stop and report on failure.

### Phase 3 — exact-pinned bump

1. Edit `src/frontend/package.json`: `"@biomejs/biome": "2.4.12"` → `"2.4.13"` (keep exact pin — no caret).
2. `npm install`.
3. Verify: `npm run lint` (biome is the linter), `npm test`.

## Verification bar

Per phase, all of:

- `tsc --noEmit --pretty --project tsconfig.json` exits 0
- `npm run lint` exits 0
- `npm test` (jest) exits 0

Playwright e2e, Storybook builds, and `npm start` smoke tests are explicitly **not** required by this plan — the user will handle manual browser verification post-PR.

## Deliverables

- Modified `src/frontend/package.json`
- Modified `src/frontend/package-lock.json`
- Any code edits required by tailwind-merge v3
- Status report listing each package's `before → after` and the exit codes of each verification command

## Out of scope

- `src/frontend/package.json` `overrides` block (`tar`, `tar-fs`, `glob`, `test-exclude`) — security pins, leave alone unless `npm install` complains.
- `engines.node` bump.
- Storybook and Playwright runs.
- `docs/package.json` and `scripts/aws/package.json`.
- Node version upgrades in CI.
- Any backend / uv / Python changes.

## Failure handling

If any phase's verification fails:

1. Stop; do not proceed to the next phase.
2. Surface the failure (truncated relevant output) and a proposed fix.
3. Ask before applying fixes that go beyond trivial type or import adjustments.

If a fix would balloon (e.g., tailwind-merge v3 requires a non-trivial refactor), pause and ask whether to:

- continue and absorb the refactor in this PR,
- defer that one bump and ship the rest,
- split into two PRs after all.

## Rollback

Single branch, single PR. To revert:

```
git restore src/frontend/package.json src/frontend/package-lock.json
rm -rf src/frontend/node_modules
(cd src/frontend && npm install)
```

No database migrations, no external state.

## Notes for implementer

- Per project memory (`feedback_no_git_commits`), do not commit without asking first — even though the plan produces committable output, the implementer must pause for permission at the commit step.
- Per project memory (`feedback_subagent_commit_hygiene`), any dispatched subagents must stage explicit paths, never `git add -A` / `git add .`.
- This branch (`platform-multi-tenant`) is the effective main (`project_main_branch_equivalent.md`), so work lands directly here.
