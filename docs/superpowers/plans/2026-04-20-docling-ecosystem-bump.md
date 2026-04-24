# Docling Ecosystem Coordinated Bump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the docling family to a coordinated latest-compatible set (docling 2.90, docling-core 2.74, docling-parse 5.x, docling-ibm-models 3.13, langchain-docling capped at 1.x) and swap legacy `rapidocr-onnxruntime` for `rapidocr` 3.x, ending with green smoke tests + full unit suites and the pandas-3 override's docling entry removed.

**Architecture:** Three phases — (1) release-notes audit + code survey against the six files that touch docling, producing a fixed per-file triage list; (2) write four smoke tests *on the current 2.70 baseline* so they define "works" pre-bump; (3) apply pin changes, `uv lock` + `uv sync --all-extras --dev`, rerun smoke tests + docling_utils tests + full unit suites. Each phase ends with an explicit commit checkpoint.

**Tech Stack:** uv (package manager), pytest, docling 2.90, docling-core 2.74, docling-parse 5.x, rapidocr 3.x.

**Spec:** `docs/superpowers/specs/2026-04-20-docling-ecosystem-bump-design.md`

---

## Global Ground Rules

Read these before starting any task.

- **Branch:** Per project memory, `platform-multi-tenant` is the effective main; however the spec calls for a dedicated worktree. Create a new worktree branched off `platform-multi-tenant` (see Task 0). No upstream push. No PRs to langflow-ai/langflow.
- **Prerequisite:** pandas 3.0 is already committed on `platform-multi-tenant` (commit `6c295a70dc`, report at `docs/superpowers/specs/2026-04-20-pandas-3.0-upgrade-report.md`). Docling sits behind a `pandas>=3.0,<4.0` override — this plan removes that override's docling entry since docling 2.90 natively supports pandas <4.0. The comparison baseline for unit-suite regressions is the pandas-3.0 report's known-failure list, not the 2.3 one.
- **Commit policy:** User requires explicit permission before every `git commit`. Every commit task in this plan says "pause and ask user to commit" — follow that literally. If the user declines, continue the next task with the change left uncommitted. Never commit silently.
- **lfx tests:** Require `LFX_TEST_ALLOW_LANGFLOW=1` when run from the repo-level venv (see `reference_lfx_test_env.md` in user memory).
- **Transitive conflict policy:** If `uv lock` fails because a non-docling transitive dep caps one of the target versions, **stop and report** per the pandas-upgrade precedent. Do not patch upstream packages or add silent workarounds.
- **Scope discipline — blockers stay blocked:** Do not bump `docling-core` to 3.0 (blocked by docling 2.x) or `langchain-docling` to 2.0 (requires langchain-core 1.x migration). These are listed as out-of-scope in the spec.
- **Abort condition:** If Phase 1 uncovers more than ~3 breaking API removals requiring non-trivial refactors, stop and report — the spec assumes shallow changes.

---

## File Structure

**Pyproject edits (2 files):**
- `src/backend/base/pyproject.toml` — bump `[project.optional-dependencies].docling` floors
- `pyproject.toml` — bump `[project.optional-dependencies].docling` (rapidocr swap, langchain-docling cap) and edit the `[tool.uv].override-dependencies` comment

**Lockfile (1 file):**
- `uv.lock` — regenerated via `uv lock`

