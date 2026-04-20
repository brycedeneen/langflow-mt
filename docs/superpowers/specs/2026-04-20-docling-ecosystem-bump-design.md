# Docling ecosystem coordinated bump — design

**Date:** 2026-04-20
**Branch:** TBD (new worktree, sequenced after pandas 2.3 upgrade lands)
**Status:** design approved, awaiting implementation plan

## Goal

Bring the docling ecosystem to the latest compatible coordinated set, pick up upstream features, and clear the path for pandas 3.0 (docling 2.90 allows `pandas>=2.1.4,<4.0.0`).

## Background

The docling family (docling, docling-core, docling-parse, docling-ibm-models, langchain-docling) is released as a loosely-coordinated set where `docling` pins floors on its siblings. Bumping one forces the others. Current state:

| Package | Installed | Latest | Notes |
|---|---|---|---|
| docling | 2.70.0 | 2.90.0 | 20 minor behind |
| docling-core | 2.60.1 | 2.74.0 | 3.0.0 exists but blocked (see below) |
| docling-parse | 4.7.3 | 5.9.0 | **major** — forced by docling 2.90 |
| docling-ibm-models | 3.12.0 | 3.13.0 | forced by docling 2.90 |
| langchain-docling | 1.1.0 | 2.0.0 | 2.0 blocked (see below) |

**Blockers:**
- **docling-core 3.0.0**: docling 2.x pins `docling-core<3.0.0`. Dead end until docling 3.x exists.
- **langchain-docling 2.0.0**: requires `langchain-core~=1.0`. We use `langchain-core>=0.3.81,<1.0.0`. Bumping would cascade into a separate langchain-core 1.x migration project.

## Scope decisions

| Decision | Chosen |
|---|---|
| Trigger | Latest features + pandas 3.0 forward compatibility |
| Packages | docling family (5) + OCR in the `[docling]` extra |
| Skipped | torch/torchvision (pyproject note re: altk), tesserocr/ocrmac (already latest), docling-core 3.0 (blocked), langchain-docling 2.0 (blocked) |
| rapidocr modernization | Swap legacy `rapidocr-onnxruntime` 1.x → `rapidocr` 3.x |
| API-break approach | Hybrid — release-notes audit + code survey, then bump, then verify |
| Verification | Add smoke tests for the 4 docling components before bumping |
| Timing | Sequential — after pandas 2.3 upgrade lands |
| Pin style | Tight ranges with `<next-major` caps (mirrors pandas decision) |
| Transitive conflicts | Same policy as pandas — stop and report if `uv lock` blocks |

## Out of scope

- docling-core 3.0 (blocked by docling 2.x)
- langchain-docling 2.0 (requires langchain-core 1.x migration)
- torch / torchvision
- tesserocr / ocrmac (already at latest)
- pandas 3.0 (separate effort)

## Pin changes

### `src/backend/base/pyproject.toml` `[docling]` extra
| From | To |
|---|---|
| `docling-core>=2.36.1,<3.0.0` | `docling-core>=2.74,<3.0.0` |
| `docling>=2.36.1,<3.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'` | `docling>=2.90,<3.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'` |

### top-level `pyproject.toml` `[docling]` extra
| From | To |
|---|---|
| `langchain-docling>=1.1.0` | `langchain-docling>=1.1,<2.0` |
| `rapidocr-onnxruntime>=1.4.4` | `rapidocr>=3.7,<4.0` |
| `tesserocr>=2.8.0` | unchanged |
| `ocrmac>=1.0.0; sys_platform == 'darwin'` | unchanged |
| `torch>=2.0.0` | unchanged |
| `torchvision>=0.15.0` | unchanged |

### Transitive (no declaration needed)
- docling-parse 4.7.3 → 5.9.0 (major, forced by docling 2.90)
- docling-ibm-models 3.12.0 → 3.13.0 (forced by docling 2.90)

### Lockfile
`uv.lock` regenerated via `uv lock`.

## Code usage surface

Six source files use docling directly:

- `src/lfx/src/lfx/base/data/docling_utils.py` — shared helpers used by the 4 components
- `src/lfx/src/lfx/components/docling/chunk_docling_document.py`
- `src/lfx/src/lfx/components/docling/docling_inline.py`
- `src/lfx/src/lfx/components/docling/docling_remote.py`
- `src/lfx/src/lfx/components/docling/export_docling_document.py`
- `src/lfx/src/lfx/components/files_and_knowledge/file.py`

