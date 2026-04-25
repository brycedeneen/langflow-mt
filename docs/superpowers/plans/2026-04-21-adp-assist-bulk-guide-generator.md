# ADP Assist · Bulk Guide Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate starter `assist_guide` content for every **ADP-Assist-eligible** Langflow component (~400 classes, skipping those with `assist_enabled = False`) so ADP Assist's per-component popover opens with specialized guidance instead of a generic prompt. Produces a YAML bundle at `src/backend/base/langflow/services/component_assist/guides/` and a review report surfacing components with thin metadata.

**⚠ DataMapper hands-off:** `DataMapperComponent` sets `assist_enabled = False` (see Plan 1 Task 12A). The generator MUST skip it — do not write a YAML entry for it under any circumstance. Same rule applies to any other future opt-outs discovered at runtime.

**Architecture:** A one-shot Python script (`scripts/generate_component_assist_guides.py`) walks the two component roots, extracts metadata (display_name, description, documentation, per-input `info` strings, class docstring, return types) for each eligible class, asks an LLM to synthesize a 1–2 paragraph guide, and writes YAML files partitioned by top-level category directory. Idempotent: re-runs skip classes that already have a guide (inline or in-bundle) unless `--overwrite` is passed.

**Tech Stack:** Python 3.11+, `pyyaml`, `click` or `argparse` for CLI, Anthropic SDK (inherits the Claude API pattern from the existing flow-level assistant). Tests use `pytest` with a scripted fake LLM.

**Source spec:** `docs/superpowers/specs/2026-04-21-adp-assist-per-component-design.md` §7.

