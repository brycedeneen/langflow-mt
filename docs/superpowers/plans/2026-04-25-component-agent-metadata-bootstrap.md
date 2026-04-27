# Component Agent Metadata Bootstrap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate starting `agent_summary` and `agent_usage_notes` content for every assist-enabled, non-legacy component, persist it as YAML in source control, and seed it into the existing `component_metadata` DB table at startup.

**Architecture:** Offline LLM-driven generator script writes per-category YAML bundles under `services/component_assist/agent_metadata/`. A new lifespan-startup seeder (`create_or_update_component_agent_metadata`, sibling to `create_or_update_template_metadata`) upserts those entries into `component_metadata` using the same three-state `updated_by` policy. The existing `guide_registry.resolve()` becomes async and reads `agent_usage_notes` from the DB before falling back to the existing class-attribute / YAML chain.

**Tech Stack:** Python 3.11+, FastAPI, SQLModel, SQLAlchemy async, pytest + pytest-asyncio, pyyaml, Anthropic SDK (Claude Sonnet 4.6).

**Spec:** `docs/superpowers/specs/2026-04-25-component-agent-metadata-bootstrap-design.md`

---

## Conventions used in this plan

- Python tests run with `uv run pytest <path> -v`.
- Backend tests live under `src/backend/tests/`. The lfx tests (used here only for resolver tests of components in `src/lfx`) run with `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/...`.
- After every task that touches code, run `uv run ruff check <paths>` for lint and `uv run pytest <test_paths> -v` for tests.
- Each task ends with a "Commit" step. **Do not commit without confirming with the user first.** When the step says "commit", pause and ask.
- Stage files explicitly by path. Never use `git add -A` or `git add .`.

---

## Task 1: Verify pre-flight assumptions

No code changes. Investigate and document findings inline in the plan (or as comments in subsequent tasks) before any implementation.

**Files:**
- Read-only: `src/backend/base/langflow/services/component_assist/guide_registry.py`, `src/backend/base/langflow/api/v1/component_assist.py`, `src/backend/base/langflow/initial_setup/setup.py`, `src/backend/base/langflow/main.py`, `src/lfx/src/lfx/inputs/inputs.py` (or wherever Input classes live).

- [ ] **Step 1: Confirm `guide_registry.resolve` has only one production call site**

Run:

```bash
rg -n 'guide_registry\.resolve|resolve as resolve_guide|from .*guide_registry import.*resolve' src/
```

Expected: matches in `src/backend/base/langflow/api/v1/component_assist.py` and `src/backend/tests/unit/services/component_assist/test_guide_registry.py` only. If anything else turns up under `src/backend/base/langflow/` or `src/lfx/src/lfx/`, list it — those call sites need updating in Task 5.

- [ ] **Step 2: Confirm the lifespan position for the new seeder**

Open `src/backend/base/langflow/main.py` and locate the existing `await create_or_update_template_metadata()` call (~line 206, inside the lifespan startup block). Confirm:
- It's wrapped in a `try/except Exception` that logs a warning and continues.
- The line above it caches types via `get_and_cache_all_types_dict`.

The new seeder call goes immediately after the template-metadata call, mirroring the same try/except shape.

- [ ] **Step 3: Confirm Input class attribute names**

Spot-read three Input definitions from `src/lfx/src/lfx/inputs/inputs.py` (or wherever they live — `rg -n 'class .*Input.*BaseModel' src/lfx/src/lfx/inputs/`). For each, confirm the attribute names that `extract_metadata` will read:
- `name` — the field name
- `info` — the description string
- `field_type` — the Input subclass name (e.g., `"SecretStrInput"`); confirm via `Input(...).field_type` or via class-name introspection
- `required` — bool, defaults to False
- `advanced` — bool, defaults to False

If `field_type` is not a public attribute, use `type(raw).__name__` instead. Note the chosen approach as a comment in `_agent_metadata_gen/synthesize.py` when it's written in Task 8.

- [ ] **Step 4: Confirm `legacy` is the right filter signal**

Run:

```bash
rg -n 'legacy = True|legacy: ClassVar\[bool\] = True' src/lfx/src/lfx/components/ src/backend/base/langflow/components/ | wc -l
```

Expected: a non-zero count (today: 14+ results across `datastax/`, `deactivated/`, etc.). Confirm a sample of the matches are real Component subclasses by opening 2-3 of them.

- [ ] **Step 5: Confirm the YAML output directory does not already exist or collide**

Run:

```bash
ls -la src/backend/base/langflow/services/component_assist/
```

Expected: a `guides/` directory exists; no `agent_metadata/` directory yet. Confirm by also running:

```bash
rg -n 'agent_metadata' src/backend/ src/lfx/ | grep -v specs/ | grep -v plans/ | grep -v _generated.ts | grep -v generated.meta.ts
```

Expected: only matches in code that's about to be added (none yet, or nothing semantically relevant).

- [ ] **Step 6: Note findings**

If any of steps 1–5 surface deviations from the spec's assumptions, write them down (as a short note in the PR description, or as a comment at the top of the relevant module). If nothing deviates, proceed to Task 2.

- [ ] **Step 7: No commit**

This task makes no code changes. Move to Task 2.

---

## Task 2: Extend `InputMetadata` with `field_type`, `required`, `advanced`

The existing `InputMetadata` only captures `name` and `info`. We need three more fields so the synthesizer prompt can include them and the LLM can decide which inputs are "ask the user" candidates vs hidden / advanced / secret.

**Files:**
- Modify: `scripts/_assist_guide_gen/extract.py`
- Test: `tests/unit/assist_guide_gen/test_extract.py`

- [ ] **Step 1: Write the failing test**

Open `tests/unit/assist_guide_gen/test_extract.py` and add (do not replace existing tests):

```python
def test_extract_metadata_captures_field_type_required_advanced():
    class _Input:
        def __init__(self, name, info=None, required=False, advanced=False):
            self.name = name
            self.info = info
            self.required = required
            self.advanced = advanced
            # Mimics SecretStrInput / TableInput / etc. Subclass name surfaces via type().__name__.
        @property
        def field_type(self):
            return type(self).__name__

    class _SecretStrInput(_Input):
        pass

    class _Comp:
        display_name = "Comp"
        description = "desc"
        documentation = ""
        inputs = [
            _Input(name="prompt", info="user prompt", required=True),
            _SecretStrInput(name="api_key", info="LLM key", required=True),
            _Input(name="advanced_knob", info="rare knob", advanced=True),
        ]
        outputs = []

    meta = extract_metadata(_Comp)
    assert [(i.name, i.field_type, i.required, i.advanced) for i in meta.inputs] == [
        ("prompt", "_Input", True, False),
        ("api_key", "_SecretStrInput", True, False),
        ("advanced_knob", "_Input", False, True),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/assist_guide_gen/test_extract.py::test_extract_metadata_captures_field_type_required_advanced -v
```

Expected: FAIL — `AttributeError: 'InputMetadata' object has no attribute 'field_type'` or similar.

- [ ] **Step 3: Extend `InputMetadata` and `extract_metadata`**

Edit `scripts/_assist_guide_gen/extract.py`:

```python
"""Extract metadata from a Component class for LLM synthesis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class InputMetadata:
    name: str
    info: str | None
    field_type: str | None = None
    required: bool = False
    advanced: bool = False


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


def _input_field_type(raw: Any) -> str | None:
    """Prefer an explicit ``field_type`` attribute; fall back to the Python class name."""
    explicit = getattr(raw, "field_type", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    cls = type(raw)
    return cls.__name__ if cls is not object else None


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
            inputs.append(
                InputMetadata(
                    name=name,
                    info=info if isinstance(info, str) else None,
                    field_type=_input_field_type(raw),
                    required=bool(getattr(raw, "required", False)),
                    advanced=bool(getattr(raw, "advanced", False)),
                )
            )

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

- [ ] **Step 4: Run new + existing extract tests to confirm no regression**

Run:

```bash
uv run pytest tests/unit/assist_guide_gen/test_extract.py -v
```

Expected: PASS — including any pre-existing tests that read only `name`/`info`.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check scripts/_assist_guide_gen/extract.py tests/unit/assist_guide_gen/test_extract.py
```

Expected: no errors.

- [ ] **Step 6: Commit (pause and ask the user first)**

```bash
git add scripts/_assist_guide_gen/extract.py tests/unit/assist_guide_gen/test_extract.py
git commit -m "feat(assist-gen): extend InputMetadata with field_type, required, advanced"
```

---

## Task 3: Add `agent_metadata/` YAML output directory placeholder

Create the directory and a `.gitkeep` so subsequent tasks can reference it without "no such directory" errors. Trivial but isolates the path decision in its own commit.

**Files:**
- Create: `src/backend/base/langflow/services/component_assist/agent_metadata/.gitkeep`

