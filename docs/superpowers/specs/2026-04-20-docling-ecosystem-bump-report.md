# Docling ecosystem bump — final report

**Date:** 2026-04-20
**Branch:** `docling-ecosystem-bump` (worktree at `/Users/brycedeneen/dev/langflow-docling-bump`, based on `platform-multi-tenant`)
**Spec:** [2026-04-20-docling-ecosystem-bump-design.md](./2026-04-20-docling-ecosystem-bump-design.md)
**Plan:** [2026-04-20-docling-ecosystem-bump.md](../plans/2026-04-20-docling-ecosystem-bump.md)
**Status:** complete — uncommitted, awaiting user commit approval

## Outcome

- Full docling family bumped to the latest 2.x coordinated set
- Legacy `rapidocr-onnxruntime` 1.x replaced by `rapidocr` 3.x
- docling entry removed from the pandas-3 override comment (docling 2.90 natively supports pandas <4.0)
- Redundant `test_pandas_3_overrides_docling.py` probe deleted
- 4 new component smoke tests added (12 tests total) — pass on both 2.70 baseline and 2.90 target
- One new override introduced (`tree-sitter>=0.25,<0.27`) with a matching smoke probe
- lfx unit suite: zero docling-induced regressions; 35 failures all match pre-existing baseline

## Version changes

| Package | Before | After |
|---|---|---|
| docling | 2.70.0 | **2.90.0** |
| docling-core | 2.60.1 | **2.74.0** |
| docling-parse | 4.7.3 | **5.9.0** (major) |
| docling-ibm-models | 3.12.0 | **3.13.0** |
| langchain-docling | 1.1.0 | 1.1.0 (capped `<2.0`) |
| rapidocr-onnxruntime | 1.4.4 (direct) | **removed** |
| rapidocr | 3.7.0 (transitive) | **3.8.1** (direct) |
| tree-sitter | 0.23.x | **0.25.2** (via new override) |

## Pin changes applied

| File | Change |
|---|---|
| `src/backend/base/pyproject.toml` | `docling-core>=2.36.1,<3.0.0` → `docling-core>=2.74,<3.0.0` |
| `src/backend/base/pyproject.toml` | `docling>=2.36.1,<3.0.0; ...` → `docling>=2.90,<3.0.0; ...` |
| `pyproject.toml` | `langchain-docling>=1.1.0` → `langchain-docling>=1.1,<2.0` |
| `pyproject.toml` | `rapidocr-onnxruntime>=1.4.4` → `rapidocr>=3.8,<4.0` |
| `pyproject.toml` `[tool.uv].override-dependencies` | removed `docling (<3.0)` comment line; added `tree-sitter>=0.25,<0.27` override + explanatory comment |
| `uv.lock` | regenerated |

## Phase 1 audit findings

Zero code changes required. All six consumer files cleared the audit:

- `src/lfx/src/lfx/base/data/docling_utils.py` — no changes needed
- `src/lfx/src/lfx/components/docling/chunk_docling_document.py` — no changes needed
- `src/lfx/src/lfx/components/docling/docling_inline.py` — no changes needed
- `src/lfx/src/lfx/components/docling/docling_remote.py` — no changes needed
- `src/lfx/src/lfx/components/docling/export_docling_document.py` — no changes needed
- `src/lfx/src/lfx/components/files_and_knowledge/file.py` — no changes needed

**Why it was clean:**
- docling 2.70 → 2.90: only breaking change was dropping Python 3.9 support (not our floor)
- docling-core 2.60 → 2.74: zero breaking changes; all additions were optional params
- docling-parse 4 → 5: breaking change in the legacy v1 direct-class API, which our code never imports
- rapidocr 3.x: we invoke OCR through docling's `get_ocr_factory().create_options(kind="rapidocr")` — string-keyed factory, no direct import

## Resolver conflict resolved

`uv lock` initially blocked on a tree-sitter version split:

- `docling-core 2.74[chunking]` (required by docling 2.90) needs `tree-sitter>=0.25,<0.27`
- `astra-assistants[tools]==2.5.5` (latest; pinned `<3.0.0` in backend pyproject and used by 7 datastax component files) hard-caps `tree-sitter<0.24`

The break point is `docling-core 2.65`, below which `[chunking]` still accepted tree-sitter <0.25. Since docling 2.90 requires docling-core ≥2.73, we cannot stay below the break.

**Resolution:** added `tree-sitter>=0.25,<0.27` to `[tool.uv].override-dependencies`. Runtime inspection of `astra_assistants.tools.structured_code.{util,indent}` confirmed it already uses the modern `Language(tspython.language())` / `Parser(lang)` API supported in both 0.23 and 0.25, so the override is expected to be a resolver lie with no behavioral impact. A smoke probe at `src/backend/tests/unit/integration_smoke/test_tree_sitter_override_astra_assistants.py` instantiates the parser and imports the two astra modules to catch runtime breakage.

## New tests

New directory `src/lfx/tests/unit/components/docling/` with one file per component plus a package marker:

| File | Tests | Pass on 2.70 | Pass on 2.90 |
|---|---|---|---|
| `test_export_docling_document.py` | 5 (4 formats + dataframe) | ✅ | ✅ |
| `test_chunk_docling_document.py` | 2 (hierarchical + hybrid/OpenAI) | ✅ | ✅ |
| `test_docling_remote.py` | 2 (mocked httpx) | ✅ | ✅ |
| `test_docling_inline.py` | 3 (mocked worker) | ✅ | ✅ |

New smoke probe:

| File | Tests | Result |
|---|---|---|
| `test_tree_sitter_override_astra_assistants.py` | 2 (API check + import check) | ✅ |

Total new tests: **14 passing**.

Design notes:
- HuggingFace tokenizer path in chunker test is skipped (network / model-weight cost) — the OpenAI path exercises the same chunker code with just tiktoken locally
- Inline smoke mocks `docling_worker` at the module boundary (a real run would take 15–20 min on cold cache)
- Remote smoke mocks `httpx.Client` (no live Docling Serve instance required)

## Verification

- 12/12 docling component smoke tests green on both 2.70 baseline and 2.90 target
- 2/2 tree-sitter override smoke probes green
- Existing `src/lfx/tests/unit/base/data/test_docling_utils.py` green
- Existing `src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py` (UI-config test) green
- lfx unit suite: 2053 passed, 35 failed, 8 skipped — all 35 failures match the pre-existing baseline documented at `docs/superpowers/specs/2026-04-20-preexisting-failures-triage.md`
- `rapidocr_onnxruntime` no longer importable

## Deferred follow-ups

- **langchain-core 1.x migration** — still required before `langchain-docling 2.0` can be picked up; cascades into every other langchain package we pin
- **docling-core 3.0** — blocked by docling 2.x cap; revisit when docling 3.x releases
- **torch / torchvision bump** — not revisited; altk-compat note still stands
- **astra-assistants upgrade beyond 2.5.5** — no 3.x available as of 2026-04-20; if one lands, revisit the tree-sitter override and consider removing it

## New failures

None.