**Depends on:** `2026-04-21-adp-assist-per-component.md` (the guide registry + YAML loader must exist before this plan's output is useful).

---

## File structure

**Create:**

| File | Responsibility |
|---|---|
| `scripts/generate_component_assist_guides.py` | CLI entrypoint — walk, extract, synthesize, emit. |
| `scripts/_assist_guide_gen/__init__.py` | Package marker for helper modules. |
| `scripts/_assist_guide_gen/extract.py` | Pure metadata extraction from a Component class. |
| `scripts/_assist_guide_gen/synthesize.py` | LLM prompt + call that returns guide text. |
| `scripts/_assist_guide_gen/walker.py` | Discovers component classes under the two roots, honoring exclusion rules. |
| `scripts/_assist_guide_gen/emit.py` | YAML writer partitioned by top-level category + review report. |
| `tests/unit/assist_guide_gen/test_extract.py` | Metadata extraction tests. |
| `tests/unit/assist_guide_gen/test_synthesize.py` | Prompt shape + LLM stubbing tests. |
| `tests/unit/assist_guide_gen/test_walker.py` | Discovery + exclusion rule tests. |
| `tests/unit/assist_guide_gen/test_emit.py` | YAML partitioning + report tests. |

**Modify:**

| File | Change |
|---|---|
| `src/backend/base/langflow/services/component_assist/guides/*.yaml` | Produced by the generator on the final run. ~30 YAML files keyed by top-level component category. |

---

## Commands used throughout

- **Run generator tests:** `uv run pytest tests/unit/assist_guide_gen -v` (from repo root)
- **Dry-run the generator:** `uv run python scripts/generate_component_assist_guides.py --dry-run` (prints plan, writes nothing)
- **Generate, stopping on first error:** `uv run python scripts/generate_component_assist_guides.py --fail-fast`
- **Regenerate a single category:** `uv run python scripts/generate_component_assist_guides.py --category processing`
- **Overwrite existing bundle entries:** `uv run python scripts/generate_component_assist_guides.py --overwrite`

Memory callouts:
- Pause before every `git commit`.
- Keep LLM calls concurrency-bounded (the generator must not fan out 400 requests at once — default to `--concurrency 5`).
- Script lives under `scripts/` (same home as `build_component_index.py`), not inside a package.

---

## Task 1: `walker.py` — component discovery and exclusion

**Files:**
- Create: `scripts/_assist_guide_gen/__init__.py` (empty)
- Create: `scripts/_assist_guide_gen/walker.py`
- Create: `tests/unit/assist_guide_gen/__init__.py` (empty)
- Create: `tests/unit/assist_guide_gen/test_walker.py`

- [x] **Step 1: Write the failing test**

```python
"""Discovery + exclusion rule tests."""
from __future__ import annotations

from pathlib import Path

from scripts._assist_guide_gen.walker import (
    EXCLUDED_DIRECTORY_NAMES,
    FileCandidate,
    iter_candidate_files,
)


def _write(root: Path, rel: str, body: str = "class Foo: ...") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_excludes_files_starting_with_underscore(tmp_path: Path):
    _write(tmp_path, "processing/foo.py")
    _write(tmp_path, "processing/_private.py")
    files = list(iter_candidate_files(tmp_path))
    names = {f.path.name for f in files}
    assert "foo.py" in names
    assert "_private.py" not in names


def test_excludes_deactivated_directory(tmp_path: Path):
    _write(tmp_path, "deactivated/old.py")
    _write(tmp_path, "processing/keep.py")
    files = list(iter_candidate_files(tmp_path))
    paths = {str(f.path.relative_to(tmp_path)) for f in files}
    assert "processing/keep.py" in paths
    assert all("deactivated/" not in p for p in paths)


def test_excludes_dunder_init(tmp_path: Path):
    _write(tmp_path, "processing/__init__.py")
    _write(tmp_path, "processing/thing.py")
    names = {f.path.name for f in iter_candidate_files(tmp_path)}
    assert "__init__.py" not in names
    assert "thing.py" in names


def test_category_inferred_from_top_level_directory(tmp_path: Path):
    _write(tmp_path, "processing/text_ops.py")
    _write(tmp_path, "vectorstores/chroma/local.py")
    files = {str(f.path.relative_to(tmp_path)): f.category for f in iter_candidate_files(tmp_path)}
    assert files["processing/text_ops.py"] == "processing"
    assert files["vectorstores/chroma/local.py"] == "vectorstores"


def test_excluded_directory_names_covers_known_skips():
    assert "deactivated" in EXCLUDED_DIRECTORY_NAMES
```

- [x] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/assist_guide_gen/test_walker.py -v
```
Expected: ImportError.

- [x] **Step 3: Implement the walker**

```python
# scripts/_assist_guide_gen/walker.py
"""Walk component roots, yielding candidate files for guide generation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

EXCLUDED_DIRECTORY_NAMES: frozenset[str] = frozenset({"deactivated", "__pycache__"})


@dataclass(frozen=True)
class FileCandidate:
    path: Path          # absolute path to the .py file
    category: str       # top-level directory under the component root


def iter_candidate_files(root: Path) -> Iterator[FileCandidate]:
    """Yield every `.py` file under `root` eligible for guide generation.

    Excludes:
    - files whose name starts with `_` (internal/mixins) — including `__init__.py`
    - any file inside a directory whose name is in ``EXCLUDED_DIRECTORY_NAMES``
    """
    if not root.is_dir():
        return

    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
            continue
        rel = path.relative_to(root)
        if not rel.parts:
            continue
        yield FileCandidate(path=path, category=rel.parts[0])


def iter_all(roots: Iterable[Path]) -> Iterator[FileCandidate]:
    for root in roots:
        yield from iter_candidate_files(root)
```

- [x] **Step 4: Run and confirm passing**

```bash
uv run pytest tests/unit/assist_guide_gen/test_walker.py -v
```
Expected: 5 passed.

- [x] **Step 5: Commit**

```bash
git add scripts/_assist_guide_gen/__init__.py \
        scripts/_assist_guide_gen/walker.py \
        tests/unit/assist_guide_gen/__init__.py \
        tests/unit/assist_guide_gen/test_walker.py
git commit -m "feat(assist-guides): component discovery walker with exclusion rules"
```

---

## Task 2: `extract.py` — metadata extraction from a Component class

**Files:**
- Create: `scripts/_assist_guide_gen/extract.py`
- Create: `tests/unit/assist_guide_gen/test_extract.py`

- [x] **Step 1: Write the failing test**

```python
"""Tests for per-class metadata extraction."""
from __future__ import annotations

from typing import ClassVar

from scripts._assist_guide_gen.extract import (
    ComponentMetadata,
    extract_metadata,
    metadata_completeness,
)


class _FakeInput:
    def __init__(self, name: str, info: str | None = None):
        self.name = name
        self.info = info


class _Rich:
    """Rich component docstring."""

    display_name = "Rich Widget"
    description = "Does rich things."
    documentation = "https://example/rich"
    inputs: ClassVar = [
        _FakeInput("alpha", info="First input."),
        _FakeInput("beta", info="Second input."),
    ]


class _Thin:
    display_name = "Thin"
    description = ""
    inputs: ClassVar = [_FakeInput("x", info=None)]


def test_extracts_rich_metadata():
    meta = extract_metadata(_Rich)
    assert meta.display_name == "Rich Widget"
    assert meta.description == "Does rich things."
    assert meta.documentation == "https://example/rich"
    assert meta.docstring.startswith("Rich component")
    assert [(i.name, i.info) for i in meta.inputs] == [
        ("alpha", "First input."),
        ("beta", "Second input."),
    ]


def test_extracts_thin_metadata():
    meta = extract_metadata(_Thin)
    assert meta.display_name == "Thin"
    assert meta.description == ""
    assert meta.inputs[0].info is None


def test_completeness_flags_thin_metadata():
    assert metadata_completeness(extract_metadata(_Rich)) == "rich"
    assert metadata_completeness(extract_metadata(_Thin)) == "thin"
```

- [x] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/assist_guide_gen/test_extract.py -v
```
Expected: ImportError.

- [x] **Step 3: Implement extraction**

```python
# scripts/_assist_guide_gen/extract.py
"""Extract metadata from a Component class for LLM synthesis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class InputMetadata:
    name: str
    info: str | None


@dataclass(frozen=True)
class ComponentMetadata:
    class_name: str
    display_name: str
    description: str
    documentation: str | None
    docstring: str
    inputs: list[InputMetadata] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


def _safe_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def extract_metadata(component_cls: type) -> ComponentMetadata:
    class_name = component_cls.__name__
    display_name = _safe_str(getattr(component_cls, "display_name", ""))
    description = _safe_str(getattr(component_cls, "description", ""))
    documentation = _safe_str(getattr(component_cls, "documentation", "")) or None
    docstring = _safe_str(component_cls.__doc__ or "")

    inputs: list[InputMetadata] = []
    for raw in getattr(component_cls, "inputs", []) or []:
        name = getattr(raw, "name", None) or ""
        info = getattr(raw, "info", None)
        if name:
            inputs.append(InputMetadata(name=name, info=info if isinstance(info, str) else None))

    outputs: list[str] = []
    for raw in getattr(component_cls, "outputs", []) or []:
        name = getattr(raw, "name", None)
        if isinstance(name, str) and name:
            outputs.append(name)

    return ComponentMetadata(
        class_name=class_name,
        display_name=display_name,
        description=description,
        documentation=documentation,
        docstring=docstring,
        inputs=inputs,
        outputs=outputs,
    )


def metadata_completeness(meta: ComponentMetadata) -> Literal["rich", "thin"]:
    """Heuristic: flag components unlikely to yield a useful guide from metadata alone."""
    has_description = bool(meta.description) or bool(meta.docstring)
    has_input_info = any(i.info for i in meta.inputs)
    return "rich" if (has_description and (has_input_info or not meta.inputs)) else "thin"
```

- [x] **Step 4: Run and confirm passing**

```bash
uv run pytest tests/unit/assist_guide_gen/test_extract.py -v
```
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add scripts/_assist_guide_gen/extract.py tests/unit/assist_guide_gen/test_extract.py
git commit -m "feat(assist-guides): component metadata extraction + completeness heuristic"
```

---

## Task 3: `synthesize.py` — LLM-backed guide synthesis

**Files:**
- Create: `scripts/_assist_guide_gen/synthesize.py`
- Create: `tests/unit/assist_guide_gen/test_synthesize.py`

- [x] **Step 1: Write the failing test**

```python
"""Tests for LLM-backed guide synthesis."""
from __future__ import annotations

from scripts._assist_guide_gen.extract import ComponentMetadata, InputMetadata
from scripts._assist_guide_gen.synthesize import (
    build_prompt,
    synthesize_guide,
)


def _meta() -> ComponentMetadata:
    return ComponentMetadata(
        class_name="TextOperationsComponent",
        display_name="Text Operations",
        description="Run operations over text (split, join, trim).",
        documentation="https://docs.example/text-ops",
        docstring="",
        inputs=[
            InputMetadata("text", "The input text."),
            InputMetadata("operation", "Which operation to perform."),
        ],
        outputs=["result"],
    )


def test_prompt_includes_all_metadata():
    prompt = build_prompt(_meta())
    assert "Text Operations" in prompt
    assert "TextOperationsComponent" in prompt
    assert "split" in prompt
    assert "operation" in prompt


def test_synthesize_calls_llm_and_returns_text():
    recorded: list[str] = []

    def fake_llm(prompt: str) -> str:
        recorded.append(prompt)
        return "Synthesized guide body."

    guide = synthesize_guide(_meta(), llm=fake_llm)
    assert guide == "Synthesized guide body."
    assert "TextOperationsComponent" in recorded[0]


def test_synthesize_falls_back_when_llm_returns_empty():
    fake_llm = lambda _prompt: ""  # noqa: E731
    guide = synthesize_guide(_meta(), llm=fake_llm)
    # Fallback uses the description so the YAML entry isn't literally empty.
    assert "Text Operations" in guide
    assert "split" in guide.lower()
```

- [x] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/assist_guide_gen/test_synthesize.py -v
```
Expected: ImportError.

- [x] **Step 3: Implement synthesis**

```python
# scripts/_assist_guide_gen/synthesize.py
"""LLM-backed synthesis of assist guides from extracted metadata."""
from __future__ import annotations

import textwrap
from typing import Callable

from scripts._assist_guide_gen.extract import ComponentMetadata

LLMCall = Callable[[str], str]

_PROMPT_TEMPLATE = """\
You write short, useful configuration guides for individual components in a visual flow
builder. Each guide will be injected into the system prompt of an AI assistant that helps
users configure one instance of the component.

Write a 1–2 paragraph guide for this component. Cover:
- What the component does (one sentence).
- When the user should adjust which inputs, and what the inputs mean.
- Any notable constraints or gotchas inferable from the metadata.

Rules:
- Write in second person ("you help the user ...").
- Do not invent capabilities not present in the metadata.
- Do not repeat the display name or description verbatim — extract value from the inputs.
- No markdown headings; plain prose.
- 80–220 words.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}

Return ONLY the guide prose. No preamble, no closing, no markdown fencing.
"""


def _format_inputs(meta: ComponentMetadata) -> str:
    if not meta.inputs:
        return "  (no declared inputs)"
    lines = []
    for i in meta.inputs:
        info = i.info.replace("\n", " ").strip() if i.info else "(no description)"
        lines.append(f"  - {i.name}: {info}")
    return "\n".join(lines)


def build_prompt(meta: ComponentMetadata) -> str:
    return _PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
    )