- [ ] **Step 1: Create the directory and gitkeep**

```bash
mkdir -p src/backend/base/langflow/services/component_assist/agent_metadata
touch src/backend/base/langflow/services/component_assist/agent_metadata/.gitkeep
```

- [ ] **Step 2: Confirm the directory is committable**

Run:

```bash
git status -s src/backend/base/langflow/services/component_assist/agent_metadata
```

Expected: shows `?? src/backend/base/langflow/services/component_assist/agent_metadata/.gitkeep`.

- [ ] **Step 3: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/services/component_assist/agent_metadata/.gitkeep
git commit -m "chore(assist): scaffold agent_metadata bundle directory"
```

---

## Task 4: Convert `guide_registry.resolve` to async with DB-first lookup

The DB-first behavior change. After this task, the resolver consults `component_metadata.agent_usage_notes` first; if it's null/empty, the existing class-attribute / YAML / None chain is used unchanged.

**Files:**
- Modify: `src/backend/base/langflow/services/component_assist/guide_registry.py`
- Modify: `src/backend/tests/unit/services/component_assist/test_guide_registry.py`
- Modify: `src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py` (only if its assertions call `resolve` directly — confirm in step 1)

- [ ] **Step 1: Audit existing resolve test assertions**

Run:

```bash
rg -n 'guide_registry\.resolve|resolve as resolve_guide' src/lfx/tests/ src/backend/tests/
```

Expected: hits in `src/backend/tests/unit/services/component_assist/test_guide_registry.py` (lines ~27, 36, 41) and in `src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py` if it imports `resolve`. Both will need `await` after this task.

- [ ] **Step 2: Write failing test for DB-first lookup**

Edit `src/backend/tests/unit/services/component_assist/test_guide_registry.py`. Append:

```python
import pytest


@pytest.mark.asyncio
async def test_db_lookup_takes_priority_over_class_attribute(monkeypatch: pytest.MonkeyPatch):
    """A non-empty agent_usage_notes in the DB beats an inline assist_guide class attr."""
    async def _fake_db_lookup(name: str) -> str | None:
        return "from-db" if name == "_FakeWithGuide" else None

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _fake_db_lookup,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win either"},
    )
    assert await guide_registry.resolve(_FakeWithGuide) == "from-db"


@pytest.mark.asyncio
async def test_db_lookup_falls_through_when_null(monkeypatch: pytest.MonkeyPatch):
    """When DB returns None, the class-attribute path still wins."""
    async def _no_row(name: str) -> str | None:
        return None

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _no_row,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {})
    assert await guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


@pytest.mark.asyncio
async def test_db_lookup_falls_through_when_empty_string(monkeypatch: pytest.MonkeyPatch):
    """Empty string in DB is treated as no content; falls through to next step."""
    async def _empty(name: str) -> str | None:
        return "   "

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _empty,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {"_FakeWithoutGuide": "yaml"})
    assert await guide_registry.resolve(_FakeWithoutGuide) == "yaml"
```

Also update the existing tests in the same file to be async — they currently call `guide_registry.resolve(...)` synchronously. Replace each with the async version and a `monkeypatch` of `fetch_component_usage_notes` returning `None`:

```python
@pytest.mark.asyncio
async def test_class_attribute_takes_priority(monkeypatch: pytest.MonkeyPatch):
    async def _no_row(name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win"},
    )
    assert await guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


@pytest.mark.asyncio
async def test_yaml_bundle_fallback(monkeypatch: pytest.MonkeyPatch):
    async def _no_row(name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithoutGuide": "yaml guide body"},
    )
    assert await guide_registry.resolve(_FakeWithoutGuide) == "yaml guide body"


@pytest.mark.asyncio
async def test_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch):
    async def _no_row(name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {})
    assert await guide_registry.resolve(_FakeWithoutGuide) is None
```

- [ ] **Step 3: Run new tests to verify they fail**

Run:

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_guide_registry.py -v
```

Expected: the new async tests FAIL because `resolve` is still sync (TypeError or "object str can't be used in 'await' expression"). Pre-existing tests will also fail because they're now `await`ing a sync function.

- [ ] **Step 4: Update `guide_registry.py` to async with DB-first lookup**

Replace the file's contents with:

```python
"""Resolve a component's assist guide.

Resolution order:
1. ``component_metadata.agent_usage_notes`` in the DB (admin-editable).
2. ``assist_guide: ClassVar[str]`` attribute on the class (legacy).
3. YAML bundle under ``guides/*.yaml`` keyed by class name (legacy).
4. ``None`` — callers fall back to a generic system prompt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from langflow.services.assistant.tools.metadata_lookup import (
    fetch_component_usage_notes,
)

logger = logging.getLogger(__name__)

_GUIDES_DIR = Path(__file__).parent / "guides"
_cached_bundle: dict[str, str] | None = None


def _load_yaml_bundle() -> dict[str, str]:
    """Load and merge every ``*.yaml`` file under ``_GUIDES_DIR``. Cached for the process."""
    global _cached_bundle  # noqa: PLW0603
    if _cached_bundle is not None:
        return _cached_bundle

    merged: dict[str, str] = {}
    if _GUIDES_DIR.is_dir():
        for path in sorted(_GUIDES_DIR.glob("*.yaml")):
            try:
                raw: Any = yaml.safe_load(path.read_text()) or []
            except yaml.YAMLError:
                logger.warning("Skipping malformed guide YAML: %s", path)
                continue
            if not isinstance(raw, list):
                continue
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                component_type = entry.get("type")
                guide = entry.get("guide")
                if isinstance(component_type, str) and isinstance(guide, str):
                    merged[component_type] = guide
    _cached_bundle = merged
    return merged


async def resolve(component_cls: type) -> str | None:
    """Return the guide for a component class, or ``None`` if none configured.

    Resolution order: DB (component_metadata.agent_usage_notes) -> class attr
    ``assist_guide`` -> YAML bundle -> ``None``.
    """
    # 1. DB lookup (component_metadata.agent_usage_notes).
    db_value = await fetch_component_usage_notes(component_cls.__name__)
    if isinstance(db_value, str) and db_value.strip():
        return db_value

    # 2. Class attribute (legacy inline guide).
    inline = getattr(component_cls, "assist_guide", None)
    if isinstance(inline, str) and inline.strip():
        return inline

    # 3. YAML bundle (legacy bundle).
    return _load_yaml_bundle().get(component_cls.__name__)


def is_assist_enabled(component_cls: type) -> bool:
    """Return ``False`` only when the class explicitly opts out via ``assist_enabled = False``.

    Components opt out when they ship their own bespoke assistant (e.g., DataMapperComponent).
    """
    value = getattr(component_cls, "assist_enabled", True)
    return bool(value)


def reset_cache() -> None:
    """Test helper — drop the cached YAML bundle."""
    global _cached_bundle  # noqa: PLW0603
    _cached_bundle = None
```

- [ ] **Step 5: Update the only production caller (`api/v1/component_assist.py`)**

Edit `src/backend/base/langflow/api/v1/component_assist.py:157` from:

```python
    guide = resolve_guide(component_cls) if component_cls is not None else None
```

to:

```python
    guide = await resolve_guide(component_cls) if component_cls is not None else None
```

The enclosing function `component_assist_messages` is already `async def`, so no further changes are needed at that call site.

- [ ] **Step 6: Update `src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py` if it calls `resolve`**

Re-run the audit:

```bash
rg -n 'guide_registry\.resolve' src/lfx/tests/
```

If a match exists in `test_assist_opt_out_and_guide.py`, change the assertion to `await`-style (`@pytest.mark.asyncio` on the test) and stub `fetch_component_usage_notes` exactly as the backend tests do. If `rg` returns no matches, skip this step.

- [ ] **Step 7: Run all resolver-related tests**

Run:

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_guide_registry.py -v
```

Expected: all PASS, including the new DB-first cases.

If `src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py` was modified in step 6, also run:

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py -v
```

Expected: PASS.

- [ ] **Step 8: Lint**

Run:

```bash
uv run ruff check src/backend/base/langflow/services/component_assist/guide_registry.py src/backend/base/langflow/api/v1/component_assist.py src/backend/tests/unit/services/component_assist/test_guide_registry.py
```

Expected: no errors.

- [ ] **Step 9: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/services/component_assist/guide_registry.py \
        src/backend/base/langflow/api/v1/component_assist.py \
        src/backend/tests/unit/services/component_assist/test_guide_registry.py