Existing test coverage:
- `src/lfx/tests/unit/base/data/test_docling_utils.py` — utils coverage
- `src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py` — tests `update_build_config` UI-field-visibility logic only; does **not** exercise docling's chunking API. Would not catch a functional regression from the bump.

The other 3 components (inline, remote, export) have **no tests at all**. Phase 2 addresses both gaps: new smoke tests must exercise the actual docling API paths, not just UI config logic.

## Phase 1 — release-notes audit + code survey

Read-then-grep pass, fixed target list, no mid-session expansion.

**Read:**
1. docling 2.70 → 2.90 CHANGELOG — list Breaking / Deprecated / Renamed items
2. docling-parse 4.x → 5.x release notes (major — highest risk)
3. docling-core 2.60 → 2.74 CHANGELOG, paying attention to `DoclingDocument` and chunking APIs

**Verify:**
4. langchain-docling 1.1.0 still resolves cleanly once `<2.0` cap is added
5. Any direct `rapidocr_onnxruntime` imports in our 6 files need replacing with `rapidocr` (docling likely invokes OCR through config, not direct import — verify)

**Triage rule:**
- API renamed or signature changed → fix in place now
- API deprecated but still works → leave, add to follow-up list
- API removed → must fix now

**Exit:** per-file list of fixes (or "no changes needed") with confidence level.

## Phase 2 — smoke tests (baseline at 2.70)

New test directory: `src/lfx/tests/unit/components/docling/`. Four new test files, one per component. These are complementary to the existing UI-config test in `src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py`, which we leave untouched.

| Test file | Coverage target |
|---|---|
| `test_chunk_docling_document.py` | `ChunkDoclingDocumentComponent` — chunks a tiny synthetic DoclingDocument; asserts non-empty chunks with expected keys |
| `test_docling_inline.py` | `DoclingInlineComponent` — runs a small fixture (hardcoded-path PDF or HTML); asserts non-empty DoclingDocument returned |
| `test_docling_remote.py` | `DoclingRemoteComponent` — mocked HTTP call; asserts request payload and response-shape handling |
| `test_export_docling_document.py` | `ExportDoclingDocumentComponent` — export a tiny DoclingDocument to each supported format; asserts non-empty output |

**Rule:** tests are written on the current pandas-2.3 / docling-2.70 baseline and **must pass there first**. This is what defines "works" before the bump.

## Phase 3 — bump + verify

1. Apply pin changes (backend + top-level pyprojects).
2. `uv lock`. Conflict → stop and report per transitive-dep policy.
3. `uv sync --all-extras --dev`.
4. Confirm installed versions:
   - `docling==2.90.x`
   - `docling-core==2.74.x`
   - `docling-parse==5.x`
   - `docling-ibm-models==3.13.x`
   - `langchain-docling==1.1.x`
   - `rapidocr==3.x` (installed)
   - `rapidocr-onnxruntime` not present (removed)
5. Run new smoke tests (Phase 2) — all must pass.
6. Run `src/lfx/tests/unit/base/data/test_docling_utils.py` — must pass.
7. Run full backend + lfx unit suites as final gate.
8. Any failure: debug, fix, re-run. Meaningful refactoring → escalate.

**Exit condition:** smoke tests + docling_utils test + full unit suites green.

## Rollback

Work lives on a dedicated worktree branch. `git restore` reverts pyproject/lock. Per user policy, no commits without explicit permission — rollback surface is small.

## Deliverables

1. Edited `pyproject.toml` files (2).
2. Regenerated `uv.lock`.
3. Phase 1 code fixes (if any).
4. 4 new smoke test files.
5. Final report: audit findings, API changes absorbed, deferred follow-ups.
6. No commits unless explicitly requested.

## Follow-ups (not in this spec)

- **langchain-core 1.x migration** — required before langchain-docling 2.0.0 can be picked up; scope likely touches many other langchain packages.
- **docling-core 3.0** — available once docling 3.x releases and we pick that up.
- **torch / torchvision bump** — deferred; evaluate if altk-compatibility note becomes obsolete.