def _fallback_guide(meta: ComponentMetadata) -> str:
    parts = [
        f"You help the user configure the {meta.display_name or meta.class_name} component.",
    ]
    if meta.description:
        parts.append(meta.description)
    if meta.inputs:
        names = ", ".join(i.name for i in meta.inputs if i.info or i.name)
        parts.append(f"Key inputs: {names}. Ask the user which they need to adjust.")
    return textwrap.fill(" ".join(parts), width=100)


def synthesize_guide(meta: ComponentMetadata, *, llm: LLMCall) -> str:
    prompt = build_prompt(meta)
    result = (llm(prompt) or "").strip()
    if not result:
        return _fallback_guide(meta)
    return result
```

- [x] **Step 4: Run and confirm passing**

```bash
uv run pytest tests/unit/assist_guide_gen/test_synthesize.py -v
```
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add scripts/_assist_guide_gen/synthesize.py tests/unit/assist_guide_gen/test_synthesize.py
git commit -m "feat(assist-guides): LLM-backed guide synthesis with deterministic fallback"
```

---

## Task 4: `emit.py` — YAML partitioning and review report

**Files:**
- Create: `scripts/_assist_guide_gen/emit.py`
- Create: `tests/unit/assist_guide_gen/test_emit.py`

- [x] **Step 1: Write the failing test**