# only if step 6 modified it:
git add src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py 2>/dev/null || true
git commit -m "feat(assist): resolve() is async + DB-first; agent_usage_notes wins over assist_guide"
```

---

## Task 5: Add `create_or_update_component_agent_metadata` seeder

Mirrors the shape of the existing `create_or_update_template_metadata` (`setup.py:1016`). Three-state `updated_by` policy. Unit-tested with a tmp YAML directory and an in-memory DB fixture (the same fixtures `test_template_metadata_seeding.py` uses).

**Files:**
- Modify: `src/backend/base/langflow/initial_setup/setup.py` — add new function near `create_or_update_template_metadata`.
- Create: `src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py`

- [ ] **Step 1: Write failing tests for the seeder**

Create `src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py`:

```python
"""Tests for create_or_update_component_agent_metadata.

Seeder behavior (per spec):
- First seed (no row exists) -> INSERT with updated_by=NULL.
- Re-seed when updated_by IS NULL -> UPDATE (overwrite from YAML).
- Re-seed when updated_by IS NOT NULL -> SKIP (admin took ownership).
- Malformed YAML file -> log + skip, doesn't break sibling files.
- Concurrent INSERT race -> IntegrityError swallowed; no exception bubbled.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.initial_setup.setup import (
    create_or_update_component_agent_metadata,
    session_scope,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata


def _write_yaml(dir_path: Path, filename: str, body: str) -> None:
    (dir_path / filename).write_text(body)


async def _fetch_metadata(component_name: str) -> ComponentMetadata | None:
    async with session_scope() as session:
        return (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
            )
        ).first()


@pytest.mark.asyncio
async def test_first_seed_inserts_row(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: One-line summary.\n"
        "  agent_usage_notes: |\n"
        "    ## What it does\n"
        "    Calls OpenAI.\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row is not None
    assert row.agent_summary == "One-line summary."
    assert "## What it does" in row.agent_usage_notes
    assert row.updated_by is None


@pytest.mark.asyncio
async def test_reseed_updates_when_updated_by_is_null(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Original.\n"
        "  agent_usage_notes: original notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    # Regenerate with new content, re-seed.
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Updated.\n"
        "  agent_usage_notes: updated notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row.agent_summary == "Updated."
    assert row.agent_usage_notes == "updated notes"
    assert row.updated_by is None


@pytest.mark.asyncio
async def test_reseed_skips_when_admin_owned(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Original.\n"
        "  agent_usage_notes: original notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    admin_id = uuid4()
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == "OpenAIModel"
                )
            )
        ).first()
        row.agent_summary = "Admin-edited."
        row.updated_by = admin_id
        session.add(row)

    # Re-seed with new YAML content; admin row must not be overwritten.
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Should-not-overwrite.\n"
        "  agent_usage_notes: nope\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row.agent_summary == "Admin-edited."
    assert row.updated_by == admin_id


@pytest.mark.asyncio
async def test_malformed_yaml_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    _write_yaml(tmp_path, "good.yaml", "- component_name: GoodComp\n  agent_summary: G\n  agent_usage_notes: g\n")
    _write_yaml(tmp_path, "bad.yaml", "::: not: yaml [\n")

    with caplog.at_level("WARNING"):
        await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    assert await _fetch_metadata("GoodComp") is not None
    assert any("bad.yaml" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_no_yaml_files_is_noop(tmp_path: Path):
    # Empty directory should not raise and not create any rows.
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)
    async with session_scope() as session:
        all_rows = (await session.exec(select(ComponentMetadata))).all()
    # Filter to a sentinel name that the test owns:
    assert not any(r.component_name == "GoodComp" for r in all_rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py -v
```

Expected: ImportError — `create_or_update_component_agent_metadata` does not exist yet.

- [ ] **Step 3: Implement the seeder**

Open `src/backend/base/langflow/initial_setup/setup.py`. Add this import block near the existing `from langflow.services.database.models.template_metadata.model import TemplateMetadata` line (~line 50):

```python
from langflow.services.database.models.component_metadata.model import ComponentMetadata
```

Add the new function immediately after `create_or_update_template_metadata` (the existing function ends around line 1108). Do not touch the existing function:

```python
async def create_or_update_component_agent_metadata(
    yaml_dir: anyio.Path | Path | None = None,
) -> None:
    """Seed ``ComponentMetadata`` rows from per-category YAML bundles.

    Each YAML file under ``yaml_dir`` is a list of
    ``{component_name, agent_summary, agent_usage_notes}`` entries.

    Upsert policy (matches ``create_or_update_template_metadata``):
    - No existing row -> INSERT with ``updated_by=None``.
    - Existing row, ``updated_by IS NULL`` -> UPDATE (re-seed).
    - Existing row, ``updated_by IS NOT NULL`` -> SKIP (admin took ownership).
    - IntegrityError on INSERT (concurrent worker won the race) -> swallow + debug log.
    """
    import yaml as _yaml
    from sqlalchemy.exc import IntegrityError

    if yaml_dir is None:
        yaml_dir = anyio.Path(__file__).resolve().parent.parent / "services" / "component_assist" / "agent_metadata"
    else:
        yaml_dir = anyio.Path(yaml_dir)

    yaml_files: list[anyio.Path] = []
    async for f in yaml_dir.glob("*.yaml"):
        yaml_files.append(f)

    if not yaml_files:
        await logger.adebug(
            f"No component agent-metadata YAML files in {yaml_dir}; skipping."
        )
        return

    inserted = 0
    reseeded = 0
    skipped = 0

    for yaml_file in yaml_files:
        try:
            content = await yaml_file.read_text(encoding="utf-8")
            entries = _yaml.safe_load(content) or []
        except _yaml.YAMLError as e:
            await logger.awarning(f"Skipping malformed agent-metadata YAML {yaml_file.name}: {e}")
            continue
        except Exception as e:  # noqa: BLE001
            await logger.aexception(f"Skipping agent-metadata YAML {yaml_file.name}: {e}")
            continue

        if not isinstance(entries, list):
            await logger.awarning(f"Top-level YAML in {yaml_file.name} is not a list; skipping.")
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            component_name = entry.get("component_name")
            if not isinstance(component_name, str) or not component_name.strip():
                continue
            agent_summary = entry.get("agent_summary")
            agent_usage_notes = entry.get("agent_usage_notes")

            async with session_scope() as session:
                existing_stmt = select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
                existing = (await session.exec(existing_stmt)).first()

                if existing is None:
                    row = ComponentMetadata(
                        component_name=component_name,
                        agent_summary=agent_summary,
                        agent_usage_notes=agent_usage_notes,
                        updated_by=None,
                    )
                    session.add(row)
                    try:
                        await session.flush()
                    except IntegrityError:
                        await session.rollback()
                        await logger.adebug(
                            f"Race on component_metadata insert for '{component_name}'; another worker won."
                        )
                        continue
                    inserted += 1
                elif existing.updated_by is None:
                    existing.agent_summary = agent_summary
                    existing.agent_usage_notes = agent_usage_notes
                    session.add(existing)
                    reseeded += 1
                else:
                    skipped += 1

    await logger.ainfo(
        f"Component agent metadata seed: inserted {inserted}, "
        f"re-seeded {reseeded}, skipped {skipped} (admin-owned)."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/backend/base/langflow/initial_setup/setup.py src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py
```

Expected: no errors.

- [ ] **Step 6: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/initial_setup/setup.py \
        src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py
git commit -m "feat(assist): seeder for component agent metadata (3-state updated_by policy)"
```

---

## Task 6: Wire the seeder into the lifespan startup

The seeder is harmless when the YAML directory is empty (Task 3 left only a `.gitkeep`), so we can wire it now and start exercising the path immediately.

**Files:**
- Modify: `src/backend/base/langflow/main.py` — add an import + a try/except call after the template-metadata call (~line 206).

- [ ] **Step 1: Read the surrounding context**

Open `src/backend/base/langflow/main.py` around lines 200–215. Confirm the shape:

```python
            # Seed template metadata from .metadata.json sidecars (ADP etc.).
            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Seeding template metadata")
            try:
                await create_or_update_template_metadata()
                await logger.adebug(
                    f"Template metadata seeded in {asyncio.get_event_loop().time() - current_time:.2f}s"
                )
            except Exception as e:  # noqa: BLE001
                await logger.awarning(f"Failed to seed template metadata: {e}")
```

- [ ] **Step 2: Add the import**

Find the existing import line `create_or_update_template_metadata,` (~line 33) and add the new function alongside it:

```python
from langflow.initial_setup.setup import (
    ...,
    create_or_update_component_agent_metadata,
    create_or_update_template_metadata,
    ...,
)
```

(Order alphabetically within the existing import block; the linter / isort will resolve any drift.)

- [ ] **Step 3: Add the new lifespan call after the template-metadata call**

Insert immediately after the existing template-metadata try/except block (~line 211):

```python
            # Seed component agent metadata from per-category YAML bundles.
            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Seeding component agent metadata")
            try:
                await create_or_update_component_agent_metadata()
                await logger.adebug(
                    f"Component agent metadata seeded in {asyncio.get_event_loop().time() - current_time:.2f}s"
                )
            except Exception as e:  # noqa: BLE001
                await logger.awarning(f"Failed to seed component agent metadata: {e}")
```

- [ ] **Step 4: Boot the app to confirm no regression**

Run (in a separate terminal if a long-running boot is needed):

```bash
uv run langflow run --host 127.0.0.1 --port 7860 --no-open-browser &
LANGFLOW_PID=$!
sleep 8
curl -sf http://127.0.0.1:7860/health > /dev/null && echo "OK: health endpoint responded" || echo "FAIL: health endpoint did not respond"
kill $LANGFLOW_PID
```

Expected: `OK: health endpoint responded`. The startup logs should include `"Seeding component agent metadata"` and `"No component agent-metadata YAML files in …; skipping."` (debug level — may need to set `LANGFLOW_LOG_LEVEL=debug` to see).

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/backend/base/langflow/main.py
```

Expected: no errors.

- [ ] **Step 6: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/main.py
git commit -m "feat(assist): wire component agent metadata seeder into lifespan"
```

---

## Task 7: Build the peer index module (`scripts/_agent_metadata_gen/peers.py`)

The peer index is what lets the summary prompt include real sibling components by name + 1-line description. Includes hand-authored peer entries (currently DataMapper).

**Files:**
- Create: `scripts/_agent_metadata_gen/__init__.py` (empty)
- Create: `scripts/_agent_metadata_gen/peers.py`
- Create: `tests/unit/agent_metadata_gen/__init__.py` (empty)
- Create: `tests/unit/agent_metadata_gen/test_peers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agent_metadata_gen/test_peers.py`:

```python
"""Tests for peer-index construction."""
from __future__ import annotations

from scripts._agent_metadata_gen.peers import (
    HAND_AUTHORED_PEERS,
    PeerEntry,
    build_peer_index,
    format_peers_block,
)


def _comp(name: str, *, category: str, display_name: str = "", description: str = "", legacy: bool = False, assist_enabled: bool = True):
    cls = type(name, (), {})
    cls.display_name = display_name or name
    cls.description = description
    cls.legacy = legacy
    cls.assist_enabled = assist_enabled
    cls.__category__ = category  # test helper; build_peer_index actually consumes (cls, category) tuples
    return cls


def test_index_groups_by_category_and_excludes_legacy():
    classes = [
        (_comp("Alpha", category="x", description="desc-a"), "x"),
        (_comp("Beta", category="x", description="desc-b", legacy=True), "x"),
        (_comp("Gamma", category="y", description="desc-g"), "y"),
    ]
    idx = build_peer_index(classes)
    assert sorted(p.component_name for p in idx["x"]) == ["Alpha"]
    assert sorted(p.component_name for p in idx["y"]) == ["Gamma"]


def test_index_includes_opted_out_components():
    """Opted-out components still appear in the canvas picker, so they remain peer-eligible."""
    classes = [
        (_comp("OptedOut", category="z", description="desc-o", assist_enabled=False), "z"),
        (_comp("Visible", category="z", description="desc-v"), "z"),
    ]
    idx = build_peer_index(classes)
    assert sorted(p.component_name for p in idx["z"]) == ["OptedOut", "Visible"]


def test_index_merges_hand_authored_peers():
    """Hand-authored peers are merged into the matching category."""
    classes = [
        (_comp("StructuredOutput", category="processing", description="natural-language extraction"), "processing"),
    ]
    idx = build_peer_index(classes)
    names = sorted(p.component_name for p in idx["processing"])
    assert "DataMapper" in names  # comes from HAND_AUTHORED_PEERS
    assert "StructuredOutput" in names


def test_format_peers_block_excludes_self_and_renders_one_line_each():
    peers = [
        PeerEntry(component_name="A", category="x", display_name="A Comp", description="does a"),
        PeerEntry(component_name="B", category="x", display_name="B Comp", description="does b"),
        PeerEntry(component_name="Self", category="x", display_name="Self", description="ignored"),
    ]
    block = format_peers_block(peers, exclude="Self")
    lines = [line for line in block.splitlines() if line.strip()]
    assert lines == [
        "- A — A Comp — does a",
        "- B — B Comp — does b",
    ]


def test_format_peers_block_returns_placeholder_when_empty():
    assert format_peers_block([], exclude="X") == "(no peers in this category)"


def test_hand_authored_data_mapper_entry_present():
    """The DataMapper hand-authored entry is the canonical example."""
    assert "DataMapper" in HAND_AUTHORED_PEERS
    entry = HAND_AUTHORED_PEERS["DataMapper"]
    assert entry.category == "processing"
    assert "low cost" in entry.description.lower() or "precise" in entry.description.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_peers.py -v
```

Expected: ImportError — `scripts._agent_metadata_gen.peers` does not exist.

- [ ] **Step 3: Create `scripts/_agent_metadata_gen/__init__.py`**

```bash
touch scripts/_agent_metadata_gen/__init__.py
```

- [ ] **Step 4: Implement `peers.py`**

Create `scripts/_agent_metadata_gen/peers.py`:

```python
"""Peer-index construction for the agent_summary prompt.