**New test files (4, all under `src/lfx/tests/unit/components/docling/`):**
- `src/lfx/tests/unit/components/docling/__init__.py` — empty package marker
- `src/lfx/tests/unit/components/docling/test_chunk_docling_document.py` — exercises `ChunkDoclingDocumentComponent.chunk_documents` against a tiny synthetic `DoclingDocument`
- `src/lfx/tests/unit/components/docling/test_docling_inline.py` — exercises `DoclingInlineComponent.process_files` with mocked `docling_worker` (so we don't pay the 15–20 min model load in CI)
- `src/lfx/tests/unit/components/docling/test_docling_remote.py` — exercises `DoclingRemoteComponent.process_files` against a mocked `httpx.Client`
- `src/lfx/tests/unit/components/docling/test_export_docling_document.py` — exercises `ExportDoclingDocumentComponent.export_document` across all four formats

**Code changes (potential, determined by Phase 1 audit):**
- `src/lfx/src/lfx/base/data/docling_utils.py`
- `src/lfx/src/lfx/components/docling/chunk_docling_document.py`
- `src/lfx/src/lfx/components/docling/docling_inline.py`
- `src/lfx/src/lfx/components/docling/docling_remote.py`
- `src/lfx/src/lfx/components/docling/export_docling_document.py`
- `src/lfx/src/lfx/components/files_and_knowledge/file.py`

If Phase 1 finds "no changes needed" for a file, it stays untouched.

---

## Task 0: Create the worktree and verify prerequisite

**Files:**
- Read: `docs/superpowers/specs/2026-04-20-pandas-3.0-upgrade-report.md`
- No edits in this task.

- [x] **Step 1: Verify pandas 3.0 baseline is committed**

Run from repo root:

```bash
git -C /Users/brycedeneen/dev/langflow log --oneline -n 30 platform-multi-tenant -- src/backend/base/pyproject.toml src/lfx/pyproject.toml pyproject.toml uv.lock
```

Expected: commit `6c295a70dc` ("bump pandas 2.3 -> 3.0, raise Python floor to 3.11, add dep smoke probes") reachable from `platform-multi-tenant`.

If that commit is not present, **stop and ask the user**.

- [x] **Step 2: Create dedicated worktree**

```bash
git -C /Users/brycedeneen/dev/langflow worktree add -b docling-ecosystem-bump ../langflow-docling-bump platform-multi-tenant
```

Expected: worktree created at `/Users/brycedeneen/dev/langflow-docling-bump` on branch `docling-ecosystem-bump`.

All remaining tasks run inside that worktree. Every later `pwd`-sensitive command in this plan assumes you `cd` into the worktree first — or use `git -C <worktree> ...` and absolute paths.

- [x] **Step 3: Confirm installed docling baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras python -c "import docling, docling_core, docling_parse, docling_ibm_models, langchain_docling; print(docling.__version__, docling_core.__version__, docling_parse.__version__, docling_ibm_models.__version__, langchain_docling.__version__)"
```

Expected: `2.70.x 2.60.x 4.7.x 3.12.x 1.1.x` (or close to those — exact patch versions may drift).

Record the exact versions in a scratch note — they are the "before" state for the final report.

- [x] **Step 4: Confirm rapidocr-onnxruntime baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras python -c "import rapidocr_onnxruntime; print(rapidocr_onnxruntime.__version__)"
```

Expected: `1.4.x` or similar 1.x version present.

Also run:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras python -c "import rapidocr" 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'rapidocr'` (the new package is not yet installed).

---

## Task 1: Phase 1 audit — docling 2.70 → 2.90 release notes

**Files:**
- Read-only: external release notes via web + source grep
- Create: scratch notes (not committed) tracking findings

The goal of Phase 1 is to produce a **fixed per-file triage list** before touching pins. No code edits in this phase.

- [x] **Step 1: Fetch docling CHANGELOG 2.70 → 2.90**

Use WebFetch against `https://github.com/docling-project/docling/blob/main/CHANGELOG.md` (or the raw version). Extract every `Breaking`, `Removed`, `Deprecated`, `Renamed` entry between v2.70.0 and v2.90.0 inclusive.

Write findings to a scratch file (not committed):

```bash
mkdir -p /tmp/docling-audit && touch /tmp/docling-audit/docling-2.70-to-2.90.md
```

Populate it with bullet points per breaking/deprecated/renamed item, including the version and the affected symbol.

- [x] **Step 2: Fetch docling-core CHANGELOG 2.60 → 2.74**

Same process against `https://github.com/docling-project/docling-core/blob/main/CHANGELOG.md`. Record into `/tmp/docling-audit/docling-core-2.60-to-2.74.md`.

Focus: `DoclingDocument`, chunking (`HybridChunker`, `HierarchicalChunker`, `HuggingFaceTokenizer`, `OpenAITokenizer`), and `ImageRefMode`, since those are the symbols used in our code.

- [x] **Step 3: Fetch docling-parse 4.x → 5.x notes**

Against `https://github.com/docling-project/docling-parse/blob/main/CHANGELOG.md`. This is the **major bump** (4 → 5) so has the highest risk. Record into `/tmp/docling-audit/docling-parse-4-to-5.md`.

Docling-parse is a transitive — our code doesn't import it directly. The audit here is for understanding what docling 2.90 is asking for, not direct code fixes.

- [x] **Step 4: Fetch langchain-docling 1.x notes**

Against `https://github.com/langchain-ai/langchain-docling/blob/main/CHANGELOG.md`. We are capping at `<2.0`, so only confirm 1.1.x remains the latest 1.x tag.

- [x] **Step 5: Fetch rapidocr 3.x migration notes**

Against `https://github.com/RapidAI/RapidOCR` and `https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/`. The legacy import is `rapidocr_onnxruntime`; the new package is `rapidocr` with a different top-level API. Confirm:
  - whether docling 2.90 invokes OCR through config (string-keyed factory) or through a direct `rapidocr_onnxruntime` import — our code uses `get_ocr_factory(allow_external_plugins=False).create_options(kind=ocr_engine)` in `docling_utils.py`, which is config-based
  - whether the string key `"rapidocr"` still resolves under docling 2.90 when `rapidocr` 3.x is installed instead of `rapidocr-onnxruntime`

Record findings.

- [x] **Step 6: Grep our six files for direct rapidocr imports**

Use the Grep tool, pattern `rapidocr_onnxruntime|from rapidocr|import rapidocr`, paths:

```
src/lfx/src/lfx/base/data/docling_utils.py
src/lfx/src/lfx/components/docling/chunk_docling_document.py
src/lfx/src/lfx/components/docling/docling_inline.py
src/lfx/src/lfx/components/docling/docling_remote.py
src/lfx/src/lfx/components/docling/export_docling_document.py
src/lfx/src/lfx/components/files_and_knowledge/file.py
```

Expected: **zero** direct imports (based on current inspection, OCR is invoked via docling's factory). If any match surfaces, add it to the per-file triage list as a fix.

- [x] **Step 7: Grep our six files for deprecated docling_core symbols**

Pull the list of `Deprecated` / `Renamed` items from Step 2 and grep each one across the six files. For any match, record:
  - file + line number
  - whether it's still-works-deprecated (leave alone, note for follow-up) or removed-broken (must fix)

- [x] **Step 8: Produce the per-file triage list**

Append to `/tmp/docling-audit/triage.md` one entry per file:

```
# File: <path>
# Status: <no changes needed | fix required | deprecated-note>
# Fixes (if any):
#   - line <N>: <symbol> → <replacement>
#   - ...
```

This is the work plan for Task 3. If Status is "fix required" for more than ~3 files, **stop and report**.

- [x] **Step 9: Pause for review**

Share the triage list with the user. Proceed to Task 2 once acknowledged.

---

## Task 2: Phase 2 smoke tests — test_export_docling_document.py

**Files:**
- Create: `src/lfx/tests/unit/components/docling/__init__.py`
- Create: `src/lfx/tests/unit/components/docling/test_export_docling_document.py`

Export is the purest smoke target: synchronous, no OCR, no worker process, no HTTP. Start here to validate the test plumbing before moving to the heavier components.

- [x] **Step 1: Create package marker**

Write to `src/lfx/tests/unit/components/docling/__init__.py`:

```python
```

(An empty file is correct — matches the pattern of other `__init__.py` files under `src/lfx/tests/unit/components/`.)

- [x] **Step 2: Write the failing test**

Write to `src/lfx/tests/unit/components/docling/test_export_docling_document.py`:

```python
"""Smoke tests for ExportDoclingDocumentComponent."""

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.components.docling.export_docling_document import ExportDoclingDocumentComponent
from lfx.schema import Data


def _tiny_doc() -> DoclingDocument:
    return DoclingDocument(name="smoke_doc")


class TestExportDoclingDocumentSmoke:
    @pytest.mark.parametrize("export_format", ["Markdown", "HTML", "Plaintext", "DocTags"])
    def test_export_each_format_returns_non_empty_data(self, export_format):
        component = ExportDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.export_format = export_format
        component.image_mode = "placeholder"
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""

        results = component.export_document()

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], Data)
        # Empty DoclingDocument renders an empty string in some formats (Plaintext especially);
        # the smoke assertion is that `.text` is a `str` and the call did not raise.
        assert isinstance(results[0].text, str)

    def test_export_dataframe_wraps_export_document(self):
        component = ExportDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.export_format = "Markdown"
        component.image_mode = "placeholder"
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""

        df = component.as_dataframe()

        assert len(df) == 1
```

- [x] **Step 3: Run test against current (2.70) baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/test_export_docling_document.py -v
```

Expected: **all 5 parametrized cases PASS**. If any fail on the 2.70 baseline, the test is wrong — fix the test (not the component) before proceeding.

- [x] **Step 4: Commit**

Pause and ask the user: "Phase 2 test for export is green on baseline. OK to commit?"

If yes:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add src/lfx/tests/unit/components/docling/__init__.py src/lfx/tests/unit/components/docling/test_export_docling_document.py && git commit -m "test(docling): smoke test for ExportDoclingDocumentComponent"
```

---

## Task 3: Phase 2 smoke tests — test_chunk_docling_document.py

**Files:**
- Create: `src/lfx/tests/unit/components/docling/test_chunk_docling_document.py`

- [x] **Step 1: Write the failing test**

Write to `src/lfx/tests/unit/components/docling/test_chunk_docling_document.py`:

```python
"""Smoke tests for ChunkDoclingDocumentComponent.

The existing test file at
src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py
covers only the UI-config show/hide logic. This file exercises the actual
chunking pipeline end-to-end against a tiny synthetic DoclingDocument.
"""

import pytest

pytest.importorskip("tiktoken")
pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.components.docling.chunk_docling_document import ChunkDoclingDocumentComponent
from lfx.schema import Data


def _tiny_doc() -> DoclingDocument:
    return DoclingDocument(name="smoke_doc")


class TestChunkDoclingDocumentSmoke:
    def test_hierarchical_chunker_returns_dataframe(self):
        component = ChunkDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.chunker = "HierarchicalChunker"
        # HybridChunker-only fields, set to defaults (unused for HierarchicalChunker):
        component.provider = "Hugging Face"
        component.hf_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        component.openai_model_name = "gpt-4o"
        component.max_tokens = None
        component.merge_peers = True
        component.always_emit_headings = False

        df = component.chunk_documents()

        # An empty DoclingDocument yields 0 chunks; the smoke check is that
        # the method completes and returns a DataFrame.
        assert hasattr(df, "columns")

    def test_hybrid_chunker_openai_provider_returns_dataframe(self):
        """OpenAI tokenizer path requires tiktoken but not network — good smoke coverage."""
        component = ChunkDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.chunker = "HybridChunker"
        component.provider = "OpenAI"
        component.hf_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        component.openai_model_name = "gpt-4o"
        component.max_tokens = None
        component.merge_peers = True
        component.always_emit_headings = False

        df = component.chunk_documents()

        assert hasattr(df, "columns")
```

Note: the Hugging Face path is intentionally excluded from this smoke test because `HuggingFaceTokenizer.from_pretrained(...)` downloads model weights, which is unacceptable for a unit test. The OpenAI path exercises the same upstream chunking code and only needs `tiktoken` locally.

- [x] **Step 2: Run test against current (2.70) baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/test_chunk_docling_document.py -v
```

Expected: **both tests PASS** on 2.70 baseline.

- [x] **Step 3: Commit**

Pause and ask the user to commit.

If yes:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add src/lfx/tests/unit/components/docling/test_chunk_docling_document.py && git commit -m "test(docling): smoke test for ChunkDoclingDocumentComponent"
```

---

## Task 4: Phase 2 smoke tests — test_docling_remote.py

**Files:**
- Create: `src/lfx/tests/unit/components/docling/test_docling_remote.py`

- [x] **Step 1: Write the failing test**

Write to `src/lfx/tests/unit/components/docling/test_docling_remote.py`:

```python
"""Smoke tests for DoclingRemoteComponent — mocked Docling Serve HTTP."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.base.data import BaseFileComponent
from lfx.components.docling.docling_remote import DoclingRemoteComponent


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestDoclingRemoteSmoke:
    def test_process_files_converts_file_via_mocked_http(self, tmp_path):
        # Arrange
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = DoclingRemoteComponent()
        component.api_url = "http://docling-serve.example:5001"
        component.max_concurrency = 1
        component.max_poll_timeout = 60.0
        component.api_headers = None
        component.docling_serve_opts = None

        # DoclingDocument payload that the component will validate
        doc_payload = DoclingDocument(name="smoke_doc").model_dump(mode="json")

        # Fake httpx.Client — post → task; get poll → success; get result → doc
        fake_client = MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        fake_client.post.return_value = _FakeResponse(200, {"task_id": "t1", "task_status": "pending"})
        fake_client.get.side_effect = [
            _FakeResponse(200, {"task_id": "t1", "task_status": "success"}),
            _FakeResponse(200, {"document": {"json_content": doc_payload}}),
        ]

        file_list = [BaseFileComponent.BaseFile(path=pdf_path, file=None, data=None)]

        # Act
        with patch("lfx.components.docling.docling_remote.httpx.Client", return_value=fake_client), \
             patch("lfx.components.docling.docling_remote.time.sleep"):
            result = component.process_files(file_list)

        # Assert — one converted file came back; its payload base64 matches the fixture.
        assert len(result) == 1
        posted_payload = fake_client.post.call_args.kwargs["json"]
        assert posted_payload["sources"][0]["filename"] == "smoke.pdf"
        assert base64.b64decode(posted_payload["sources"][0]["base64_string"]) == b"%PDF-1.4\n%mocked\n"

    def test_process_files_returns_none_when_json_content_missing(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = DoclingRemoteComponent()
        component.api_url = "http://docling-serve.example:5001"
        component.max_concurrency = 1
        component.max_poll_timeout = 60.0
        component.api_headers = None
        component.docling_serve_opts = None

        fake_client = MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        fake_client.post.return_value = _FakeResponse(200, {"task_id": "t1", "task_status": "pending"})
        fake_client.get.side_effect = [
            _FakeResponse(200, {"task_id": "t1", "task_status": "success"}),
            _FakeResponse(200, {"document": {"json_content": None}}),
        ]

        file_list = [BaseFileComponent.BaseFile(path=pdf_path, file=None, data=None)]

        with patch("lfx.components.docling.docling_remote.httpx.Client", return_value=fake_client), \
             patch("lfx.components.docling.docling_remote.time.sleep"):
            result = component.process_files(file_list)

        # The component surfaces this as a None entry in the rollup — the test verifies
        # the method completes without raising.
        assert isinstance(result, list)
```

Note on `BaseFileComponent.BaseFile` construction: if the real dataclass has different required fields than the shape shown above, the Phase 1 audit (Task 1 Step 6 grep area) will surface them — fix the test's construction to match before running.

- [x] **Step 2: Run test against current (2.70) baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/test_docling_remote.py -v
```

Expected: **both tests PASS**.

If the `BaseFile` construction fails (wrong kwargs), inspect `src/lfx/src/lfx/base/data/__init__.py` (or wherever `BaseFileComponent.BaseFile` is defined) and adjust the test — do not skip this step.

- [x] **Step 3: Commit**

Pause and ask the user to commit.

If yes:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add src/lfx/tests/unit/components/docling/test_docling_remote.py && git commit -m "test(docling): smoke test for DoclingRemoteComponent with mocked httpx"
```

---

## Task 5: Phase 2 smoke tests — test_docling_inline.py

**Files:**
- Create: `src/lfx/tests/unit/components/docling/test_docling_inline.py`

The inline component delegates to `docling_worker` running in a thread, which internally builds a `DocumentConverter`. Building a real converter takes 15–20 minutes on a cold cache — unacceptable for a unit test. We therefore mock `docling_worker` at the module boundary and verify the component's orchestration (thread start, queue drain, error mapping, rollup).

- [x] **Step 1: Write the failing test**

Write to `src/lfx/tests/unit/components/docling/test_docling_inline.py`:

```python
"""Smoke tests for DoclingInlineComponent — mocked docling_worker to avoid 15+ min model loads."""

from unittest.mock import patch

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.base.data import BaseFileComponent
from lfx.components.docling.docling_inline import DoclingInlineComponent


def _make_component() -> DoclingInlineComponent:
    component = DoclingInlineComponent()
    component.pipeline = "standard"
    component.ocr_engine = "None"
    component.do_picture_classification = False
    component.pic_desc_llm = None
    component.pic_desc_prompt = "unused"
    return component


class TestDoclingInlineSmoke:
    def test_process_files_rollup_maps_worker_results(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = _make_component()
        file_list = [BaseFileComponent.BaseFile(path=pdf_path, file=None, data=None)]

        synthetic = DoclingDocument(name="smoke_doc")

        def fake_worker(*, queue, file_paths, **kwargs):  # noqa: ARG001
            queue.put(
                [
                    {
                        "document": synthetic,
                        "file_path": str(pdf_path),
                        "status": "SUCCESS",
                    }
                ]
            )

        with patch("lfx.components.docling.docling_inline.docling_worker", side_effect=fake_worker):
            result = component.process_files(file_list)

        assert len(result) == 1

    def test_process_files_raises_on_dependency_error(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = _make_component()
        file_list = [BaseFileComponent.BaseFile(path=pdf_path, file=None, data=None)]

        def fake_worker(*, queue, **kwargs):  # noqa: ARG001
            queue.put(
                {
                    "error": "tesserocr is not correctly installed. pip install tesserocr",
                    "error_type": "dependency_error",
                    "dependency_name": "tesserocr",
                }
            )

        with patch("lfx.components.docling.docling_inline.docling_worker", side_effect=fake_worker):
            with pytest.raises(ImportError, match="tesserocr"):
                component.process_files(file_list)

    def test_process_files_empty_list_skips_worker(self):
        component = _make_component()

        with patch("lfx.components.docling.docling_inline.docling_worker") as worker:
            result = component.process_files([])

        assert result == []
        worker.assert_not_called()
```

- [x] **Step 2: Run test against current (2.70) baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/test_docling_inline.py -v
```

Expected: **all 3 tests PASS**. The third test (empty list) is the cheapest assertion that proves the top-of-function short-circuit works without touching docling imports.

- [x] **Step 3: Commit**

Pause and ask the user to commit.

If yes:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add src/lfx/tests/unit/components/docling/test_docling_inline.py && git commit -m "test(docling): smoke test for DoclingInlineComponent with mocked worker"
```

---

## Task 6: Apply Phase 1 code fixes (if any)

**Files:**
- Modify: whichever files the Task 1 triage list marked `fix required`

If the Task 1 triage list had Status `no changes needed` for all six files, **skip this entire task** and proceed directly to Task 7.

- [x] **Step 1: Apply fixes per triage**

For each file in the triage list with Status `fix required`, apply the per-line replacements recorded there. Use the Edit tool, one edit per symbol.

Do not bundle unrelated refactors. A bug-fix plan is not the place to rename variables or restructure modules.

- [x] **Step 2: Re-run the 4 Phase 2 smoke tests on 2.70 baseline**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/ -v
```

Expected: **all tests still PASS** (the triage fixes should be forward-compatible edits that work under both 2.70 and 2.90; if a fix is 2.90-only, defer it to Task 8).

- [x] **Step 3: Commit**

Pause and ask the user to commit the preemptive code fixes.

If yes:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add <files> && git commit -m "refactor(docling): absorb API changes ahead of 2.90 bump"
```

---

## Task 7: Apply pin changes — backend pyproject

**Files:**
- Modify: `src/backend/base/pyproject.toml` (the `[project.optional-dependencies].docling` block, currently around lines 329–332)

- [x] **Step 1: Edit the docling block**

Replace:

```toml
docling = [
    "docling-core>=2.36.1,<3.0.0",
    "docling>=2.36.1,<3.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'",
]
```

With:

```toml
docling = [
    "docling-core>=2.74,<3.0.0",
    "docling>=2.90,<3.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'",
]
```

Leave the surrounding `easyocr = [...]` line and the `langflow-base[docling]` reference in the `complete` block untouched.

- [x] **Step 2: Verify edit**

Use the Grep tool, pattern `docling-core|docling>=`, path `src/backend/base/pyproject.toml`, to confirm only the two intended lines changed.

---

## Task 8: Apply pin changes — top-level pyproject

**Files:**
- Modify: `pyproject.toml` (lines ~102–112 and ~149–160)

- [x] **Step 1: Edit the docling optional-dependencies block**

Replace:

```toml
docling = [
    "langchain-docling>=1.1.0",
    "tesserocr>=2.8.0",
    "rapidocr-onnxruntime>=1.4.4",
    "ocrmac>=1.0.0; sys_platform == 'darwin'",
    # CPU-only PyTorch required for docling features
    # Loose version ranges intentionally used to avoid conflicts with transitive dependencies (e.g., altk)
    "torch>=2.0.0",
    "torchvision>=0.15.0",
]
```

With:

```toml
docling = [
    "langchain-docling>=1.1,<2.0",
    "tesserocr>=2.8.0",
    "rapidocr>=3.8,<4.0",
    "ocrmac>=1.0.0; sys_platform == 'darwin'",
    # CPU-only PyTorch required for docling features
    # Loose version ranges intentionally used to avoid conflicts with transitive dependencies (e.g., altk)
    "torch>=2.0.0",
    "torchvision>=0.15.0",
]
```

Changes: `langchain-docling` gets a `<2.0` cap, `rapidocr-onnxruntime>=1.4.4` becomes `rapidocr>=3.8,<4.0`.

- [x] **Step 2: Update the override-dependencies comment**

In `pyproject.toml` around lines 150–160, find:

```toml
[tool.uv]
override-dependencies = [
    # temporary force a newer python-pptx
    "python-pptx>=1.0.2",
    # Force pandas 3.0+ despite these consumers pinning lower:
    #   - ibm-watsonx-ai (<2.4)      — deploy target doesn't include watsonx; see project memory
    #   - docling (<3.0)             — ecosystem bump parked (2026-04-20-docling-ecosystem-bump-design.md)
    #   - cleanlab-tlm (==2.*)       — upstream hasn't released a pandas-3 compatible cut
    # Each has a smoke probe in tests/unit/integration_smoke/test_pandas_3_overrides.py
    # to catch runtime breakage.
    "pandas>=3.0,<4.0",
]
```

Replace with:

```toml
[tool.uv]
override-dependencies = [
    # temporary force a newer python-pptx
    "python-pptx>=1.0.2",
    # Force pandas 3.0+ despite these consumers pinning lower:
    #   - ibm-watsonx-ai (<2.4)      — deploy target doesn't include watsonx; see project memory
    #   - cleanlab-tlm (==2.*)       — upstream hasn't released a pandas-3 compatible cut
    # Each has a smoke probe in tests/unit/integration_smoke/test_pandas_3_overrides.py
    # to catch runtime breakage.
    "pandas>=3.0,<4.0",
]
```

Rationale: docling 2.90 declares `pandas>=2.1.4,<4.0.0`, which already allows pandas 3.0. The override comment's docling entry is now obsolete.

- [x] **Step 3: Verify edits**

Grep `pyproject.toml` for `docling|rapidocr|pandas` and confirm:
  - `rapidocr-onnxruntime` is no longer present
  - `rapidocr>=3.8,<4.0` is present
  - `langchain-docling>=1.1,<2.0` is present
  - The `docling (<3.0)` line inside the pandas override comment is gone
  - The `"pandas>=3.0,<4.0"` override itself remains (still needed for watsonx + cleanlab-tlm)

- [x] **Step 4: Remove the docling-specific pandas-3 smoke probe**

The file `src/backend/tests/unit/integration_smoke/test_pandas_3_overrides_docling.py` exists specifically to catch breakage of the docling override. With docling now at 2.90 which allows `pandas<4.0.0`, the override no longer applies to docling and the probe is redundant.

Delete the file:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git rm src/backend/tests/unit/integration_smoke/test_pandas_3_overrides_docling.py
```

(If the file is untracked on your branch — `git status` shows it as untracked — use `rm` instead.)

---

## Task 9: Regenerate lockfile

**Files:**
- Modify: `uv.lock`

- [x] **Step 1: Regenerate**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv lock
```

Expected: lockfile updates with docling 2.90.x, docling-core 2.74.x, docling-parse 5.x, docling-ibm-models 3.13.x, rapidocr 3.x; `rapidocr-onnxruntime` disappears.

If `uv lock` fails with a resolver error:
  - If the error names a **non-docling** transitive (e.g., some random package caps `docling<2.80`), **stop and report** per the abort rule. Do not add more overrides without the user's sign-off.
  - If the error names `pandas` or another package in the existing override list, the override may need an additional line — check with the user.

- [x] **Step 2: Inspect lock delta**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git diff --stat uv.lock
```

Record the rough size (expected: hundreds of lines — docling-parse's major bump pulls in new wheels across platforms).

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git diff uv.lock | grep -E '^\+name = "(docling|docling-core|docling-parse|docling-ibm-models|langchain-docling|rapidocr|rapidocr-onnxruntime)"' -A 1
```

Confirm the target versions are what the spec asks for.

---

## Task 10: Sync environment and verify installed versions

**Files:** none (runtime verification only).

- [x] **Step 1: Sync**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv sync --all-extras --dev
```

Expected: new wheels fetched for docling, docling-core, docling-parse, docling-ibm-models, rapidocr; `rapidocr-onnxruntime` removed.

- [x] **Step 2: Confirm versions**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras python -c "import docling, docling_core, docling_parse, docling_ibm_models, langchain_docling, rapidocr; print(docling.__version__, docling_core.__version__, docling_parse.__version__, docling_ibm_models.__version__, langchain_docling.__version__, rapidocr.__version__)"
```

Expected output (exact patches may drift):
```
2.90.x 2.74.x 5.x.x 3.13.x 1.1.x 3.7.x (or later)
```

- [x] **Step 3: Confirm rapidocr-onnxruntime is gone**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras python -c "import rapidocr_onnxruntime" 2>&1 | head -3
```

Expected: `ModuleNotFoundError: No module named 'rapidocr_onnxruntime'`.

If the legacy package is still present, inspect `uv.lock` — another extra (not `docling`) may still declare it.

---

## Task 11: Re-run Phase 2 smoke tests on 2.90

**Files:** none.

- [x] **Step 1: Run the four smoke tests**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/components/docling/ -v
```

Expected: **all tests PASS** under docling 2.90.

If a test fails:
  - If the failure is clearly a docling 2.90 API change not caught by Phase 1 audit — fix the component code in place (do not fix the test to hide the regression).
  - If the failure is an OCR-factory change affecting the `"rapidocr"` string key — follow-up fix in `docling_utils.py` (e.g., remap the kind name).
  - Re-run until green.

- [x] **Step 2: Run the existing docling_utils tests**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit/base/data/test_docling_utils.py -v
```

Expected: all tests PASS. These cover the shared `extract_docling_documents` helper across Data / list[Data] / DataFrame inputs.

- [x] **Step 3: Run the existing UI-config test**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras pytest src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py -v
```

Expected: all tests PASS.

---

## Task 12: Run full unit suites as final gate

**Files:** none.

- [x] **Step 1: Backend unit suite**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && uv run --all-extras pytest src/backend/tests/unit -x --timeout 300 2>&1 | tail -80
```

Expected: pass, or the same set of pre-existing failures already documented in the pandas-3.0 upgrade report (`docs/superpowers/specs/2026-04-20-pandas-3.0-upgrade-report.md`). Anything new outside that list is docling-induced and must be investigated.

- [x] **Step 2: lfx unit suite**

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && LFX_TEST_ALLOW_LANGFLOW=1 uv run --all-extras pytest src/lfx/tests/unit -x --timeout 300 2>&1 | tail -80
```

Expected: same rule — no new failures beyond the pandas-3.0 baseline.

- [x] **Step 3: Record deltas**

If any tests fail that were green on the pandas-3.0 baseline, write them to `docs/superpowers/specs/2026-04-20-docling-ecosystem-bump-report.md` under a "New failures" heading with one-line diagnosis per test.

---

## Task 13: Commit bump + final report

**Files:**
- Modify (already edited): `src/backend/base/pyproject.toml`, `pyproject.toml`, `uv.lock`
- Delete (already): `src/backend/tests/unit/integration_smoke/test_pandas_3_overrides_docling.py`
- Create: `docs/superpowers/specs/2026-04-20-docling-ecosystem-bump-report.md`

- [x] **Step 1: Write the final report**

Write to `docs/superpowers/specs/2026-04-20-docling-ecosystem-bump-report.md`:

```markdown
# Docling ecosystem bump — final report

**Date:** <YYYY-MM-DD of completion>
**Branch:** docling-ecosystem-bump
**Spec:** [2026-04-20-docling-ecosystem-bump-design.md](./2026-04-20-docling-ecosystem-bump-design.md)
**Status:** <complete | blocked>

## Outcome

- docling family bumped: <before → after per package>
- `rapidocr-onnxruntime` 1.x → `rapidocr` 3.x swap
- pandas-3 override's docling entry removed (`docling 2.90` accepts pandas <4.0 natively)
- 4 new smoke tests added under `src/lfx/tests/unit/components/docling/`
- docling-specific pandas-3 probe deleted

## Pin changes applied

| File | Change |
|---|---|
| `src/backend/base/pyproject.toml` | `docling-core>=2.36.1,<3.0.0` → `docling-core>=2.74,<3.0.0` |
| `src/backend/base/pyproject.toml` | `docling>=2.36.1,<3.0.0; ...` → `docling>=2.90,<3.0.0; ...` |
| `pyproject.toml` | `langchain-docling>=1.1.0` → `langchain-docling>=1.1,<2.0` |
| `pyproject.toml` | `rapidocr-onnxruntime>=1.4.4` → `rapidocr>=3.8,<4.0` |
| `pyproject.toml` override comment | removed `docling (<3.0)` line |
| `uv.lock` | regenerated |

## Phase 1 audit findings

<paste per-file triage summary from /tmp/docling-audit/triage.md>

## Code changes applied (if any)

<list files + one-line diff summary per file, or "none">

## Deferred follow-ups

- **langchain-core 1.x migration** — still required before `langchain-docling 2.0` can be picked up.
- **docling-core 3.0** — blocked by docling 2.x cap; revisit when docling 3.x lands.
- **torch / torchvision bump** — not revisited in this plan.

## Verification

- 4 smoke tests green on 2.70 baseline AND on 2.90
- `src/lfx/tests/unit/base/data/test_docling_utils.py` green
- Full backend + lfx unit suites: <match baseline | N new failures, see below>

## New failures (if any)

<list per-test one-line diagnosis, or "none">
```

Fill in the bracketed placeholders with real values from Tasks 1, 6, 9, 10, 12.

- [x] **Step 2: Commit**

Pause and ask the user: "Docling bump is complete and verified. OK to commit the pyproject + lockfile changes and the final report?"

If yes, commit in two bites — bump first, report second:

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add src/backend/base/pyproject.toml pyproject.toml uv.lock && git commit -m "build(deps): bump docling ecosystem to 2.90 / core 2.74 / parse 5.x and swap rapidocr 1.x → 3.x"
```

```bash
cd /Users/brycedeneen/dev/langflow-docling-bump && git add docs/superpowers/specs/2026-04-20-docling-ecosystem-bump-report.md && git commit -m "docs: final report for docling ecosystem bump"
```

If the pandas-3 docling probe was removed, include that deletion in the first commit (`git add -u` picks it up, or add the path explicitly).

- [x] **Step 3: Announce completion**

Report to user: worktree at `../langflow-docling-bump`, branch `docling-ecosystem-bump`, N commits ahead of `platform-multi-tenant`. Ask how they want to integrate (merge into `platform-multi-tenant`, keep worktree, etc.) — do not merge without instructions.

---

## Self-review checklist (already run by the plan author)

- **Spec coverage:** Phase 1 audit (Task 1) covers §§ "Phase 1" and "Code usage surface" of the spec. Phase 2 smoke tests (Tasks 2–5) cover § "Phase 2" — one test per listed component. Phase 3 (Tasks 7–12) covers § "Phase 3" including all pin changes, lock regen, sync, and verification gates. Rollback is implicit via the worktree + commit policy.
- **Placeholder scan:** no `TBD`, no "implement later", no unresolved test bodies.
- **Type consistency:** `DoclingDocument(name=...)`, `ExportDoclingDocumentComponent.export_document()`, `ChunkDoclingDocumentComponent.chunk_documents()`, `DoclingRemoteComponent.process_files()`, `DoclingInlineComponent.process_files()`, and the `docling_worker` signature (`queue`, `file_paths`, `pipeline`, `ocr_engine`, `do_picture_classification`, `pic_desc_config`, `pic_desc_prompt`) all match the code as read.
- **Known-risk item:** `BaseFileComponent.BaseFile(path=..., file=None, data=None)` construction in the inline + remote tests — if the real dataclass has a different signature, Task 4 Step 2 and Task 5 Step 2 will surface it. The plan flags this explicitly rather than hiding it.