```python
"""YAML emit + review report tests."""
from __future__ import annotations

from pathlib import Path

import yaml

from scripts._assist_guide_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)


def test_write_bundle_partitions_by_category(tmp_path: Path):
    entries = [
        GuideEntry(category="processing", component_type="AComponent", guide="A guide."),
        GuideEntry(category="processing", component_type="BComponent", guide="B guide."),
        GuideEntry(category="vectorstores", component_type="CComponent", guide="C guide."),
    ]
    write_bundle(entries, tmp_path)

    proc = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    assert {e["type"] for e in proc} == {"AComponent", "BComponent"}

    vec = yaml.safe_load((tmp_path / "vectorstores.yaml").read_text())
    assert vec[0]["type"] == "CComponent"


def test_write_bundle_skips_existing_entries_by_default(tmp_path: Path):
    existing = [{"type": "AComponent", "guide": "pre-existing"}]
    (tmp_path / "processing.yaml").write_text(yaml.safe_dump(existing))

    entries = [GuideEntry(category="processing", component_type="AComponent", guide="new")]
    write_bundle(entries, tmp_path)

    merged = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    guide_for_a = next(e for e in merged if e["type"] == "AComponent")["guide"]
    assert guide_for_a == "pre-existing"


def test_write_bundle_overwrites_when_flag_set(tmp_path: Path):
    existing = [{"type": "AComponent", "guide": "pre-existing"}]
    (tmp_path / "processing.yaml").write_text(yaml.safe_dump(existing))

    entries = [GuideEntry(category="processing", component_type="AComponent", guide="new")]
    write_bundle(entries, tmp_path, overwrite=True)

    merged = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    guide_for_a = next(e for e in merged if e["type"] == "AComponent")["guide"]
    assert guide_for_a == "new"


def test_write_review_report(tmp_path: Path):
    rows = [
        ReportRow(component_type="AComponent", category="processing", completeness="rich", status="generated"),
        ReportRow(component_type="BComponent", category="processing", completeness="thin", status="generated"),
        ReportRow(component_type="CComponent", category="vectorstores", completeness="rich", status="skipped-existing"),
        ReportRow(component_type="DataMapperComponent", category="processing", completeness="rich", status="skipped-opted-out"),
    ]
    report_path = tmp_path / "review.md"
    write_review_report(rows, report_path)
    body = report_path.read_text()
    assert "BComponent" in body
    assert "thin" in body
    assert "Flagged for manual review" in body  # the thin-metadata callout
    assert "DataMapperComponent" in body  # opt-outs surfaced
    assert "opted out" in body.lower() or "skipped-opted-out" in body
```