A "peer" is a non-legacy component in the same category that the LLM can
legitimately reference when writing the optional 3rd-sentence tradeoff
("Prefer over <peer> when …"). Opted-out components (assist_enabled=False)
remain peer-eligible because they still appear in the canvas picker.
Hand-authored peers cover components that are worth referencing but have
no LLM-generated row of their own (currently DataMapper).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeerEntry:
    component_name: str
    category: str
    display_name: str
    description: str


HAND_AUTHORED_PEERS: dict[str, PeerEntry] = {
    "DataMapper": PeerEntry(
        component_name="DataMapper",
        category="processing",
        display_name="Data Mapper",
        description=(
            "Hyper-precise field-to-field mapping with an explicit schema and transforms. "
            "Very low cost per run; requires technical expertise to author the mapping. "
            "Has its own dedicated configuration agent."
        ),
    ),
}


def build_peer_index(
    classes: list[tuple[type, str]],
) -> dict[str, list[PeerEntry]]:
    """Group classes by category, applying the peer-eligibility rules.

    Eligibility:
    - ``getattr(cls, "legacy", False)`` is True -> EXCLUDED.
    - All others -> INCLUDED (opted-out components stay in the index).

    Hand-authored peers (e.g., DataMapper) are merged into the matching
    category after the class scan.

    Args:
        classes: list of ``(component_class, category)`` tuples produced
            by the walker / generator pipeline.

    Returns:
        ``{category: [PeerEntry, ...]}``. Each list is sorted by
        ``component_name`` for stable prompt output.
    """
    by_category: dict[str, list[PeerEntry]] = {}
    for cls, category in classes:
        if getattr(cls, "legacy", False):
            continue
        entry = PeerEntry(
            component_name=cls.__name__,
            category=category,
            display_name=str(getattr(cls, "display_name", cls.__name__) or cls.__name__),
            description=str(getattr(cls, "description", "") or "").strip(),
        )
        by_category.setdefault(category, []).append(entry)

    for hand_entry in HAND_AUTHORED_PEERS.values():
        by_category.setdefault(hand_entry.category, []).append(hand_entry)

    for category in by_category:
        by_category[category] = sorted(by_category[category], key=lambda p: p.component_name)

    return by_category


def format_peers_block(peers: list[PeerEntry], *, exclude: str) -> str:
    """Render the peer list for the prompt, one line per peer, excluding self.

    Returns ``"(no peers in this category)"`` when nothing remains after
    excluding the current component.
    """
    lines = [
        f"- {p.component_name} — {p.display_name} — {p.description}"
        for p in peers
        if p.component_name != exclude
    ]
    if not lines:
        return "(no peers in this category)"
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_peers.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Lint**

Run:

```bash
uv run ruff check scripts/_agent_metadata_gen/ tests/unit/agent_metadata_gen/
```

Expected: no errors.

- [ ] **Step 7: Commit (pause and ask the user first)**

```bash
git add scripts/_agent_metadata_gen/__init__.py \
        scripts/_agent_metadata_gen/peers.py \
        tests/unit/agent_metadata_gen/__init__.py \
        tests/unit/agent_metadata_gen/test_peers.py
git commit -m "feat(assist-gen): peer index with hand-authored DataMapper entry"
```

---

## Task 8: Build `synthesize.py` — prompts + per-call fallbacks

Two LLM calls per component (summary + usage notes), each with its own prompt template and metadata-only fallback.

**Files:**
- Create: `scripts/_agent_metadata_gen/synthesize.py`
- Create: `tests/unit/agent_metadata_gen/test_synthesize.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agent_metadata_gen/test_synthesize.py`:

