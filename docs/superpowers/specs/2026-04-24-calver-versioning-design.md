# CalVer versioning — design

**Date:** 2026-04-24
**Scope:** Monorepo-wide version scheme change + helper script + initial migration.
**Owner:** bryced
**Branch:** `platform-multi-tenant` (effective main).

## Goal

Move the four versioned packages in this repo to a shared CalVer scheme (`YY.{M}{DD}.{B}`), migrate the two inter-package pins that would otherwise break, and add a helper script so future bumps are a one-command operation.

## Version format

```
YY.{M}{DD}.{B}
```

| Segment | Meaning | Rules |
|---|---|---|
| `YY` | 2-digit year | No leading zero (we're in the 2020s). |
| `M` | Month, 1–12 | **No** leading zero — npm/PEP 440 forbid leading zeros on numeric identifiers. |
| `DD` | Day, 01–31 | **Leading zero required** so numeric ordering matches chronological ordering (April 4 = `404`, not `44`). |
| `B` | Build number, 1, 2, 3, … | No leading zero. Starts at 1 each new calendar day. Increments on same-day re-release. |

**Examples:**

| Date | Build 1 | Build 2 |
|---|---|---|
| 2026-04-04 | `26.404.1` | `26.404.2` |
| 2026-04-24 | `26.424.1` | `26.424.2` |
| 2026-10-04 | `26.1004.1` | `26.1004.2` |
| 2026-12-31 | `26.1231.1` | `26.1231.2` |

**Ordering guarantees:**

- Jan–Sep produce 3-digit middles (101–930).
- Oct–Dec produce 4-digit middles (1001–1231).
- Numeric comparison agrees with chronological order because 3-digit < 4-digit always, and within each block the encoding preserves month-then-day order.

**Compatibility:**

- Valid **npm semver** — three numeric identifiers, no leading zeros.
- Valid **PEP 440** — three-segment release version.
- `^26.424.1` (npm caret) → `>=26.424.1 <27.0.0` — all of 2026 satisfies it. Fine for monorepo use; worth knowing.

## Scope: files that change

### Initial migration (6 edits, once)

| File | Field | Before | After |
|---|---|---|---|
| `pyproject.toml` | `version` | `"1.8.4"` | `"26.424.1"` |
| `pyproject.toml` | dependency pin | `"langflow-base[complete]~=0.8.4"` | `"langflow-base[complete]>=26.424.1"` |
| `src/backend/base/pyproject.toml` | `version` | `"0.8.4"` | `"26.424.1"` |
| `src/backend/base/pyproject.toml` | dependency pin | `"lfx~=0.3.4"` | `"lfx>=26.424.1"` |
| `src/lfx/pyproject.toml` | `version` | `"0.3.4"` | `"26.424.1"` |
| `src/frontend/package.json` | `version` | `"1.8.4"` | `"26.424.1"` |

**Why `>=` on the inter-package pins:** `~=0.8.4` means "compatible with 0.8.x", which no longer matches `26.424.x`. Tight pins like `~=26.424.1` would force the pin to be re-edited on every build inside the same day (since `~=26.424.1` means `>=26.424.1, <26.425`). A loose `>=` avoids per-release churn, which is fine in a monorepo where the three Python packages always ship together.

### Ongoing bumps (4 edits, via script)

After migration, the helper script updates the four `version` fields only. Inter-package pins are left alone — you update them only when you genuinely need to raise the minimum (e.g., lfx adds a function langflow now depends on).

## Files explicitly out of scope

- `docs/package.json` (`"0.0.0"`) — docs-site placeholder, never published.
- `scripts/aws/package.json` (`"0.1.0"`) — AWS deploy scripts, independent.
- Runtime `__version__` constants in Python — they read from installed package metadata (`importlib.metadata.version(pkg_name)`), so they automatically pick up the new pyproject version. No edits needed.
- `.github/workflows/release.yml`, `release-lfx.yml`, `release_nightly.yml` — they read `version = …` from pyproject at build time. Schema is unchanged; they keep working. No edits needed.
- Docker image tags — same: they read the version at build time.

## Helper script: `scripts/bump_version.py`

### Interface

```
python scripts/bump_version.py                  # auto-compute
python scripts/bump_version.py --build 5        # explicit build
python scripts/bump_version.py --check          # dry-run: print diff, write nothing
make bump-version                               # Makefile wrapper over no-args form
```

### Behavior

1. Read current version from `pyproject.toml` (source of truth).
2. Compute today's `YY.{M}{DD}` using local time.
3. Determine new version:
   - **If `--build N`:** use `{today-YY-MDD}.N`.
   - **Else if current version's `YY.{M}{DD}` prefix matches today's:** increment the build number. (e.g., current `26.424.1` → new `26.424.2`.)
   - **Else:** use `{today-YY-MDD}.1`. (New calendar day resets build.)
4. If `--check`: print old/new for each of the 4 files and exit 0 without writing.
5. Else: update all 4 files. Print new version to stdout (for scripting: `NEW=$(python scripts/bump_version.py)`).

### Edge cases

- **Current version not in `YY.{M}{DD}.{B}` format** (i.e., during the initial migration, before the first bump): treat as "not today" — use `{today-YY-MDD}.1`.
- **`--build 0`:** rejected (`1` is the minimum build number).
- **Any file missing or unparsable:** exit non-zero with an error naming the file. Don't half-update.
- **Version field already at target value:** no-op success. Print a note to stderr.

### Implementation notes (for the plan)

- Python stdlib only where possible: `tomllib` (3.11+) for reading TOML, `json` for `package.json`.
- **Writing:** use line-level regex on the `version = "…"` line rather than a full TOML round-trip, to preserve formatting and comments. Same approach for `package.json`'s `"version": "…"` line. This is a targeted rewrite, not a parser.
- Atomic-ish: compute all new file contents first, then write each. A write failure mid-way leaves some files at new version and some at old — document this as a caveat and rely on the user re-running to correct it (don't build a transactional multi-file write).
- No auto-commit. No git operations at all.

### What the script does NOT do

- Commit or tag (user's preference: manual commit control).
- Touch inter-package pins (judgment call, not automation).
- Write to CI configs, Docker, docs.
- Validate that the computed version is greater than the current one (if you manually set a build lower than current, the script trusts you).

## Testing

Unit tests for the script, living at `scripts/tests/test_bump_version.py` (new directory). Reason: `bump_version.py` is a repo-level utility, not part of any Python package's test suite — keeping its tests next to it avoids polluting `src/backend/base/tests/unit/` with a concern that doesn't belong there. Add `scripts/tests/__init__.py` so pytest can discover them. Cover:

1. Same-day bump: current `26.424.1`, today is 2026-04-24 → new `26.424.2`.
2. New-day reset: current `26.424.5`, today is 2026-04-25 → new `26.425.1`.
3. Pre-migration state: current `1.8.4`, today is 2026-04-24 → new `26.424.1`.
4. Explicit `--build 7` on 2026-04-24 → `26.424.7` regardless of current.
5. `--check` leaves all files unchanged.
6. `--check` output names all 4 files and their old/new versions.
7. All 4 files end up at the same new version after a real bump.
8. Error when any file is missing.
9. Day with leading zero: 2026-04-04 → `26.404.1` (not `26.44.1`).
10. October day: 2026-10-04 → `26.1004.1`.

Tests should use a tmp-dir fixture with minimal TOML/JSON fixtures, not mutate the real repo files.

## Verification after migration

After editing the 6 files, confirm:

1. `uv sync` resolves cleanly (dep pins satisfied by new versions).
2. `cd src/frontend && npm install` completes without version-format errors.
3. `python -c "from importlib.metadata import version; print(version('langflow'))"` prints `26.424.1`.
4. `python scripts/bump_version.py --check` (with no args) prints "would bump build: 26.424.1 → 26.424.2" (since today matches and build is currently 1).
5. Re-run preflight from the npm upgrade plan: `npm outdated` still clean.

## Failure handling

- **`uv sync` fails after migration:** almost certainly a dep pin we missed. Grep for `~=0.8.4`, `~=0.3.4`, `~=1.8.4` across `pyproject.toml` files and update any we didn't catch.
- **`npm install` rejects the version:** means we picked a non-semver form somewhere. Fall back to `26.424.1` (confirmed valid).
- **Script rewrites a file incorrectly:** `git restore` the single file, investigate, fix the script, re-run.

## Rollback

Single branch, no external state. `git restore` the 6 files to revert the migration. Delete `scripts/bump_version.py`, `scripts/tests/test_bump_version.py`, and the Makefile target to remove the script.

## Notes for implementer

- Per project memory (`feedback_no_git_commits`), do not commit without asking first — not even the spec or the script.
- Per project memory (`feedback_subagent_commit_hygiene`), any dispatched subagents must stage explicit paths.
- `platform-multi-tenant` is the effective main (`project_main_branch_equivalent.md`); work lands directly here.
- The current `Makefile` uses `VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')` to derive version — that shell command still works with `26.424.1` unchanged, no Makefile edit required beyond adding the `bump-version` target.