- [x] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/assist_guide_gen/test_emit.py -v
```
Expected: ImportError.

- [x] **Step 3: Implement emission**

```python
# scripts/_assist_guide_gen/emit.py
"""YAML bundle writer + review report generator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import yaml


@dataclass(frozen=True)
class GuideEntry:
    category: str
    component_type: str
    guide: str


@dataclass(frozen=True)
class ReportRow:
    component_type: str
    category: str
    completeness: Literal["rich", "thin"]
    status: Literal[
        "generated",
        "skipped-existing",
        "skipped-opted-out",
        "fallback-used",
        "errored",
    ]


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text()) or []
    return raw if isinstance(raw, list) else []


def write_bundle(entries: Iterable[GuideEntry], out_dir: Path, *, overwrite: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_category: dict[str, list[GuideEntry]] = {}
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry)

    for category, new_entries in sorted(by_category.items()):
        path = out_dir / f"{category}.yaml"
        existing = _load_existing(path)
        existing_types = {e.get("type") for e in existing}

        merged = list(existing)
        for entry in new_entries:
            if entry.component_type in existing_types and not overwrite:
                continue
            merged = [e for e in merged if e.get("type") != entry.component_type]
            merged.append({"type": entry.component_type, "guide": entry.guide})

        merged.sort(key=lambda e: e["type"])
        path.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=100))


def write_review_report(rows: Iterable[ReportRow], path: Path) -> None:
    rows_list = list(rows)
    thin = [r for r in rows_list if r.completeness == "thin"]
    opted_out = [r for r in rows_list if r.status == "skipped-opted-out"]
    lines: list[str] = [
        "# Component Assist Guide — Review Report",
        "",
        f"Total components processed: {len(rows_list)}",
        f"Generated: {sum(1 for r in rows_list if r.status == 'generated')}",
        f"Fallback used: {sum(1 for r in rows_list if r.status == 'fallback-used')}",
        f"Skipped (existing): {sum(1 for r in rows_list if r.status == 'skipped-existing')}",
        f"Skipped (opted out): {len(opted_out)}",
        f"Errored: {sum(1 for r in rows_list if r.status == 'errored')}",
        "",
        "## Opted out of ADP Assist",
        "",
    ]
    if not opted_out:
        lines.append("_None._")
    else:
        for row in sorted(opted_out, key=lambda r: (r.category, r.component_type)):
            lines.append(f"- `{row.category}/` · **{row.component_type}**")
    lines.append("")
    lines.append("## Flagged for manual review (thin metadata)")
    lines.append("")
    if not thin:
        lines.append("_None — every component had sufficient metadata._")
    else:
        for row in sorted(thin, key=lambda r: (r.category, r.component_type)):
            lines.append(f"- `{row.category}/` · **{row.component_type}** — {row.status}")
    lines.append("")
    path.write_text("\n".join(lines))
```

- [x] **Step 4: Run and confirm passing**

```bash
uv run pytest tests/unit/assist_guide_gen/test_emit.py -v
```
Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add scripts/_assist_guide_gen/emit.py tests/unit/assist_guide_gen/test_emit.py
git commit -m "feat(assist-guides): YAML partitioning and review-report writer"
```

---

## Task 5: CLI entrypoint + first full generation run

**Files:**
- Create: `scripts/generate_component_assist_guides.py`
- Create: `src/backend/base/langflow/services/component_assist/guides/*.yaml` (produced by running the script)
- Create: `docs/adp-assist-guide-generation-report.md` (produced by running the script)

- [x] **Step 1: Write the CLI entrypoint**

```python
# scripts/generate_component_assist_guides.py
#!/usr/bin/env python
"""Generate starter assist_guides for every user-facing Langflow component.