```python
"""Tests for prompt construction + fallback behavior."""
from __future__ import annotations

from scripts._agent_metadata_gen.peers import PeerEntry
from scripts._agent_metadata_gen.synthesize import (
    build_summary_prompt,
    build_usage_notes_prompt,
    fallback_summary,
    fallback_usage_notes,
    synthesize_pair,
)
from scripts._assist_guide_gen.extract import ComponentMetadata, InputMetadata


def _meta(*, class_name="Comp", inputs=None, outputs=None):
    return ComponentMetadata(
        class_name=class_name,
        display_name="Comp Display",
        description="A comp.",
        documentation=None,
        docstring="",
        inputs=inputs or [],
        outputs=outputs or [],
    )


def test_summary_prompt_includes_class_inputs_outputs_and_peers():
    meta = _meta(
        inputs=[InputMetadata(name="prompt", info="user prompt", required=True)],
        outputs=["text"],
    )
    peers = [PeerEntry("Other", "models", "Other Comp", "does other")]
    prompt = build_summary_prompt(meta, peers, exclude="Comp")
    assert "Comp" in prompt
    assert "prompt" in prompt
    assert "text" in prompt
    assert "- Other — Other Comp — does other" in prompt
    assert "Comp Display" in prompt


def test_summary_prompt_excludes_self_from_peers():
    meta = _meta(class_name="Comp")
    peers = [
        PeerEntry("Comp", "models", "Comp Display", "self should not appear"),
        PeerEntry("Other", "models", "Other Comp", "does other"),
    ]
    prompt = build_summary_prompt(meta, peers, exclude="Comp")
    assert "self should not appear" not in prompt
    assert "Other" in prompt


def test_summary_prompt_handles_empty_peers():
    meta = _meta()
    prompt = build_summary_prompt(meta, [], exclude="Comp")
    assert "(no peers in this category)" in prompt


def test_usage_notes_prompt_marks_secret_and_advanced_inputs():
    """The prompt block exposes field_type/required/advanced so the LLM can decide which to bullet."""
    meta = _meta(
        inputs=[
            InputMetadata(name="prompt", info="user prompt", field_type="MessageTextInput", required=True),
            InputMetadata(name="api_key", info="LLM key", field_type="SecretStrInput", required=True),
            InputMetadata(name="advanced_knob", info="rare", field_type="IntInput", advanced=True),
        ],
    )
    prompt = build_usage_notes_prompt(meta)
    assert "SecretStrInput" in prompt
    assert "advanced=True" in prompt or "advanced=true" in prompt.lower()
    assert "required=True" in prompt or "required=true" in prompt.lower()
    assert "## What it does" in prompt
    assert "## Inputs to ask about" in prompt
    assert "## Outputs" in prompt
    assert "## Notes" in prompt


def test_fallback_summary_uses_display_name_and_description():
    meta = _meta(class_name="StructuredOutput")
    out = fallback_summary(meta)
    assert "Comp Display" in out
    assert "A comp." in out


def test_fallback_usage_notes_emits_all_four_headings():
    meta = _meta(
        inputs=[InputMetadata(name="prompt", info="user prompt", required=True)],
        outputs=["text"],
    )
    out = fallback_usage_notes(meta)
    assert "## What it does" in out
    assert "## Inputs to ask about" in out
    assert "## Outputs" in out
    assert "## Notes" in out
    assert "**prompt**" in out
    assert "**text**" in out


def test_synthesize_pair_uses_fallback_when_llm_returns_empty():
    """Both LLM calls return ''; both fallbacks fire and are tagged in status."""
    meta = _meta()
    def _llm(_prompt: str) -> str:
        return ""
    summary, summary_status, notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert "Comp Display" in summary
    assert summary_status == "fallback-used"
    assert "## What it does" in notes
    assert notes_status == "fallback-used"


def test_synthesize_pair_uses_llm_when_response_is_nonempty():
    meta = _meta()
    def _llm(prompt: str) -> str:
        if "configuration notes" in prompt:
            return "## What it does\nx\n## Inputs to ask about\n_None._\n## Outputs\n_None._\n## Notes\n_None._"
        return "Generated summary."
    summary, summary_status, notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert summary == "Generated summary."
    assert summary_status == "generated"
    assert "## What it does" in notes
    assert notes_status == "generated"


def test_synthesize_pair_mixed_outcomes():
    """One field generates, the other falls back."""
    meta = _meta()
    def _llm(prompt: str) -> str:
        return "Generated summary." if "summary of this component" in prompt else ""
    summary, summary_status, notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert summary_status == "generated"
    assert notes_status == "fallback-used"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_synthesize.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `synthesize.py`**

Create `scripts/_agent_metadata_gen/synthesize.py`:

```python
"""Prompt construction + LLM call orchestration for component agent metadata."""
from __future__ import annotations

import textwrap
from typing import Callable, Literal

from scripts._agent_metadata_gen.peers import PeerEntry, format_peers_block
from scripts._assist_guide_gen.extract import ComponentMetadata, InputMetadata

LLMCall = Callable[[str], str]
FieldStatus = Literal["generated", "fallback-used", "errored"]


_SUMMARY_PROMPT_TEMPLATE = """\
Write a 1-3 sentence summary of this component for an AI assistant
choosing it from a list of candidates.

Sentence 1 (required): what the component does. Be concrete - name the
thing it produces, transforms, or connects to.

Sentence 2 (optional): when this is a good fit, or what it pairs with.

Sentence 3 (optional, ONLY when one or more peers below genuinely
overlaps): the tradeoff. Format: "Prefer over <peer display name> when ...".
Use this only when you can articulate a clear, one-line "use this when ... /
use the peer when ..." distinction. If no peer materially overlaps, omit
sentence 3 - do not write filler.

Rules:
- Second person ("you help the user...").
- Don't repeat the display name verbatim.
- Don't invent capabilities not in the metadata.
- No marketing language. No markdown.
- 30-120 words. Return only the summary text.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}

Other components in the same category (peers):
{peers}
"""


_USAGE_NOTES_PROMPT_TEMPLATE = """\
Write configuration notes for an AI assistant configuring this
component. Use this exact markdown structure - emit each heading even
if a section is empty (write `_None._` in that case):

## What it does
One short paragraph (1-3 sentences).

## Inputs to ask about
- **<input_name>** - what to ask the user, plus a suggested default if
  one is obvious from the metadata.
- (one bullet per non-trivial input - skip inputs marked
  advanced=True unless they are commonly required; skip inputs whose
  field_type is SecretStrInput, since the assistant uses a separate
  variable-creation flow for those)

## Outputs
- **<output_name>** - what it produces and what it commonly feeds
  into.

## Notes
- Gotchas, constraints, or pairings worth flagging. Use `_None._` if
  nothing notable.

Rules:
- Second person ("ask the user...").
- Don't invent capabilities not in the metadata.
- One line per bullet - keep it scannable.
- 120-300 words.
- Return only the markdown body. No preamble, no fencing.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}
"""


def _format_inputs(meta: ComponentMetadata) -> str:
    if not meta.inputs:
        return "  (no declared inputs)"
    lines = []
    for i in meta.inputs:
        info = (i.info or "").replace("\n", " ").strip() or "(no description)"
        ftype = i.field_type or "Input"
        lines.append(
            f"  - {i.name} [field_type={ftype}, required={i.required}, advanced={i.advanced}]: {info}"
        )
    return "\n".join(lines)


def build_summary_prompt(
    meta: ComponentMetadata,
    peers: list[PeerEntry],
    *,
    exclude: str,
) -> str:
    return _SUMMARY_PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
        peers=format_peers_block(peers, exclude=exclude),
    )


def build_usage_notes_prompt(meta: ComponentMetadata) -> str:
    return _USAGE_NOTES_PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
    )


def fallback_summary(meta: ComponentMetadata) -> str:
    parts = [f"You help users with {meta.display_name or meta.class_name}."]
    if meta.description:
        parts.append(meta.description)
    return textwrap.fill(" ".join(parts), width=100)


def fallback_usage_notes(meta: ComponentMetadata) -> str:
    inputs_section_lines: list[str] = []
    for i in meta.inputs:
        if i.field_type == "SecretStrInput":
            continue
        if i.advanced and not i.required:
            continue
        prompt_text = (i.info or "").strip() or f"the value for `{i.name}`"
        inputs_section_lines.append(f"- **{i.name}** — ask the user for {prompt_text}.")
    if not inputs_section_lines:
        inputs_section_lines = ["_None._"]

    outputs_lines = [f"- **{name}** — produces upstream-typed output." for name in meta.outputs]
    if not outputs_lines:
        outputs_lines = ["_None._"]

    body = (
        f"## What it does\n{meta.description or '(no description)'}\n\n"
        f"## Inputs to ask about\n" + "\n".join(inputs_section_lines) + "\n\n"
        f"## Outputs\n" + "\n".join(outputs_lines) + "\n\n"
        f"## Notes\n_None._"
    )
    return body


def synthesize_pair(
    meta: ComponentMetadata,
    *,
    peers: list[PeerEntry],
    llm: LLMCall,
) -> tuple[str, FieldStatus, str, FieldStatus]:
    """Run the two LLM calls. Each falls back independently when the response is empty.

    Returns:
        ``(summary, summary_status, usage_notes, usage_notes_status)``.
    """
    summary_prompt = build_summary_prompt(meta, peers, exclude=meta.class_name)
    notes_prompt = build_usage_notes_prompt(meta)

    summary_raw = (llm(summary_prompt) or "").strip()
    if summary_raw:
        summary, summary_status = summary_raw, "generated"
    else:
        summary, summary_status = fallback_summary(meta), "fallback-used"

    notes_raw = (llm(notes_prompt) or "").strip()
    if notes_raw:
        notes, notes_status = notes_raw, "generated"
    else:
        notes, notes_status = fallback_usage_notes(meta), "fallback-used"

    return summary, summary_status, notes, notes_status
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_synthesize.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check scripts/_agent_metadata_gen/synthesize.py tests/unit/agent_metadata_gen/test_synthesize.py
```

Expected: no errors.

- [ ] **Step 6: Commit (pause and ask the user first)**

```bash
git add scripts/_agent_metadata_gen/synthesize.py tests/unit/agent_metadata_gen/test_synthesize.py
git commit -m "feat(assist-gen): synthesize summary + usage_notes with per-field fallback"
```

---

## Task 9: Build `emit.py` — YAML output and review report

Per-category YAML files; report row per component with two field-status columns.

**Files:**
- Create: `scripts/_agent_metadata_gen/emit.py`
- Create: `tests/unit/agent_metadata_gen/test_emit.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agent_metadata_gen/test_emit.py`:

```python
"""Tests for the YAML bundle writer + report writer."""
from __future__ import annotations

from pathlib import Path

import yaml as _yaml

from scripts._agent_metadata_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)


def test_bundle_grouped_by_category_and_sorted(tmp_path: Path):
    entries = [
        GuideEntry(category="models", component_name="Beta", agent_summary="b", agent_usage_notes="bn"),
        GuideEntry(category="models", component_name="Alpha", agent_summary="a", agent_usage_notes="an"),
        GuideEntry(category="processing", component_name="Charlie", agent_summary="c", agent_usage_notes="cn"),
    ]
    write_bundle(entries, tmp_path, overwrite=True)

    models_path = tmp_path / "models.yaml"
    proc_path = tmp_path / "processing.yaml"
    assert models_path.exists() and proc_path.exists()

    models = _yaml.safe_load(models_path.read_text())
    assert [e["component_name"] for e in models] == ["Alpha", "Beta"]


def test_bundle_skips_existing_when_overwrite_false(tmp_path: Path):
    """Existing entries with matching component_name are kept verbatim."""
    (tmp_path / "models.yaml").write_text(
        "- component_name: Alpha\n  agent_summary: original\n  agent_usage_notes: original\n"
    )
    entries = [
        GuideEntry(category="models", component_name="Alpha", agent_summary="new", agent_usage_notes="new"),
        GuideEntry(category="models", component_name="Beta", agent_summary="b", agent_usage_notes="bn"),
    ]
    write_bundle(entries, tmp_path, overwrite=False)
    bundle = _yaml.safe_load((tmp_path / "models.yaml").read_text())
    by_name = {e["component_name"]: e for e in bundle}
    assert by_name["Alpha"]["agent_summary"] == "original"
    assert by_name["Beta"]["agent_summary"] == "b"


def test_bundle_overwrites_when_overwrite_true(tmp_path: Path):
    (tmp_path / "models.yaml").write_text(
        "- component_name: Alpha\n  agent_summary: original\n  agent_usage_notes: original\n"
    )
    entries = [
        GuideEntry(category="models", component_name="Alpha", agent_summary="new", agent_usage_notes="new"),
    ]
    write_bundle(entries, tmp_path, overwrite=True)
    bundle = _yaml.safe_load((tmp_path / "models.yaml").read_text())
    assert bundle[0]["agent_summary"] == "new"


def test_review_report_writes_markdown_table(tmp_path: Path):
    rows = [
        ReportRow(
            component_name="Alpha",
            category="models",
            metadata_completeness="rich",
            outcome="processed",
            summary_status="generated",
            usage_status="generated",
        ),
        ReportRow(
            component_name="Beta",
            category="models",
            metadata_completeness="thin",
            outcome="processed",
            summary_status="generated",
            usage_status="fallback-used",
        ),
        ReportRow(
            component_name="DataMapper",
            category="processing",
            metadata_completeness="rich",
            outcome="skipped-opted-out",
            summary_status="n/a",
            usage_status="n/a",
        ),
    ]
    out = tmp_path / "report.md"
    write_review_report(rows, out)
    text = out.read_text()
    assert "| Alpha | models | rich | processed | generated | generated |" in text
    assert "| Beta | models | thin | processed | generated | fallback-used |" in text
    assert "| DataMapper | processing | rich | skipped-opted-out | n/a | n/a |" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_emit.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `emit.py`**

Create `scripts/_agent_metadata_gen/emit.py`:

```python
"""Emit per-category YAML bundles and a markdown review report."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml as _yaml


@dataclass(frozen=True)
class GuideEntry:
    category: str
    component_name: str
    agent_summary: str
    agent_usage_notes: str


@dataclass(frozen=True)
class ReportRow:
    component_name: str
    category: str
    metadata_completeness: Literal["rich", "thin"] | str
    outcome: Literal[
        "processed", "skipped-opted-out", "skipped-legacy", "skipped-existing", "errored"
    ] | str
    summary_status: Literal["generated", "fallback-used", "errored", "n/a"] | str
    usage_status: Literal["generated", "fallback-used", "errored", "n/a"] | str


class _LiteralStr(str):
    """A str subclass rendered with literal block scalar (`|`) for readability."""


def _literal_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


_yaml.add_representer(_LiteralStr, _literal_presenter)


def write_bundle(entries: list[GuideEntry], out_dir: Path, *, overwrite: bool) -> None:
    """Write per-category YAML files. Entries within each file are sorted by component_name.

    When ``overwrite=False``, existing entries with a matching ``component_name`` are
    preserved verbatim (read from the file on disk before merging in new entries).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[GuideEntry]] = defaultdict(list)
    for e in entries:
        grouped[e.category].append(e)

    for category, new_entries in grouped.items():
        path = out_dir / f"{category}.yaml"
        existing_by_name: dict[str, dict] = {}
        if path.exists():
            try:
                raw = _yaml.safe_load(path.read_text()) or []
                if isinstance(raw, list):
                    for entry in raw:
                        if isinstance(entry, dict) and "component_name" in entry:
                            existing_by_name[entry["component_name"]] = entry
            except _yaml.YAMLError:
                # Malformed file - we'll overwrite it.
                existing_by_name = {}

        merged: dict[str, dict] = dict(existing_by_name)
        for e in new_entries:
            if e.component_name in existing_by_name and not overwrite:
                continue
            merged[e.component_name] = {
                "component_name": e.component_name,
                "agent_summary": _LiteralStr(e.agent_summary),
                "agent_usage_notes": _LiteralStr(e.agent_usage_notes),
            }

        ordered = sorted(merged.values(), key=lambda d: d["component_name"])
        path.write_text(
            _yaml.dump(
                ordered,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )
        )


def write_review_report(rows: list[ReportRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Component Agent Metadata Generation Report\n\n"
        "| Component | Category | Completeness | Outcome | Summary Status | Usage Status |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )
    body_lines = []
    for r in sorted(rows, key=lambda x: (x.category, x.component_name)):
        body_lines.append(
            f"| {r.component_name} | {r.category} | {r.metadata_completeness} | "
            f"{r.outcome} | {r.summary_status} | {r.usage_status} |"
        )
    path.write_text(header + "\n".join(body_lines) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_emit.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check scripts/_agent_metadata_gen/emit.py tests/unit/agent_metadata_gen/test_emit.py
```

Expected: no errors.

- [ ] **Step 6: Commit (pause and ask the user first)**

```bash
git add scripts/_agent_metadata_gen/emit.py tests/unit/agent_metadata_gen/test_emit.py
git commit -m "feat(assist-gen): emit per-category YAML + per-field-status review report"
```

---

## Task 10: Build the generator entry point

The CLI: argparse, walk components, build peer index, run synthesis with concurrency, write bundle + report.