Run from repo root. See ``--help`` for flags.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts._assist_guide_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)
from scripts._assist_guide_gen.extract import (
    ComponentMetadata,
    extract_metadata,
    metadata_completeness,
)
from scripts._assist_guide_gen.synthesize import synthesize_guide
from scripts._assist_guide_gen.walker import FileCandidate, iter_all

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOTS = (
    REPO_ROOT / "src/lfx/src/lfx/components",
    REPO_ROOT / "src/backend/base/langflow/components",
)
GUIDES_DIR = REPO_ROOT / "src/backend/base/langflow/services/component_assist/guides"
REPORT_PATH = REPO_ROOT / "docs/adp-assist-guide-generation-report.md"


def _find_component_classes(candidate: FileCandidate) -> list[type]:
    """Import the module at ``candidate.path`` and return all Component subclasses it defines."""
    module_name = f"_assist_guide_module_{candidate.path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, candidate.path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return []

    from lfx.custom.custom_component.component import Component  # local import; heavy

    out: list[type] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if not issubclass(obj, Component) or obj is Component:
            continue
        out.append(obj)
    return out


def _build_llm() -> "object":
    """Return a callable ``(prompt: str) -> str`` backed by the Anthropic SDK."""
    import anthropic

    client = anthropic.Anthropic()

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    return call


def _process_one(
    candidate: FileCandidate,
    existing_types: set[str],
    overwrite: bool,
    llm,
) -> tuple[list[GuideEntry], list[ReportRow]]:
    from langflow.services.component_assist.guide_registry import is_assist_enabled

    entries: list[GuideEntry] = []
    rows: list[ReportRow] = []
    for cls in _find_component_classes(candidate):
        class_name = cls.__name__
        if not is_assist_enabled(cls):
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-opted-out"))
            continue
        if getattr(cls, "assist_guide", None):
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-existing"))
            continue
        if class_name in existing_types and not overwrite:
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-existing"))
            continue

        meta: ComponentMetadata = extract_metadata(cls)
        completeness = metadata_completeness(meta)
        try:
            guide = synthesize_guide(meta, llm=llm)
            status = "generated" if guide and guide.strip() else "fallback-used"
        except Exception as exc:  # noqa: BLE001
            guide = ""
            status = "errored"
            print(f"! {class_name}: {exc}", file=sys.stderr)
        if guide:
            entries.append(GuideEntry(candidate.category, class_name, guide))
        rows.append(ReportRow(class_name, candidate.category, completeness, status))
    return entries, rows


def _existing_bundle_types(out_dir: Path) -> set[str]:
    import yaml

    types: set[str] = set()
    for path in out_dir.glob("*.yaml"):
        raw = yaml.safe_load(path.read_text()) or []
        if isinstance(raw, list):
            types.update(e["type"] for e in raw if isinstance(e, dict) and "type" in e)
    return types


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ADP Assist component guides.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing guides.")
    parser.add_argument("--category", help="Restrict generation to one top-level category.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    candidates = list(iter_all(COMPONENT_ROOTS))
    if args.category:
        candidates = [c for c in candidates if c.category == args.category]

    if args.dry_run:
        print(f"Would process {len(candidates)} files across {len({c.category for c in candidates})} categories.")
        return 0

    existing_types = _existing_bundle_types(GUIDES_DIR)
    llm = _build_llm()

    all_entries: list[GuideEntry] = []
    all_rows: list[ReportRow] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(_process_one, c, existing_types, args.overwrite, llm): c
            for c in candidates
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            c = futures[fut]
            try:
                entries, rows = fut.result()
            except Exception as exc:
                print(f"!! {c.path}: {exc}", file=sys.stderr)
                if args.fail_fast:
                    return 1
                continue
            all_entries.extend(entries)
            all_rows.extend(rows)
            print(f"[{i}/{len(candidates)}] {c.category}/{c.path.name}")

    write_bundle(all_entries, GUIDES_DIR, overwrite=args.overwrite)
    write_review_report(all_rows, REPORT_PATH)
    print(f"\nWrote {len(all_entries)} guides to {GUIDES_DIR}")
    print(f"Review report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Dry-run the generator**

```bash
uv run python scripts/generate_component_assist_guides.py --dry-run
```
Expected: prints `Would process ~400 files across ~30 categories.`

- [x] **Step 3: Generate a single category as a sanity check**

Pick a small, well-instrumented category (`input_output` is a good candidate).

```bash
ANTHROPIC_API_KEY=... uv run python scripts/generate_component_assist_guides.py --category input_output
```

Inspect `src/backend/base/langflow/services/component_assist/guides/input_output.yaml`. Confirm the YAML parses, has one entry per user-facing class, and the guide bodies read like real guidance (not boilerplate or hallucination).

- [x] **Step 4: Full generation run**

```bash
ANTHROPIC_API_KEY=... uv run python scripts/generate_component_assist_guides.py --concurrency 8
```

Expect several minutes to tens of minutes depending on concurrency and provider latency. The run emits progress lines and a final summary. On completion, `docs/adp-assist-guide-generation-report.md` exists and lists any components flagged as thin.

- [x] **Step 5: Review the output**

Skim each YAML file. Spot-check 3–5 guides per large category for:
- Hallucinated capabilities (generator invented behavior that isn't in the metadata)
- Generic non-guidance ("This component does what its description says")
- Outdated references (pointing at things that no longer exist)

Delete or rewrite any problematic entries in-place. The registry loads whatever is on disk.

- [x] **Step 6: Commit per category**

Per the spec's review workflow, commit in small batches:

```bash
git add src/backend/base/langflow/services/component_assist/guides/input_output.yaml \
        src/backend/base/langflow/services/component_assist/guides/processing.yaml \
        src/backend/base/langflow/services/component_assist/guides/data.yaml
git commit -m "feat(assist-guides): starter guides for input_output/processing/data components"
```

Repeat for subsequent clusters of categories, sized for reviewability (3–5 files each).

- [x] **Step 7: Commit the review report**

```bash
git add docs/adp-assist-guide-generation-report.md
git commit -m "docs(assist-guides): generation review report"
```

- [x] **Step 8: Smoke-test the end-to-end flow**

With Plan 1's infrastructure already in place:

1. Start the backend + frontend.
2. Open a flow that uses any of the newly-guided components.
3. Click the Assist icon on one of them.
4. Send a configuration question related to the component.
5. Confirm the LLM's response reflects the specific guide (not the generic fallback) — the wording should pick up nuances from that component's YAML entry.

If the response is generic, open the YAML entry for that component type and confirm the guide text actually loaded (check server logs for any YAML parse errors).

- [x] **Step 9: Commit the generator script if not already committed**

```bash
git add scripts/generate_component_assist_guides.py
git commit -m "feat(assist-guides): bulk generator CLI"
```

---

## Self-Review

**Spec coverage (§7 of the design doc):**

| Spec requirement | Covered by |
|---|---|
| Inventory (~400 classes, exclusions) | Task 1 (walker) |
| Metadata extraction (display_name, description, documentation, input `info`, docstring) | Task 2 (extract) |
| LLM synthesis, 1–2 paragraph guide | Task 3 (synthesize) |
| Skip `deactivated/`, `_`-prefixed files | Task 1 (walker) |
| Skip classes with inline `assist_guide` | Task 5 (`_process_one`) |
| YAML format (list of `{type, guide}`) | Task 4 (emit) |
| Per-category YAML partitioning | Task 4 (emit) |
| Idempotent re-runs, `--overwrite` flag | Tasks 4 + 5 |
| Review report with thin-metadata callout | Task 4 (emit) |
| Per-directory PR-sized commits | Task 5 Step 6 |
| Acceptance bar (every non-excluded component has an entry) | Task 5 Step 4 (full run) |

**Placeholder scan:** No "TBD"/"TODO" markers. The one soft spot is Task 5 Step 4 — the actual full run depends on an Anthropic API key and network; it's called out explicitly in the step and the executor will need one.

**Type consistency:** `ComponentMetadata`, `InputMetadata`, `GuideEntry`, `ReportRow`, `FileCandidate`, and the `LLMCall` signature are used consistently across Tasks 1–5.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-adp-assist-bulk-guide-generator.md`. Execute after `2026-04-21-adp-assist-per-component.md` is merged (the registry + YAML loader it produces are prerequisites for this plan's output to be useful).

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — batch execution with checkpoints.