**Files:**
- Create: `scripts/generate_component_agent_metadata.py`
- Create: `tests/unit/agent_metadata_gen/test_filters.py` (covers the filter rules at the script's `_process_one` level)

- [ ] **Step 1: Write failing tests for the filter rules**

Create `tests/unit/agent_metadata_gen/test_filters.py`:

```python
"""Tests for the per-class filter rules used by the generator entry point."""
from __future__ import annotations

from typing import ClassVar

from scripts._agent_metadata_gen import generate as gen


class _OptedOut:
    assist_enabled: ClassVar[bool] = False
    legacy: ClassVar[bool] = False
    display_name = "Opted Out"
    description = "opted out"
    inputs = []
    outputs = []


class _Legacy:
    assist_enabled: ClassVar[bool] = True
    legacy: ClassVar[bool] = True
    display_name = "Legacy"
    description = "legacy"
    inputs = []
    outputs = []


class _Eligible:
    display_name = "Eligible"
    description = "eligible"
    inputs = []
    outputs = []


def test_decide_outcome_skips_opted_out():
    outcome = gen.decide_outcome(_OptedOut, existing_types=set(), overwrite=False)
    assert outcome == "skipped-opted-out"


def test_decide_outcome_skips_legacy():
    outcome = gen.decide_outcome(_Legacy, existing_types=set(), overwrite=False)
    assert outcome == "skipped-legacy"


def test_decide_outcome_skips_existing_when_no_overwrite():
    outcome = gen.decide_outcome(
        _Eligible, existing_types={"_Eligible"}, overwrite=False,
    )
    assert outcome == "skipped-existing"


def test_decide_outcome_overwrite_processes_existing():
    outcome = gen.decide_outcome(
        _Eligible, existing_types={"_Eligible"}, overwrite=True,
    )
    assert outcome == "processed"


def test_decide_outcome_processes_new_eligible():
    outcome = gen.decide_outcome(
        _Eligible, existing_types=set(), overwrite=False,
    )
    assert outcome == "processed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_filters.py -v
```

Expected: ImportError — `scripts._agent_metadata_gen.generate` does not exist.

- [ ] **Step 3: Create a small importable module + the CLI script**

Create `scripts/_agent_metadata_gen/generate.py` (importable; the CLI script imports from here):

```python
"""Core generator logic, importable from tests."""
from __future__ import annotations

from typing import Literal

from langflow.services.component_assist.guide_registry import is_assist_enabled

Outcome = Literal[
    "processed", "skipped-opted-out", "skipped-legacy", "skipped-existing"
]


def decide_outcome(
    cls: type,
    *,
    existing_types: set[str],
    overwrite: bool,
) -> Outcome:
    """Apply the per-class filter rules in priority order."""
    if not is_assist_enabled(cls):
        return "skipped-opted-out"
    if getattr(cls, "legacy", False):
        return "skipped-legacy"
    if cls.__name__ in existing_types and not overwrite:
        return "skipped-existing"
    return "processed"
```

Create `scripts/generate_component_agent_metadata.py`:

```python
#!/usr/bin/env python
"""Generate starter agent_summary + agent_usage_notes for every assist-enabled,
non-legacy Langflow component.

Run from repo root. See ``--help`` for flags.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure repo root is on sys.path so the sibling `scripts._agent_metadata_gen` package resolves
# when this file is invoked as a script (`python scripts/generate_...`).
_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from scripts._agent_metadata_gen.emit import GuideEntry, ReportRow, write_bundle, write_review_report
from scripts._agent_metadata_gen.generate import decide_outcome
from scripts._agent_metadata_gen.peers import PeerEntry, build_peer_index
from scripts._agent_metadata_gen.synthesize import synthesize_pair
from scripts._assist_guide_gen.extract import extract_metadata, metadata_completeness
from scripts._assist_guide_gen.walker import FileCandidate, iter_all

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOTS = (
    REPO_ROOT / "src/lfx/src/lfx/components",
    REPO_ROOT / "src/backend/base/langflow/components",
)
BUNDLE_DIR = REPO_ROOT / "src/backend/base/langflow/services/component_assist/agent_metadata"
REPORT_PATH = REPO_ROOT / "docs/component-agent-metadata-generation-report.md"


def _find_component_classes(candidate: FileCandidate) -> list[type]:
    module_name = f"_agent_metadata_module_{candidate.path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, candidate.path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return []

    from lfx.custom.custom_component.component import Component  # heavy import

    out: list[type] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if not issubclass(obj, Component) or obj is Component:
            continue
        out.append(obj)
    return out


def _build_llm():
    """Return a callable ``(prompt: str) -> str`` backed by the Anthropic SDK."""
    import anthropic

    client = anthropic.Anthropic()

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    return call


def _existing_bundle_types(bundle_dir: Path) -> set[str]:
    import yaml as _yaml

    types: set[str] = set()
    if not bundle_dir.is_dir():
        return types
    for path in bundle_dir.glob("*.yaml"):
        raw = _yaml.safe_load(path.read_text()) or []
        if isinstance(raw, list):
            types.update(
                e["component_name"] for e in raw if isinstance(e, dict) and "component_name" in e
            )
    return types


def _scan_classes(candidates: list[FileCandidate]) -> list[tuple[type, str]]:
    """Discover all component classes across candidates. Returns (class, category) pairs."""
    out: list[tuple[type, str]] = []
    for candidate in candidates:
        for cls in _find_component_classes(candidate):
            out.append((cls, candidate.category))
    return out


def _process_one_class(
    cls: type,
    category: str,
    *,
    existing_types: set[str],
    overwrite: bool,
    peers: list[PeerEntry],
    llm,
) -> tuple[GuideEntry | None, ReportRow]:
    outcome = decide_outcome(cls, existing_types=existing_types, overwrite=overwrite)
    if outcome != "processed":
        return None, ReportRow(
            component_name=cls.__name__,
            category=category,
            metadata_completeness="n/a",
            outcome=outcome,
            summary_status="n/a",
            usage_status="n/a",
        )

    meta = extract_metadata(cls)
    completeness = metadata_completeness(meta)
    try:
        summary, summary_status, notes, notes_status = synthesize_pair(
            meta, peers=peers, llm=llm,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"! {cls.__name__}: {exc}", file=sys.stderr)
        return None, ReportRow(
            component_name=cls.__name__,
            category=category,
            metadata_completeness=completeness,
            outcome="errored",
            summary_status="errored",
            usage_status="errored",
        )

    entry = GuideEntry(
        category=category,
        component_name=cls.__name__,
        agent_summary=summary,
        agent_usage_notes=notes,
    )
    row = ReportRow(
        component_name=cls.__name__,
        category=category,
        metadata_completeness=completeness,
        outcome="processed",
        summary_status=summary_status,
        usage_status=notes_status,
    )
    return entry, row


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate component agent_summary + agent_usage_notes.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing entries.")
    parser.add_argument("--category", help="Restrict generation to one top-level category.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    candidates = list(iter_all(COMPONENT_ROOTS))
    if args.category:
        candidates = [c for c in candidates if c.category == args.category]

    if args.dry_run:
        print(
            f"Would process {len(candidates)} files across "
            f"{len({c.category for c in candidates})} categories."
        )
        return 0

    # Scan all classes across all candidates first so the peer index is complete.
    print(f"Scanning {len(candidates)} files for component classes...")
    classes = _scan_classes(candidates)
    print(f"Discovered {len(classes)} component classes.")

    peer_index = build_peer_index(classes)
    existing_types = _existing_bundle_types(BUNDLE_DIR)
    llm = _build_llm()

    all_entries: list[GuideEntry] = []
    all_rows: list[ReportRow] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                _process_one_class,
                cls,
                category,
                existing_types=existing_types,
                overwrite=args.overwrite,
                peers=peer_index.get(category, []),
                llm=llm,
            ): (cls, category)
            for cls, category in classes
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            cls, category = futures[fut]
            try:
                entry, row = fut.result()
            except Exception as exc:
                print(f"!! {cls.__name__} ({category}): {exc}", file=sys.stderr)
                if args.fail_fast:
                    return 1
                continue
            if entry is not None:
                all_entries.append(entry)
            all_rows.append(row)
            print(f"[{i}/{len(classes)}] {category}/{cls.__name__} -> {row.outcome}")

    write_bundle(all_entries, BUNDLE_DIR, overwrite=args.overwrite)
    write_review_report(all_rows, REPORT_PATH)
    print(f"\nWrote {len(all_entries)} bundle entries to {BUNDLE_DIR}")
    print(f"Review report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run filter tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/agent_metadata_gen/test_filters.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run a `--dry-run` against the real component tree**

Run:

```bash
uv run python scripts/generate_component_agent_metadata.py --dry-run
```

Expected: prints something like `"Would process N files across M categories."` with non-trivial N and M (today: ~419 files across ~50 categories). No errors. No files written.

- [ ] **Step 6: Lint**

Run:

```bash
uv run ruff check scripts/_agent_metadata_gen/generate.py scripts/generate_component_agent_metadata.py tests/unit/agent_metadata_gen/test_filters.py
```

Expected: no errors.

- [ ] **Step 7: Commit (pause and ask the user first)**

```bash
git add scripts/_agent_metadata_gen/generate.py \
        scripts/generate_component_agent_metadata.py \
        tests/unit/agent_metadata_gen/test_filters.py
git commit -m "feat(assist-gen): generator entry point + filter rules"
```

---

## Task 11: Run a real generation against a single category and review output

Smoke-test the full pipeline against one small category. Confirms LLM integration, YAML output, and DB seeding all work end-to-end. Pick a small, well-described category for the smoke run (e.g., `inputs/` or `outputs/`) — keep token spend low.

This task does NOT generate the full catalog. That's deferred to Task 12 (its own commit) so this PR doesn't pre-commit hundreds of LLM-authored YAML entries before review.

**Files:**
- Create (generated): `src/backend/base/langflow/services/component_assist/agent_metadata/inputs.yaml` (or whichever category is chosen)
- Create (generated): `docs/component-agent-metadata-generation-report.md`

- [ ] **Step 1: Confirm `ANTHROPIC_API_KEY` is set in the environment**

Run:

```bash
echo "ANTHROPIC_API_KEY length: ${#ANTHROPIC_API_KEY}"
```

Expected: a non-zero length. If 0, ask the user to export the key before continuing.

- [ ] **Step 2: Pick a category and inspect its size**

Run:

```bash
ls src/lfx/src/lfx/components/inputs src/backend/base/langflow/components/inputs 2>/dev/null
```

Expected: a small list (target: under 10 components for the smoke run). If `inputs/` is too large or empty, pick another small category from the dry-run output.

- [ ] **Step 3: Run the generator against the chosen category**

Run (replace `inputs` with the chosen category):

```bash
uv run python scripts/generate_component_agent_metadata.py --category inputs --concurrency 3
```

Expected: progress lines per component, ending with `"Wrote N bundle entries to …"` and a path to the report.

- [ ] **Step 4: Manually review the generated YAML**

Open `src/backend/base/langflow/services/component_assist/agent_metadata/inputs.yaml`. Spot-check 3 entries:
- `agent_summary`: 1–3 sentences, references real peers when present, no hallucinated capabilities.
- `agent_usage_notes`: all four headings present, secret inputs not bullet-listed under "Inputs to ask about".

If any entry looks wrong, hand-edit it. The whole point of the YAML-in-source-control workflow is that humans review LLM output before it lands.

- [ ] **Step 5: Boot the app and confirm seeding picks up the new YAML**

Run:

```bash
uv run langflow run --host 127.0.0.1 --port 7860 --no-open-browser &
LANGFLOW_PID=$!
sleep 8
curl -sf http://127.0.0.1:7860/health > /dev/null && echo "OK"
kill $LANGFLOW_PID
```

Then check the DB. Pick one component_name from the YAML (e.g., `ChatInput`) and run a small query (use whatever DB URL the app uses; default SQLite is at `~/.langflow/database.db` or wherever `LANGFLOW_DATABASE_URL` points):

```bash
uv run python -c "
import asyncio
from sqlmodel import select
from langflow.services.deps import session_scope
from langflow.services.database.models.component_metadata.model import ComponentMetadata

async def main():
    async with session_scope() as session:
        rows = (await session.exec(select(ComponentMetadata).where(ComponentMetadata.component_name == 'ChatInput'))).all()
        for r in rows:
            print(r.component_name, '|', (r.agent_summary or '')[:60])

asyncio.run(main())
"
```

Expected: prints `ChatInput | <first 60 chars of the agent_summary>`. If empty, the seeder either didn't run or didn't pick up the file — debug logs at startup should explain.

- [ ] **Step 6: Run the full backend test suite**

Run:

```bash
uv run pytest src/backend/tests/unit/services/component_assist/ src/backend/tests/unit/initial_setup/ tests/unit/agent_metadata_gen/ tests/unit/assist_guide_gen/ -v
```

Expected: all PASS. If any test surface added in Tasks 2–10 fails, fix before committing.

- [ ] **Step 7: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/services/component_assist/agent_metadata/inputs.yaml \
        docs/component-agent-metadata-generation-report.md
git commit -m "data(assist): seed agent metadata for inputs/ category (smoke run)"
```

---

## Task 12: Generate the full catalog (deferred — separate change)

This task is intentionally separate from Tasks 1–11. The implementation is plumbing; this is content. Run when ready.

**Files:**
- Create (generated): `src/backend/base/langflow/services/component_assist/agent_metadata/*.yaml` for every remaining category.
- Update (generated): `docs/component-agent-metadata-generation-report.md`

- [ ] **Step 1: Confirm Tasks 1–11 are merged or staged on the branch**

Run:

```bash
git log --oneline -15
```

Expected: commits from Tasks 2–11 are present. (If running from a fresh branch off platform-multi-tenant, ensure no plumbing pieces are missing.)

- [ ] **Step 2: Run the full generation**

Run:

```bash
uv run python scripts/generate_component_agent_metadata.py --concurrency 5
```

Expected: ~400 progress lines, ending with the bundle and report paths. Token spend is roughly 2 calls × ~400 components ≈ 800 LLM calls.

- [ ] **Step 3: Review the report**

Open `docs/component-agent-metadata-generation-report.md`. Sort visually by `outcome != processed` and `summary_status != generated`. For each row that's `errored`, investigate (check stderr from the run) and re-run with `--category <that-category>`. For `fallback-used`, hand-edit the YAML if the metadata-only stub is too thin to be useful.

- [ ] **Step 4: Spot-check ~10 random entries across categories**

Pick at least one entry from each of: `models/`, `agents/`, `processing/`, `inputs/`, `outputs/`, `vectorstores/`, `tools/`. Read both `agent_summary` and `agent_usage_notes`. Flag and hand-edit anything that:
- Hallucinates a capability not in the metadata.
- References a peer that doesn't actually exist in that category.
- Bullets a secret input under "Inputs to ask about".

- [ ] **Step 5: Re-run only categories where edits were made (optional)**

If you hand-edited entries and want to keep them, that's fine — the bundle is now your edits + LLM output. If you regenerate later, pass `--overwrite` only with caution.

- [ ] **Step 6: Boot the app and confirm seed counts match**

Run:

```bash
uv run langflow run --host 127.0.0.1 --port 7860 --no-open-browser &
LANGFLOW_PID=$!
sleep 10
kill $LANGFLOW_PID
```

Look for the log line `"Component agent metadata seed: inserted N, re-seeded M, skipped K (admin-owned)."` — `inserted + re-seeded` should approximately match the number of YAML entries.

- [ ] **Step 7: Commit (pause and ask the user first)**

```bash
git add src/backend/base/langflow/services/component_assist/agent_metadata/ \
        docs/component-agent-metadata-generation-report.md
git commit -m "data(assist): seed agent metadata for full component catalog"
```

---

## Self-Review

Spec coverage check (each spec section / requirement → task):

- **Storage form (hybrid YAML + DB seeder)** → Tasks 3 (dir), 5 (seeder), 9 (YAML emit), 11/12 (content).
- **Scope filter (assist-enabled, non-legacy)** → Task 10 (`decide_outcome`); Task 7 (peer eligibility — opted-out kept, legacy excluded).
- **Relationship to assist_guide (DB-first fallback)** → Task 4 (`resolve` becomes async, DB-first).
- **`agent_usage_notes` shape (markdown w/ fixed headings)** → Task 8 (prompt + fallback both emit the four headings).
- **`agent_summary` shape (1–3 sentences, optional 3rd-sentence tradeoff)** → Task 8 (prompt copy + peer-context block).
- **Generation pipeline (LLM-driven, concurrent, dry-run, overwrite, category, fail-fast)** → Task 10 (CLI).
- **Per-field fallback status reporting** → Task 8 (`synthesize_pair` returns two statuses) + Task 9 (`ReportRow` has both columns).
- **Three-state seeder upsert (`updated_by` ownership)** → Task 5 (insert / re-seed-if-null / skip-if-owned + IntegrityError swallow).
- **Lifespan wiring** → Task 6 (`main.py` after `create_or_update_template_metadata`).
- **Hand-authored peer hint for DataMapper** → Task 7 (`HAND_AUTHORED_PEERS`).
- **Resolver tests (DB → class → YAML → None)** → Task 4 (5 cases).
- **Seeder tests (insert / re-seed / skip / malformed / no-yaml)** → Task 5 (5 cases).
- **Generator tests (filters, peers, prompts, fallbacks, emit)** → Tasks 7, 8, 9, 10.

Placeholder scan: no `TBD` / `TODO` / `add appropriate error handling` / `similar to Task N`. Code blocks are complete. Commands are exact.

Type consistency: `GuideEntry`, `ReportRow`, `PeerEntry`, `ComponentMetadata`, `InputMetadata`, `synthesize_pair`'s tuple shape, `decide_outcome`'s `Outcome` literal, and `create_or_update_component_agent_metadata`'s signature are referenced consistently across tasks.
