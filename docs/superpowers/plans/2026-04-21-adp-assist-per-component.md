# ADP Assist · Per-Component (Infrastructure) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the per-component ephemeral ADP Assist feature end-to-end: the Assist icon in each node toolbar opens an ephemeral chat popover scoped to configuring that single component. Includes a class-level opt-out (`assist_enabled: ClassVar[bool] = False`) that is applied to `DataMapperComponent` — DataMapper has its own bespoke agent and must NOT be touched by this feature. One high-traffic non-excluded component (e.g., `TextOperationsComponent`) gets a hand-authored `assist_guide` to validate the class-attribute priority path. Excludes the bulk generator for the remaining ~400 component guides — that ships in a follow-up plan (`2026-04-21-adp-assist-bulk-guide-generator.md`).

**⚠ Important — do not touch DataMapper work:** `DataMapperComponent` has its own dedicated agent under active development. For this plan, DataMapper-related changes are limited to adding exactly one class attribute (`assist_enabled: ClassVar[bool] = False`) on the `DataMapperComponent` class. Do not modify its inputs, outputs, config schema, transforms, engine, or any `_data_mapper/` internals. If a task here seems to require deeper DataMapper changes, stop and raise it.

**Architecture:** A new stateless SSE endpoint (`POST /api/v1/assistant/components/messages`) streams LLM responses and `propose_config_update` tool calls. A new `ComponentAssistService` resolves an `assist_guide` for the target node (class attribute → YAML bundle → generic), builds a scoped system prompt from the node + direct-neighbor snapshots, and streams events. On the frontend, a new zustand-backed popover renders a chat UI with inline proposal blocks; Apply mutates the flow store via the existing `setNode` path.

**Tech Stack:** Python 3.11+, FastAPI, `sse-starlette`, Pydantic, anyio, pytest. React + TypeScript, Zustand v5 (use `useShallow` for composite selectors — see project memory), Tailwind v4 (CSS-first config), Jest + `@testing-library/react`.

**Source spec:** `docs/superpowers/specs/2026-04-21-adp-assist-per-component-design.md` (committed as `bfea379b76`).

**Follow-up plan:** `2026-04-21-adp-assist-bulk-guide-generator.md` (populates starter guides for the ~400 other user-facing components).

---

## File structure

**Create (backend):**

| File | Responsibility |
|---|---|
| `src/backend/base/langflow/api/v1/component_assist.py` | FastAPI router: `POST /api/v1/assistant/components/messages` (SSE). |
| `src/backend/base/langflow/services/component_assist/__init__.py` | Package marker + public re-exports. |
| `src/backend/base/langflow/services/component_assist/schemas.py` | Pydantic: `NodeSnapshot`, `ThreadMessage`, `ComponentAssistRequest`, `ProposeConfigUpdate`. |
| `src/backend/base/langflow/services/component_assist/guide_registry.py` | Resolves guide: class attribute → YAML bundle → `None`. Caches YAML bundle. |
| `src/backend/base/langflow/services/component_assist/prompt.py` | Generic base system prompt + guide-injection + snapshot rendering. |
| `src/backend/base/langflow/services/component_assist/service.py` | `ComponentAssistService.stream_reply()` — SSE event generator. |
| `src/backend/base/langflow/services/component_assist/guides/.gitkeep` | Empty placeholder so the directory exists for Plan 2 to populate. |

**Create (frontend):**

| File | Responsibility |
|---|---|
| `src/frontend/src/stores/componentAssistStore.ts` | Zustand store: `activeNodeId`, `anchorRect`, `position`, `size`, `thread`, `isStreaming`, open/close/abort. |
| `src/frontend/src/modals/ComponentAssistPopover/index.tsx` | Popover shell: drag, resize, chat area, input, footer notice. |
| `src/frontend/src/modals/ComponentAssistPopover/hooks/use-component-assist-stream.ts` | POST + SSE consumption with `AbortController`. |
| `src/frontend/src/modals/ComponentAssistPopover/components/ProposalBlock.tsx` | Inline diff card with Apply / Dismiss. |
| `src/frontend/src/modals/ComponentAssistPopover/types.ts` | Shared TS types (`ThreadMessage`, `ProposalPayload`). |

**Create (tests):**

| File | Covers |
|---|---|
| `src/backend/tests/unit/services/component_assist/__init__.py` | Package marker. |
| `src/backend/tests/unit/services/component_assist/test_schemas.py` | Pydantic validation. |
| `src/backend/tests/unit/services/component_assist/test_guide_registry.py` | Class-attr / YAML / missing resolution. |
| `src/backend/tests/unit/services/component_assist/test_prompt.py` | Guide injection + snapshot rendering. |
| `src/backend/tests/unit/services/component_assist/test_service.py` | Streaming event order + invalid-patch retry. |
| `src/backend/tests/unit/api/v1/test_component_assist_endpoint.py` | Auth (403/404) + happy-path SSE. |
| `src/backend/tests/integration/test_component_assist_smoke.py` | Fixture flow `Source → DataMapper`, proposal → Apply. |
| `src/frontend/src/stores/__tests__/componentAssistStore.test.ts` | Store behavior. |
| `src/frontend/src/modals/ComponentAssistPopover/__tests__/use-component-assist-stream.test.ts` | SSE parsing + abort. |
| `src/frontend/src/modals/ComponentAssistPopover/__tests__/ProposalBlock.test.tsx` | Diff render + Apply / Dismiss. |
| `src/frontend/src/modals/ComponentAssistPopover/__tests__/ComponentAssistPopover.test.tsx` | Greeting + drag + close. |

**Modify:**

| File | Change |
|---|---|
| `src/frontend/src/style/index.css` | Add `--color-adp-red: 353 85% 52%;` inside `:root` HSL block (matches existing `hsl(var(...))` convention). |
| `src/backend/base/langflow/api/router.py` | Include `component_assist_router` under `/api/v1`. |
| `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx` | Add `ToolbarButton` for Assist, wired to `componentAssistStore.open(nodeId, anchorRect)`. |
| `src/lfx/src/lfx/components/processing/data_mapper.py` | Add exactly one line: `assist_enabled: ClassVar[bool] = False`. **No other changes.** |
| `src/lfx/src/lfx/components/processing/text_operations.py` (or similar) | Add a hand-authored `assist_guide: ClassVar[str]` as the reference example for the class-attribute priority path. |

---

## Commands used throughout

- **Run backend tests (single file):** `uv run pytest src/backend/tests/unit/services/component_assist/test_<name>.py -v` (from repo root)
- **Run frontend tests (single file):** `cd src/frontend && npm test -- --testPathPattern=componentAssistStore`
- **Start dev server (to exercise the UI):** `make backend` + `make frontend` (separate terminals)
- **Lint backend:** `uv run ruff check src/backend/base/langflow/services/component_assist`
- **Lint frontend:** `cd src/frontend && npm run lint`

Memory callouts to respect during execution:
- Pause before every `git commit` (project has "no commits without permission" preference).
- Zustand v5: wrap composite selectors with `useShallow` to avoid snapshot-equality loops.
- Tailwind v4 is CSS-first — define the CSS variable in `src/frontend/src/style/index.css`, no `tailwind.config.mjs` edits.
- Jest (not Vitest); react-query v5 uses `isPending` (not `isLoading`) if needed.
- ADP red `#ED1C2E` ≈ `hsl(353, 85%, 52%)`. Never substitute `--destructive`.

---

## Task 1: Define the ADP red CSS variable

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Locate the `:root` HSL variable block**

Open `src/frontend/src/style/index.css` and find the `:root` block that defines variables like `--primary`, `--destructive` in HSL triples (around line ~450 based on prior greps). Variables are stored as three space-separated numbers so they can be consumed via `hsl(var(--name))`.

- [ ] **Step 2: Add `--color-adp-red`**

Add these two lines alongside the existing accent tokens (place near `--accent-red-foreground`):

```css
    --adp-red: 353 85% 52%; /* hsl(353, 85%, 52%) ≈ #ED1C2E — ADP brand red */
    --adp-red-foreground: 0 0% 100%; /* white text on ADP red */
```

Then, in the `@theme inline { }` block at the top of the file (where `--color-*` aliases are declared), add:

```css
  --color-adp-red: hsl(var(--adp-red));
  --color-adp-red-foreground: hsl(var(--adp-red-foreground));
```

- [ ] **Step 3: Smoke-check in the dev server**

Run `cd src/frontend && npm run dev`. Open http://localhost:3000, inspect any element, add the class `bg-adp-red` in DevTools, and confirm it renders as `#ED1C2E`. Kill the dev server when done.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/style/index.css
git commit -m "feat(style): add ADP brand-red CSS variable for assistant surfaces"
```

---

## Task 2: Backend Pydantic schemas

**Files:**
- Create: `src/backend/base/langflow/services/component_assist/__init__.py`
- Create: `src/backend/base/langflow/services/component_assist/schemas.py`
- Create: `src/backend/tests/unit/services/component_assist/__init__.py`
- Create: `src/backend/tests/unit/services/component_assist/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/services/component_assist/test_schemas.py`:

```python
"""Validation tests for ComponentAssist request/tool schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    NodeSnapshot,
    ProposeConfigUpdate,
    ThreadMessage,
)


def _snapshot(node_id: str = "n1", ctype: str = "DataMapperComponent") -> NodeSnapshot:
    return NodeSnapshot(
        node_id=node_id,
        type=ctype,
        display_name="Data Mapper",
        description="Maps fields",
        template={"mapping": {"display_name": "Mapping", "value": {}}},
        outputs=[{"name": "out", "types": ["Data"]}],
    )


def test_request_minimum_valid():
    req = ComponentAssistRequest(
        flow_id="11111111-1111-1111-1111-111111111111",
        node_id="n1",
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        thread=[],
        user_message="hi",
    )
    assert req.node_id == "n1"


def test_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ComponentAssistRequest(
            flow_id="11111111-1111-1111-1111-111111111111",
            node_id="n1",
            node_snapshot=_snapshot(),
            neighbor_snapshots=[],
            thread=[],
            user_message="",
        )


def test_thread_message_roles():
    assert ThreadMessage(role="user", content="x").role == "user"
    assert ThreadMessage(role="assistant", content="x").role == "assistant"
    with pytest.raises(ValidationError):
        ThreadMessage(role="system", content="x")  # system not allowed on the wire


def test_propose_config_update_requires_node_id_and_patch():
    tool = ProposeConfigUpdate(node_id="n1", patch={"a": 1}, rationale="because")
    assert tool.patch == {"a": 1}
    with pytest.raises(ValidationError):
        ProposeConfigUpdate(node_id="n1", patch="nope", rationale="x")  # patch must be dict
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_schemas.py -v
```
Expected: `ModuleNotFoundError` or collection errors — the module doesn't exist yet.

- [ ] **Step 3: Implement the schemas**

Create `src/backend/base/langflow/services/component_assist/__init__.py`:

```python
"""Per-component ephemeral assistant service."""
```

Create `src/backend/base/langflow/services/component_assist/schemas.py`:

```python
"""Pydantic schemas for the per-component ephemeral assistant."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NodeSnapshot(BaseModel):
    """Trimmed node view — enough for schema/value reasoning, no styling/layout."""

    node_id: str
    type: str                         # component class name, e.g. "DataMapperComponent"
    display_name: str
    description: str | None = None
    template: dict[str, Any] = Field(default_factory=dict)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class ThreadMessage(BaseModel):
    """A single prior turn. System messages are built server-side; not accepted on the wire."""

    role: Literal["user", "assistant"]
    content: str
    # Optional list of tool calls the assistant previously emitted (so the model sees
    # its own past proposals when reasoning this turn).
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ComponentAssistRequest(BaseModel):
    flow_id: UUID
    node_id: str
    node_snapshot: NodeSnapshot
    neighbor_snapshots: list[NodeSnapshot] = Field(default_factory=list)
    thread: list[ThreadMessage] = Field(default_factory=list)
    user_message: str

    @field_validator("user_message")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "user_message must be non-empty"
            raise ValueError(msg)
        return v


class ProposeConfigUpdate(BaseModel):
    """The single tool the model may call. Patch is a field_name → new_value map."""

    node_id: str
    patch: dict[str, Any]
    rationale: str = ""
```

- [ ] **Step 4: Create the test package marker**

Create `src/backend/tests/unit/services/component_assist/__init__.py` (empty file).

- [ ] **Step 5: Run tests and confirm they pass**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_schemas.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/component_assist/ \
        src/backend/tests/unit/services/component_assist/
git commit -m "feat(component-assist): request/tool pydantic schemas"
```

---

## Task 3: Guide registry (class-attr → YAML → None)

**Files:**
- Create: `src/backend/base/langflow/services/component_assist/guide_registry.py`
- Create: `src/backend/base/langflow/services/component_assist/guides/.gitkeep` (empty)
- Create: `src/backend/tests/unit/services/component_assist/test_guide_registry.py`

- [ ] **Step 1: Write the failing test**

Create the test file:

```python
"""Tests for the component assist guide registry."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from langflow.services.component_assist import guide_registry


class _FakeWithGuide:
    assist_guide: ClassVar[str] = "inline guide for fake component"


class _FakeWithoutGuide:
    pass


def test_class_attribute_takes_priority(monkeypatch: pytest.MonkeyPatch):
    # Even if YAML says otherwise, class attribute wins.
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win"},
    )
    assert guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


def test_yaml_bundle_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithoutGuide": "yaml guide body"},
    )
    assert guide_registry.resolve(_FakeWithoutGuide) == "yaml guide body"


def test_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {})
    assert guide_registry.resolve(_FakeWithoutGuide) is None


class _FakeOptedOut:
    assist_enabled: ClassVar[bool] = False


def test_is_assist_enabled_defaults_true():
    assert guide_registry.is_assist_enabled(_FakeWithoutGuide) is True


def test_is_assist_enabled_honors_class_attribute():
    assert guide_registry.is_assist_enabled(_FakeOptedOut) is False


def test_yaml_bundle_loads_and_merges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "a.yaml").write_text("- type: A\n  guide: from-a\n")
    (tmp_path / "b.yaml").write_text("- type: B\n  guide: from-b\n")
    monkeypatch.setattr(guide_registry, "_GUIDES_DIR", tmp_path)
    guide_registry._cached_bundle = None  # bust cache
    bundle = guide_registry._load_yaml_bundle()
    assert bundle == {"A": "from-a", "B": "from-b"}
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_guide_registry.py -v
```
Expected: ImportError — `guide_registry` doesn't exist.

- [ ] **Step 3: Implement the registry**

Create `src/backend/base/langflow/services/component_assist/guide_registry.py`:

```python
"""Resolve a component's assist guide.

Resolution order:
1. `assist_guide: ClassVar[str]` attribute on the class (highest priority).
2. YAML bundle under ``guides/*.yaml`` keyed by class name (populated by the
   bulk generator — see Plan 2).
3. ``None`` — callers fall back to a generic system prompt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
            raw: Any = yaml.safe_load(path.read_text()) or []
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


def resolve(component_cls: type) -> str | None:
    """Return the guide for a component class, or ``None`` if none configured."""
    inline = getattr(component_cls, "assist_guide", None)
    if isinstance(inline, str) and inline.strip():
        return inline
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

- [ ] **Step 4: Create the guides directory placeholder**

```bash
mkdir -p src/backend/base/langflow/services/component_assist/guides
touch src/backend/base/langflow/services/component_assist/guides/.gitkeep
```

- [ ] **Step 5: Run and confirm passing**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_guide_registry.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/component_assist/guide_registry.py \
        src/backend/base/langflow/services/component_assist/guides/.gitkeep \
        src/backend/tests/unit/services/component_assist/test_guide_registry.py
git commit -m "feat(component-assist): guide registry with class-attr and YAML resolution"
```

---

## Task 4: Prompt builder

**Files:**
- Create: `src/backend/base/langflow/services/component_assist/prompt.py`
- Create: `src/backend/tests/unit/services/component_assist/test_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the component assist prompt builder."""
from __future__ import annotations

from langflow.services.component_assist.prompt import build_system_prompt
from langflow.services.component_assist.schemas import NodeSnapshot


def _snapshot(node_id="n", ctype="FooComponent") -> NodeSnapshot:
    return NodeSnapshot(
        node_id=node_id,
        type=ctype,
        display_name="Foo",
        description="does foo",
        template={"x": {"display_name": "X", "value": 1}},
        outputs=[{"name": "out", "types": ["Data"]}],
    )


def test_prompt_includes_generic_framing_without_guide():
    prompt = build_system_prompt(
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        guide=None,
    )
    assert "FooComponent" in prompt
    assert "display_name" in prompt  # the target node is rendered
    assert "propose_config_update" in prompt


def test_prompt_injects_guide_when_present():
    prompt = build_system_prompt(
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        guide="Here is how you configure Foo: step 1.",
    )
    assert "Here is how you configure Foo: step 1." in prompt


def test_prompt_renders_neighbors_when_present():
    target = _snapshot("target", "Target")
    upstream = _snapshot("up", "UpstreamThing")
    prompt = build_system_prompt(
        node_snapshot=target,
        neighbor_snapshots=[upstream],
        guide=None,
    )
    assert "UpstreamThing" in prompt
    assert "neighbors" in prompt.lower()
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_prompt.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the prompt builder**

```python
"""Build the per-turn system prompt for the component assist service."""
from __future__ import annotations

import json

from langflow.services.component_assist.schemas import NodeSnapshot

_BASE = """You are ADP Assist, helping the user configure a single component in a Langflow flow.

Scope rules (strict):
- You MAY propose changes to the target component's template field values only.
- You MAY read neighbor component snapshots to understand the data shapes flowing in and out.
- You MUST NOT propose adding, removing, or rewiring components, or editing other components.

When you have a concrete configuration change to propose, call the `propose_config_update`
tool with the target `node_id` and a `patch` mapping of field names to new values, plus a
one-sentence `rationale` the user will see.

If the user's intent is ambiguous, ask a short clarifying question before proposing anything.
"""


def _snapshot_view(s: NodeSnapshot) -> dict:
    return {
        "node_id": s.node_id,
        "type": s.type,
        "display_name": s.display_name,
        "description": s.description,
        "template": s.template,
        "outputs": s.outputs,
    }


def build_system_prompt(
    *,
    node_snapshot: NodeSnapshot,
    neighbor_snapshots: list[NodeSnapshot],
    guide: str | None,
) -> str:
    parts: list[str] = [_BASE]
    if guide:
        parts.append("Component-specific guidance:\n" + guide.strip())

    parts.append(
        "Target component (this is the ONLY node you may propose changes to):\n"
        + json.dumps(_snapshot_view(node_snapshot), indent=2, default=str)
    )

    if neighbor_snapshots:
        parts.append(
            "Connected neighbors (read-only context — do not propose changes here):\n"
            + json.dumps(
                [_snapshot_view(s) for s in neighbor_snapshots],
                indent=2,
                default=str,
            )
        )
    else:
        parts.append(
            "This component has no connected neighbors. If upstream data shape matters for"
            " your suggestion, ask the user to describe or paste it."
        )

    return "\n\n".join(parts)
```

- [ ] **Step 4: Run and confirm passing**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_prompt.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/component_assist/prompt.py \
        src/backend/tests/unit/services/component_assist/test_prompt.py
git commit -m "feat(component-assist): system prompt builder"
```

---

## Task 5: `ComponentAssistService` with streaming + validated tool calls

**Files:**
- Create: `src/backend/base/langflow/services/component_assist/service.py`
- Create: `src/backend/tests/unit/services/component_assist/test_service.py`

- [ ] **Step 1: Write the failing test**

This test uses a dummy LLM client that yields a scripted sequence of chunks and records calls. It asserts SSE event order and that invalid patches trigger one retry before erroring.

```python
"""Tests for the ComponentAssistService streaming behavior."""
from __future__ import annotations

from typing import Any, AsyncIterator
from uuid import uuid4

import pytest

from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    NodeSnapshot,
)
from langflow.services.component_assist.service import ComponentAssistService


class _ScriptedLLM:
    """Replays a canned sequence of chunks. Exposes `.calls` for inspection."""

    def __init__(self, scripts: list[list[dict[str, Any]]]):
        self._scripts = list(scripts)
        self.calls: list[str] = []

    async def stream(self, *, system_prompt: str, thread: list, user_message: str, tools: list):
        self.calls.append(user_message)
        script = self._scripts.pop(0)

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for chunk in script:
                yield chunk

        return _gen()


def _req() -> ComponentAssistRequest:
    snap = NodeSnapshot(
        node_id="n1",
        type="FooComponent",
        display_name="Foo",
        description=None,
        template={"x": {"display_name": "X", "value": 0}},
        outputs=[],
    )
    return ComponentAssistRequest(
        flow_id=uuid4(),
        node_id="n1",
        node_snapshot=snap,
        neighbor_snapshots=[],
        thread=[],
        user_message="set x to 5",
    )


async def _collect(stream):
    return [ev async for ev in stream]


@pytest.mark.asyncio
async def test_streams_token_then_tool_call_then_done():
    llm = _ScriptedLLM([[
        {"type": "token", "text": "Setting "},
        {"type": "token", "text": "x to 5."},
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "n1", "patch": {"x": 5}, "rationale": "user asked"},
        },
    ]])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    kinds = [e["type"] for e in events]
    assert kinds == ["token", "token", "tool_call", "done"]
    assert events[2]["name"] == "propose_config_update"
    assert events[2]["args"]["patch"] == {"x": 5}


@pytest.mark.asyncio
async def test_invalid_patch_keys_trigger_one_retry_then_error():
    llm = _ScriptedLLM([
        [  # first call: patch references non-existent field
            {
                "type": "tool_call",
                "name": "propose_config_update",
                "args": {"node_id": "n1", "patch": {"not_a_field": 1}, "rationale": ""},
            },
        ],
        [  # retry call: still wrong
            {
                "type": "tool_call",
                "name": "propose_config_update",
                "args": {"node_id": "n1", "patch": {"still_wrong": 1}, "rationale": ""},
            },
        ],
    ])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    assert events[-1]["type"] == "error"
    assert len(llm.calls) == 2  # one retry


@pytest.mark.asyncio
async def test_node_id_mismatch_is_rejected():
    llm = _ScriptedLLM([[
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "different", "patch": {"x": 5}, "rationale": ""},
        },
    ], [
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "different", "patch": {"x": 5}, "rationale": ""},
        },
    ]])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    assert events[-1]["type"] == "error"
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_service.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the service**

Create `src/backend/base/langflow/services/component_assist/service.py`:

```python
"""Per-component ephemeral assistant service.

Stateless: every call to ``stream_reply`` is a fresh request carrying the full thread.
No DB writes, no in-process session cache.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from langflow.services.component_assist.prompt import build_system_prompt
from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    ProposeConfigUpdate,
)

_TOOL_SCHEMA = {
    "name": "propose_config_update",
    "description": (
        "Propose a partial update to the target node's template field values. "
        "The patch must only reference fields that exist on the target node."
    ),
    "parameters": ProposeConfigUpdate.model_json_schema(),
}


class LLMClient(Protocol):
    async def stream(
        self,
        *,
        system_prompt: str,
        thread: list,
        user_message: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        ...


class ComponentAssistService:
    def __init__(self, *, llm: LLMClient, guide: str | None) -> None:
        self._llm = llm
        self._guide = guide

    async def stream_reply(
        self,
        request: ComponentAssistRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        system_prompt = build_system_prompt(
            node_snapshot=request.node_snapshot,
            neighbor_snapshots=request.neighbor_snapshots,
            guide=self._guide,
        )
        allowed_keys = set(request.node_snapshot.template.keys())
        target_node_id = request.node_id

        user_message = request.user_message
        retries_left = 1

        while True:
            error: str | None = None
            async for chunk in await self._llm.stream(
                system_prompt=system_prompt,
                thread=[m.model_dump() for m in request.thread],
                user_message=user_message,
                tools=[_TOOL_SCHEMA],
            ):
                kind = chunk.get("type")
                if kind == "token":
                    yield {"type": "token", "text": chunk.get("text", "")}
                elif kind == "tool_call":
                    if chunk.get("name") != "propose_config_update":
                        error = f"Unknown tool: {chunk.get('name')!r}"
                        break
                    try:
                        tool = ProposeConfigUpdate.model_validate(chunk.get("args") or {})
                    except Exception as exc:  # noqa: BLE001
                        error = f"Invalid tool arguments: {exc}"
                        break
                    if tool.node_id != target_node_id:
                        error = (
                            f"Patch targets wrong node: {tool.node_id!r} "
                            f"(expected {target_node_id!r})"
                        )
                        break
                    bad_keys = [k for k in tool.patch if k not in allowed_keys]
                    if bad_keys:
                        error = f"Patch references unknown fields: {sorted(bad_keys)!r}"
                        break
                    yield {
                        "type": "tool_call",
                        "name": "propose_config_update",
                        "args": tool.model_dump(),
                    }
                elif kind == "error":
                    error = str(chunk.get("error") or "LLM error")
                    break

            if error is None:
                yield {"type": "done"}
                return

            if retries_left <= 0:
                yield {"type": "error", "error": error}
                return
            retries_left -= 1
            user_message = (
                f"{request.user_message}\n\n"
                f"Your previous proposal was rejected: {error}. "
                "Revise and try again."
            )
```

- [ ] **Step 4: Run and confirm passing**

```bash
uv run pytest src/backend/tests/unit/services/component_assist/test_service.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/component_assist/service.py \
        src/backend/tests/unit/services/component_assist/test_service.py
git commit -m "feat(component-assist): stateless streaming service with single retry"
```

---

## Task 6: SSE endpoint + router registration

**Files:**
- Create: `src/backend/base/langflow/api/v1/component_assist.py`
- Modify: `src/backend/base/langflow/api/router.py`
- Create: `src/backend/tests/unit/api/v1/test_component_assist_endpoint.py`

- [ ] **Step 1: Locate the existing assistant router**

Read `src/backend/base/langflow/api/v1/assistant.py` around the `POST /flows/{flow_id}/messages` endpoint (approximately line 300). Note the dependencies it uses: `CurrentActiveUser`, `CurrentOrg`, `DbSession`, and `_get_flow_with_org_check`. Also note the imports for `EventSourceResponse` and how it constructs the provider client.

- [ ] **Step 2: Write the failing endpoint test**

```python
"""Endpoint tests for POST /api/v1/assistant/components/messages."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _post(client: AsyncClient, body: dict[str, Any]):
    return await client.post("/api/v1/assistant/components/messages", json=body)


def _minimal_body(flow_id: str, node_id: str = "n1") -> dict[str, Any]:
    return {
        "flow_id": flow_id,
        "node_id": node_id,
        "node_snapshot": {
            "node_id": node_id,
            "type": "FakeComponent",
            "display_name": "Fake",
            "description": None,
            "template": {"x": {"display_name": "X", "value": 0}},
            "outputs": [],
        },
        "neighbor_snapshots": [],
        "thread": [],
        "user_message": "hi",
    }


async def test_403_when_flow_belongs_to_other_org(
    client_other_org: AsyncClient, other_org_flow_id: str
):
    resp = await _post(client_other_org, _minimal_body(other_org_flow_id))
    assert resp.status_code == 403


async def test_404_when_flow_missing(client_authed: AsyncClient):
    resp = await _post(client_authed, _minimal_body(str(uuid4())))
    assert resp.status_code == 404


async def test_400_when_component_opts_out(
    client_authed: AsyncClient, own_flow_id: str, monkeypatch
):
    """DataMapperComponent sets assist_enabled=False; the endpoint must refuse."""
    body = _minimal_body(own_flow_id)
    body["node_snapshot"]["type"] = "DataMapperComponent"
    resp = await _post(client_authed, body)
    assert resp.status_code == 400
    assert "opted out" in resp.json()["detail"].lower() or "assist_enabled" in resp.json()["detail"]


async def test_happy_path_streams_events(
    client_authed: AsyncClient, own_flow_id: str, scripted_llm_patch
):
    """scripted_llm_patch is a fixture that monkeypatches the LLM to yield one token + done."""
    body = _minimal_body(own_flow_id)
    async with client_authed.stream("POST", "/api/v1/assistant/components/messages", json=body) as resp:
        assert resp.status_code == 200
        lines: list[str] = []
        async for line in resp.aiter_lines():
            lines.append(line)
            if "done" in line:
                break
    assert any("token" in line for line in lines)
    assert any("done" in line for line in lines)
```

Note: `client_authed`, `client_other_org`, `own_flow_id`, `other_org_flow_id`, and `scripted_llm_patch` are fixtures that follow the same pattern as existing endpoint tests under `src/backend/tests/unit/api/v1/`. If a similar fixture set doesn't already exist, add them to `src/backend/tests/unit/api/v1/conftest.py` mirroring `test_assistant_endpoint.py`.

- [ ] **Step 3: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/api/v1/test_component_assist_endpoint.py -v
```
Expected: fixture or import errors.

- [ ] **Step 4: Implement the endpoint**

Create `src/backend/base/langflow/api/v1/component_assist.py`:

```python
"""POST /api/v1/assistant/components/messages — SSE endpoint for per-component assist."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from langflow.api.utils import CurrentActiveUser, CurrentOrg, DbSession
from langflow.api.v1.assistant import _get_flow_with_org_check, _build_llm_client
from langflow.services.component_assist.guide_registry import (
    is_assist_enabled,
    resolve as resolve_guide,
)
from langflow.services.component_assist.schemas import ComponentAssistRequest
from langflow.services.component_assist.service import ComponentAssistService

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/assistant/components", tags=["assistant"])


def _resolve_component_class(type_name: str) -> type | None:
    """Look up the Component subclass by its class name via the loader registry."""
    from langflow.interface.types import get_all_components  # local import — heavy

    registry = get_all_components()
    for component_cls in registry.values():
        if component_cls.__name__ == type_name:
            return component_cls
    return None


@router.post("/messages")
async def component_assist_messages(
    body: ComponentAssistRequest,
    request: Request,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
):
    # Auth: reuse the flow-level check. Raises 404/403 appropriately.
    await _get_flow_with_org_check(session=session, flow_id=body.flow_id, org=org)

    component_cls = _resolve_component_class(body.node_snapshot.type)
    if component_cls is not None and not is_assist_enabled(component_cls):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Component '{body.node_snapshot.type}' has opted out of ADP Assist "
                "(see assist_enabled=False). It ships with its own bespoke agent."
            ),
        )
    guide = resolve_guide(component_cls) if component_cls is not None else None

    llm = _build_llm_client(org=org, user=current_user)
    service = ComponentAssistService(llm=llm, guide=guide)

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        async for event in service.stream_reply(body):
            yield {"event": "message", "data": json.dumps(event)}

    return EventSourceResponse(event_gen())
```

Note on helper imports: `_get_flow_with_org_check` and `_build_llm_client` may be private to `assistant.py`. If they are not importable as-is, refactor them into `src/backend/base/langflow/api/v1/_assistant_shared.py` in a preliminary sub-commit and import from there. Keep their signatures identical.

- [ ] **Step 5: Register the router**

Open `src/backend/base/langflow/api/router.py`. Find the block that includes `assistant_router` (or equivalent) with `router_v1.include_router(...)`. Add next to it:

```python
from langflow.api.v1.component_assist import router as component_assist_router

router_v1.include_router(component_assist_router)
```

- [ ] **Step 6: Run and confirm passing**

```bash
uv run pytest src/backend/tests/unit/api/v1/test_component_assist_endpoint.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add src/backend/base/langflow/api/v1/component_assist.py \
        src/backend/base/langflow/api/router.py \
        src/backend/tests/unit/api/v1/test_component_assist_endpoint.py
git commit -m "feat(api): POST /api/v1/assistant/components/messages SSE endpoint"
```

---

## Task 7: `componentAssistStore` (zustand)

**Files:**
- Create: `src/frontend/src/stores/componentAssistStore.ts`
- Create: `src/frontend/src/modals/ComponentAssistPopover/types.ts`
- Create: `src/frontend/src/stores/__tests__/componentAssistStore.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { act, renderHook } from "@testing-library/react";

import useComponentAssistStore from "../componentAssistStore";

describe("componentAssistStore", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: null,
      anchorRect: null,
      position: { x: 0, y: 0 },
      size: { w: 420, h: 500 },
      thread: [],
      isStreaming: false,
    });
  });

  it("opens with activeNodeId and position derived from anchor", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    const rect = { top: 100, left: 200, bottom: 140, right: 280, width: 80, height: 40, x: 200, y: 100, toJSON: () => ({}) } as DOMRect;
    act(() => {
      result.current.open("node-a", rect);
    });
    expect(result.current.activeNodeId).toBe("node-a");
    expect(result.current.anchorRect).toBe(rect);
    expect(result.current.thread).toEqual([]);
  });

  it("closes and wipes the thread", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    act(() => {
      result.current.open("node-a", null);
      result.current.appendUserMessage("hi");
    });
    expect(result.current.thread.length).toBe(1);
    act(() => {
      result.current.close();
    });
    expect(result.current.activeNodeId).toBeNull();
    expect(result.current.thread).toEqual([]);
  });

  it("appendAssistantDelta merges into the trailing assistant message", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    act(() => {
      result.current.open("n", null);
      result.current.appendUserMessage("hi");
      result.current.appendAssistantDelta("Hel");
      result.current.appendAssistantDelta("lo!");
    });
    const last = result.current.thread[result.current.thread.length - 1];
    expect(last.role).toBe("assistant");
    expect(last.content).toBe("Hello!");
  });
});
```

- [ ] **Step 2: Create the types file**

```ts
// src/frontend/src/modals/ComponentAssistPopover/types.ts
export type ThreadMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; proposals?: ProposalPayload[] };

export type ProposalPayload = {
  id: string;
  nodeId: string;
  patch: Record<string, unknown>;
  rationale: string;
  applied?: { skippedKeys: string[] } | null;
};
```

- [ ] **Step 3: Implement the store**

```ts
// src/frontend/src/stores/componentAssistStore.ts
import { create } from "zustand";
import type {
  ProposalPayload,
  ThreadMessage,
} from "@/modals/ComponentAssistPopover/types";

type ComponentAssistState = {
  activeNodeId: string | null;
  anchorRect: DOMRect | null;
  position: { x: number; y: number };
  size: { w: number; h: number };
  thread: ThreadMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;

  open: (nodeId: string, anchorRect: DOMRect | null) => void;
  close: () => void;
  setPosition: (p: { x: number; y: number }) => void;
  setSize: (s: { w: number; h: number }) => void;
  appendUserMessage: (text: string) => void;
  appendAssistantDelta: (delta: string) => void;
  appendProposal: (proposal: ProposalPayload) => void;
  markProposalApplied: (proposalId: string, skippedKeys: string[]) => void;
  setStreaming: (v: boolean) => void;
  setAbortController: (c: AbortController | null) => void;
};

const INITIAL_POSITION = { x: 120, y: 120 };
const INITIAL_SIZE = { w: 420, h: 500 };

const useComponentAssistStore = create<ComponentAssistState>((set, get) => ({
  activeNodeId: null,
  anchorRect: null,
  position: INITIAL_POSITION,
  size: INITIAL_SIZE,
  thread: [],
  isStreaming: false,
  abortController: null,

  open: (nodeId, anchorRect) => {
    const position = anchorRect
      ? { x: Math.min(anchorRect.right + 12, window.innerWidth - 440), y: anchorRect.top }
      : INITIAL_POSITION;
    set({
      activeNodeId: nodeId,
      anchorRect,
      position,
      size: INITIAL_SIZE,
      thread: [],
      isStreaming: false,
    });
  },

  close: () => {
    get().abortController?.abort();
    set({
      activeNodeId: null,
      anchorRect: null,
      thread: [],
      isStreaming: false,
      abortController: null,
    });
  },

  setPosition: (position) => set({ position }),
  setSize: (size) => set({ size }),

  appendUserMessage: (content) =>
    set((s) => ({ thread: [...s.thread, { role: "user", content }] })),

  appendAssistantDelta: (delta) =>
    set((s) => {
      const last = s.thread[s.thread.length - 1];
      if (last && last.role === "assistant") {
        const updated = { ...last, content: last.content + delta };
        return { thread: [...s.thread.slice(0, -1), updated] };
      }
      return {
        thread: [...s.thread, { role: "assistant", content: delta }],
      };
    }),

  appendProposal: (proposal) =>
    set((s) => {
      const last = s.thread[s.thread.length - 1];
      if (last && last.role === "assistant") {
        const updated = {
          ...last,
          proposals: [...(last.proposals ?? []), proposal],
        };
        return { thread: [...s.thread.slice(0, -1), updated] };
      }
      return {
        thread: [...s.thread, { role: "assistant", content: "", proposals: [proposal] }],
      };
    }),

  markProposalApplied: (proposalId, skippedKeys) =>
    set((s) => ({
      thread: s.thread.map((m) =>
        m.role === "assistant" && m.proposals
          ? {
              ...m,
              proposals: m.proposals.map((p) =>
                p.id === proposalId ? { ...p, applied: { skippedKeys } } : p,
              ),
            }
          : m,
      ),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  setAbortController: (c) => set({ abortController: c }),
}));

export default useComponentAssistStore;
```

- [ ] **Step 4: Run and confirm passing**

```bash
cd src/frontend && npm test -- --testPathPattern=componentAssistStore
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/stores/componentAssistStore.ts \
        src/frontend/src/modals/ComponentAssistPopover/types.ts \
        src/frontend/src/stores/__tests__/componentAssistStore.test.ts
git commit -m "feat(component-assist): zustand store for ephemeral popover state"
```

---

## Task 8: `use-component-assist-stream` hook

**Files:**
- Create: `src/frontend/src/modals/ComponentAssistPopover/hooks/use-component-assist-stream.ts`
- Create: `src/frontend/src/modals/ComponentAssistPopover/__tests__/use-component-assist-stream.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { act, renderHook, waitFor } from "@testing-library/react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import { useComponentAssistStream } from "../hooks/use-component-assist-stream";

const SSE_OK = (chunks: string[]) => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return { ok: true, body: stream, status: 200 } as unknown as Response;
};

describe("useComponentAssistStream", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: "n1",
      anchorRect: null,
      position: { x: 0, y: 0 },
      size: { w: 0, h: 0 },
      thread: [],
      isStreaming: false,
      abortController: null,
    });
    global.fetch = jest.fn();
  });

  it("parses token events into assistant deltas", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      SSE_OK([
        'data: {"type":"token","text":"Hel"}\n',
        'data: {"type":"token","text":"lo"}\n',
        'data: {"type":"done"}\n',
      ]),
    );
    const { result } = renderHook(() => useComponentAssistStream("flow-1"));
    await act(async () => {
      await result.current.sendMessage({
        nodeSnapshot: { node_id: "n1", type: "X", display_name: "X", template: {}, outputs: [] } as any,
        neighborSnapshots: [],
        userMessage: "hi",
      });
    });
    await waitFor(() => {
      const thread = useComponentAssistStore.getState().thread;
      expect(thread[thread.length - 1]).toMatchObject({ role: "assistant", content: "Hello" });
    });
  });

  it("materializes tool_call events as proposals", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      SSE_OK([
        'data: {"type":"tool_call","name":"propose_config_update","args":{"node_id":"n1","patch":{"x":5},"rationale":"test"}}\n',
        'data: {"type":"done"}\n',
      ]),
    );
    const { result } = renderHook(() => useComponentAssistStream("flow-1"));
    await act(async () => {
      await result.current.sendMessage({
        nodeSnapshot: { node_id: "n1", type: "X", display_name: "X", template: { x: { value: 0 } }, outputs: [] } as any,
        neighborSnapshots: [],
        userMessage: "set x",
      });
    });
    const thread = useComponentAssistStore.getState().thread;
    const last = thread[thread.length - 1];
    expect(last.role).toBe("assistant");
    expect(last.proposals?.[0].patch).toEqual({ x: 5 });
  });
});
```

- [ ] **Step 2: Implement the hook**

```ts
// src/frontend/src/modals/ComponentAssistPopover/hooks/use-component-assist-stream.ts
import { useCallback } from "react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import type { ProposalPayload } from "../types";

type NodeSnapshot = {
  node_id: string;
  type: string;
  display_name: string;
  description?: string | null;
  template: Record<string, unknown>;
  outputs: unknown[];
};

type SendArgs = {
  nodeSnapshot: NodeSnapshot;
  neighborSnapshots: NodeSnapshot[];
  userMessage: string;
};

const randomId = () =>
  (globalThis.crypto?.randomUUID?.() ?? String(Math.random())).slice(0, 12);

export function useComponentAssistStream(flowId: string) {
  const sendMessage = useCallback(
    async ({ nodeSnapshot, neighborSnapshots, userMessage }: SendArgs) => {
      const store = useComponentAssistStore.getState();
      store.appendUserMessage(userMessage);
      store.setStreaming(true);

      const controller = new AbortController();
      store.setAbortController(controller);

      try {
        const response = await fetch("/api/v1/assistant/components/messages", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            flow_id: flowId,
            node_id: nodeSnapshot.node_id,
            node_snapshot: nodeSnapshot,
            neighbor_snapshots: neighborSnapshots,
            thread: store.thread.map(({ role, content }) => ({ role, content })),
            user_message: userMessage,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data: ")) continue;
            const payload = trimmed.slice(6);
            if (!payload || payload === "[DONE]") continue;
            let event: any;
            try {
              event = JSON.parse(payload);
            } catch {
              continue;
            }
            const s = useComponentAssistStore.getState();
            switch (event.type) {
              case "token":
                s.appendAssistantDelta(event.text ?? "");
                break;
              case "tool_call":
                if (event.name === "propose_config_update") {
                  const proposal: ProposalPayload = {
                    id: randomId(),
                    nodeId: event.args?.node_id,
                    patch: event.args?.patch ?? {},
                    rationale: event.args?.rationale ?? "",
                  };
                  s.appendProposal(proposal);
                }
                break;
              case "error":
                s.appendAssistantDelta(`\n[Error] ${event.error ?? "Unknown error"}`);
                break;
              case "done":
                break;
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          const s = useComponentAssistStore.getState();
          s.appendAssistantDelta(`\n[Connection lost — please try again.]`);
        }
      } finally {
        const s = useComponentAssistStore.getState();
        s.setStreaming(false);
        s.setAbortController(null);
      }
    },
    [flowId],
  );

  return { sendMessage };
}
```

- [ ] **Step 3: Run and confirm passing**

```bash
cd src/frontend && npm test -- --testPathPattern=use-component-assist-stream
```
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/modals/ComponentAssistPopover/hooks/ \
        src/frontend/src/modals/ComponentAssistPopover/__tests__/use-component-assist-stream.test.ts
git commit -m "feat(component-assist): SSE streaming hook with abort + proposal materialization"
```

---

## Task 9: `ProposalBlock` component

**Files:**
- Create: `src/frontend/src/modals/ComponentAssistPopover/components/ProposalBlock.tsx`
- Create: `src/frontend/src/modals/ComponentAssistPopover/__tests__/ProposalBlock.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";

import { ProposalBlock } from "../components/ProposalBlock";
import type { ProposalPayload } from "../types";

const makeProposal = (overrides: Partial<ProposalPayload> = {}): ProposalPayload => ({
  id: "p1",
  nodeId: "n1",
  patch: { x: 5, y: "hello" },
  rationale: "because you asked",
  applied: null,
  ...overrides,
});

describe("ProposalBlock", () => {
  it("renders each patch field", () => {
    render(
      <ProposalBlock
        proposal={makeProposal()}
        currentTemplate={{ x: { value: 0 }, y: { value: "" } }}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/x/)).toBeInTheDocument();
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/because you asked/)).toBeInTheDocument();
  });

  it("calls onApply with the full patch when Apply is clicked", () => {
    const onApply = jest.fn();
    render(
      <ProposalBlock
        proposal={makeProposal()}
        currentTemplate={{ x: { value: 0 }, y: { value: "" } }}
        onApply={onApply}
        onDismiss={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith({ x: 5, y: "hello" });
  });

  it("shows Applied state with skipped keys", () => {
    render(
      <ProposalBlock
        proposal={makeProposal({ applied: { skippedKeys: ["y"] } })}
        currentTemplate={{ x: { value: 0 } }}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/Applied/i)).toBeInTheDocument();
    expect(screen.getByText(/skipped/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement the component**

```tsx
// src/frontend/src/modals/ComponentAssistPopover/components/ProposalBlock.tsx
import type { ProposalPayload } from "../types";

type Props = {
  proposal: ProposalPayload;
  currentTemplate: Record<string, { value?: unknown }>;
  onApply: (patch: Record<string, unknown>) => void;
  onDismiss: () => void;
};

export function ProposalBlock({ proposal, currentTemplate, onApply, onDismiss }: Props) {
  const { patch, rationale, applied } = proposal;
  const isApplied = !!applied;

  return (
    <div
      className="rounded-md border border-adp-red/50 bg-adp-red/5 p-3 text-sm"
      data-testid="proposal-block"
    >
      <div className="mb-2 font-semibold text-adp-red">⚡ Proposed change</div>

      {rationale && <div className="mb-2 text-muted-foreground italic">{rationale}</div>}

      <div className="font-mono text-xs">
        {Object.entries(patch).map(([key, value]) => {
          const current = currentTemplate[key]?.value;
          return (
            <div key={key} className="grid grid-cols-[auto_1fr_auto_1fr] gap-2 py-1">
              <span className="text-muted-foreground">{key}</span>
              <span className="line-through text-muted-foreground truncate">
                {JSON.stringify(current)}
              </span>
              <span className="text-adp-red">→</span>
              <span className="truncate">{JSON.stringify(value)}</span>
            </div>
          );
        })}
      </div>

      {isApplied ? (
        <div className="mt-2 text-xs italic text-muted-foreground">
          Applied ✓
          {applied!.skippedKeys.length > 0 && (
            <> — {applied!.skippedKeys.length} field(s) skipped ({applied!.skippedKeys.join(", ")})</>
          )}
        </div>
      ) : (
        <div className="mt-3 flex justify-end gap-2">
          <button
            onClick={onDismiss}
            className="rounded border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            Dismiss
          </button>
          <button
            onClick={() => onApply(patch)}
            className="rounded bg-adp-red px-3 py-1 text-xs font-semibold text-adp-red-foreground hover:opacity-90"
          >
            Apply ▸
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run and confirm passing**

```bash
cd src/frontend && npm test -- --testPathPattern=ProposalBlock
```
Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/modals/ComponentAssistPopover/components/ProposalBlock.tsx \
        src/frontend/src/modals/ComponentAssistPopover/__tests__/ProposalBlock.test.tsx
git commit -m "feat(component-assist): inline ProposalBlock with Apply/Dismiss"
```

---

## Task 10: `ComponentAssistPopover` (drag, chat, input)

**Files:**
- Create: `src/frontend/src/modals/ComponentAssistPopover/index.tsx`
- Create: `src/frontend/src/modals/ComponentAssistPopover/__tests__/ComponentAssistPopover.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { act, fireEvent, render, screen } from "@testing-library/react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import ComponentAssistPopover from "../index";

describe("ComponentAssistPopover", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: null,
      anchorRect: null,
      position: { x: 100, y: 100 },
      size: { w: 420, h: 500 },
      thread: [],
      isStreaming: false,
      abortController: null,
    });
  });

  it("does not render when closed", () => {
    render(<ComponentAssistPopover />);
    expect(screen.queryByTestId("component-assist-popover")).not.toBeInTheDocument();
  });

  it("renders with title derived from active node and an ephemeral footer", () => {
    useComponentAssistStore.setState({ activeNodeId: "n-abc" });
    render(<ComponentAssistPopover />);
    expect(screen.getByTestId("component-assist-popover")).toBeInTheDocument();
    expect(screen.getByText(/won't be saved/i)).toBeInTheDocument();
  });

  it("closes and wipes the thread when the close button is clicked", () => {
    useComponentAssistStore.setState({
      activeNodeId: "n-1",
      thread: [{ role: "user", content: "hi" }],
    });
    render(<ComponentAssistPopover />);
    fireEvent.click(screen.getByLabelText(/close/i));
    expect(useComponentAssistStore.getState().activeNodeId).toBeNull();
    expect(useComponentAssistStore.getState().thread).toEqual([]);
  });
});
```

- [ ] **Step 2: Implement the popover**

```tsx
// src/frontend/src/modals/ComponentAssistPopover/index.tsx
import { useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useComponentAssistStore from "@/stores/componentAssistStore";
import useFlowStore from "@/stores/flowStore";

import { ProposalBlock } from "./components/ProposalBlock";
import { useComponentAssistStream } from "./hooks/use-component-assist-stream";

export default function ComponentAssistPopover() {
  const { activeNodeId, position, size, thread, isStreaming, close, setPosition } =
    useComponentAssistStore(
      useShallow((s) => ({
        activeNodeId: s.activeNodeId,
        position: s.position,
        size: s.size,
        thread: s.thread,
        isStreaming: s.isStreaming,
        close: s.close,
        setPosition: s.setPosition,
      })),
    );

  const flowId = useFlowStore((s) => s.currentFlow?.id ?? "");
  const node = useFlowStore(
    (s) => s.nodes.find((n) => n.id === activeNodeId) ?? null,
  );
  const setNode = useFlowStore((s) => s.setNode);

  const [input, setInput] = useState("");
  const bodyRef = useRef<HTMLDivElement>(null);

  const { sendMessage } = useComponentAssistStream(flowId);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [thread.length, isStreaming]);

  if (!activeNodeId || !node) return null;

  const displayName = node.data?.node?.display_name ?? "Component";
  const template = (node.data?.node?.template ?? {}) as Record<string, { value?: unknown }>;

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const text = input;
    setInput("");
    const nodeSnapshot = {
      node_id: node.id,
      type: node.data?.type ?? "",
      display_name: displayName,
      description: node.data?.node?.description ?? null,
      template,
      outputs: node.data?.node?.outputs ?? [],
    };
    await sendMessage({ nodeSnapshot, neighborSnapshots: [], userMessage: text });
  };

  const applyPatch = (patch: Record<string, unknown>, proposalId: string) => {
    const skipped: string[] = [];
    setNode(node.id, (old) => {
      const tpl = { ...(old.data?.node?.template ?? {}) };
      for (const [k, v] of Object.entries(patch)) {
        if (!(k in tpl)) {
          skipped.push(k);
          continue;
        }
        tpl[k] = { ...tpl[k], value: v };
      }
      return {
        ...old,
        data: { ...old.data, node: { ...old.data.node, template: tpl } },
      };
    });
    useComponentAssistStore.getState().markProposalApplied(proposalId, skipped);
  };

  return (
    <div
      data-testid="component-assist-popover"
      className="fixed z-50 flex flex-col rounded-lg border border-adp-red/60 bg-background shadow-2xl"
      style={{ left: position.x, top: position.y, width: size.w, height: size.h }}
    >
      {/* Header / drag handle */}
      <div
        className="flex cursor-grab items-center justify-between border-b border-adp-red/30 bg-adp-red/10 px-3 py-2"
        onMouseDown={(e) => {
          const startX = e.clientX - position.x;
          const startY = e.clientY - position.y;
          const onMove = (ev: MouseEvent) =>
            setPosition({ x: ev.clientX - startX, y: ev.clientY - startY });
          const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
          };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        }}
      >
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-adp-red" />
          <span className="text-sm font-semibold">Assist · {displayName}</span>
          <span className="text-xs italic text-amber-500">ephemeral</span>
        </div>
        <button
          aria-label="Close"
          onClick={close}
          className="text-muted-foreground hover:text-foreground"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div ref={bodyRef} className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {thread.length === 0 && (
          <div className="rounded bg-muted p-2 text-muted-foreground">
            Hi! I'll help configure {displayName}. Paste a spec, describe rules, or ask me
            anything.
          </div>
        )}
        {thread.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[85%] rounded-lg bg-muted px-3 py-2"
                  : "max-w-[95%] space-y-2"
              }
            >
              {m.content && <div className="whitespace-pre-wrap">{m.content}</div>}
              {m.role === "assistant" &&
                m.proposals?.map((p) => (
                  <ProposalBlock
                    key={p.id}
                    proposal={p}
                    currentTemplate={template}
                    onApply={(patch) => applyPatch(patch, p.id)}
                    onDismiss={() => useComponentAssistStore.getState().markProposalApplied(p.id, [])}
                  />
                ))}
            </div>
          </div>
        ))}
        {isStreaming && (
          <div className="text-xs italic text-muted-foreground">Assistant is thinking…</div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border p-2">
        <div className="flex items-center gap-2 rounded border border-border bg-muted/50 px-2 py-1">
          <ForwardedIconComponent name="Sparkles" className="h-4 w-4 text-adp-red" />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything about this component…"
            className="flex-1 bg-transparent text-sm outline-none"
          />
        </div>
        <div className="mt-1 text-center text-[10px] italic text-muted-foreground">
          This conversation won't be saved when you close.
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Mount the popover in the flow page**

Open `src/frontend/src/pages/FlowPage/index.tsx` (or wherever the top-level flow page is rendered — verify with a quick grep for `<AssistantPanel`). Add `<ComponentAssistPopover />` as a sibling of the existing `<AssistantPanel>`:

```tsx
import ComponentAssistPopover from "@/modals/ComponentAssistPopover";
// ...
<ComponentAssistPopover />
```

- [ ] **Step 4: Run and confirm passing**

```bash
cd src/frontend && npm test -- --testPathPattern=ComponentAssistPopover
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/modals/ComponentAssistPopover/index.tsx \
        src/frontend/src/modals/ComponentAssistPopover/__tests__/ComponentAssistPopover.test.tsx \
        src/frontend/src/pages/FlowPage/index.tsx
git commit -m "feat(component-assist): draggable popover with chat UI and apply handler"
```

---

## Task 11: Assist icon in the node toolbar

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx`

- [ ] **Step 1: Locate the toolbar button render block**

Open `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx`. Find the `renderToolbarButtons` memoized JSX fragment (around line 499). Note the `ToolbarButton` pattern: `<ToolbarButton icon label onClick shortcut dataTestId />`.

- [ ] **Step 2: Wire up the open-assist action**

At the top of the component, import the store and add a handler:

```tsx
import useComponentAssistStore from "@/stores/componentAssistStore";

// Inside the component body (near other useMemos / handlers):
const openComponentAssist = useComponentAssistStore((s) => s.open);
const anchorRef = useRef<HTMLDivElement>(null);
```

- [ ] **Step 3: Read the `assist_enabled` flag off the node**

The component's `assist_enabled` class attribute is exposed on the node's frontend template as part of the normal build-config path. Confirm by inspecting `data.node.template.assist_enabled` in a logged-out `console.log(data)` on a DataMapper node; otherwise it's available via `data.node.metadata.assist_enabled` (verify with a grep in `src/frontend/src/` for how other ClassVar flags like `legacy` surface on the frontend).

Derive a local boolean:

```tsx
const assistEnabled = (data?.node?.metadata?.assist_enabled ?? data?.node?.template?.assist_enabled ?? true) !== false;
```

If neither location carries the flag, add a small backend adjustment (in a preliminary task committed separately): in the component's frontend-node serializer, emit `metadata.assist_enabled = getattr(cls, "assist_enabled", True)`. Never invent a new API surface — use whichever existing class-level-flag pathway `legacy` rides on.

- [ ] **Step 4: Add the Assist button to the toolbar fragment, gated by the flag**

Insert this `ToolbarButton` at the start of the existing button list (leftmost), wrapped in the enablement check:

```tsx
{assistEnabled && (
  <ToolbarButton
    icon="Sparkles"
    label="Assist"
    iconClassName="text-adp-red"
    onClick={() => {
      const rect = anchorRef.current?.getBoundingClientRect() ?? null;
      openComponentAssist(data.id, rect);
    }}
    dataTestId="component-assist-button"
  />
)}
```

If `ToolbarButton` doesn't accept `iconClassName`, extend its props (one-line addition in `ToolbarButton.tsx`) to forward a classname into the `ForwardedIconComponent`.

- [ ] **Step 5: Attach the anchor ref to the toolbar wrapper**

Find the outer `<div>` that wraps the toolbar buttons. Attach `ref={anchorRef}` so the popover can anchor off its screen rect.

- [ ] **Step 6: Manual smoke test (including opt-out)**

```bash
make backend  # terminal 1
make frontend # terminal 2
```

Open `http://localhost:3000`, open a flow that contains a DataMapper component and at least one other component. Confirm:
1. The **non-DataMapper** node shows the red ✨ **Assist** button. Click it — the popover opens anchored near the node with the greeting. Close it with ✕.
2. The **DataMapper** node does NOT show the Assist button (it has `assist_enabled=False`).

Kill the dev processes.

- [ ] **Step 7: Commit**

```bash
git add src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx \
        src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-button.tsx  # if modified
git commit -m "feat(component-assist): add Assist icon to node toolbar"
```

---

## Task 12: DataMapper opt-out + one reference `assist_guide` on a non-excluded component

**⚠ DataMapper hands-off:** DataMapperComponent has its own dedicated agent under active development. The ONLY change to DataMapper in this task is a single new class attribute. Do not touch its inputs, outputs, engine, transforms, or config schema.

**Files:**
- Modify: `src/lfx/src/lfx/components/processing/data_mapper.py` (opt-out line only)
- Modify: a non-excluded reference component — `src/lfx/src/lfx/components/processing/text_operations.py` (if present) OR another high-traffic component chosen by the executor based on metadata completeness
- Create: `src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py`

### 12A · DataMapper opt-out

- [ ] **Step 1: Write the failing test**

```python
"""DataMapper must opt out of ADP Assist; the reference component must expose a guide."""
from __future__ import annotations

from lfx.components.processing.data_mapper import DataMapperComponent
from langflow.services.component_assist.guide_registry import (
    is_assist_enabled,
    resolve as resolve_guide,
)


def test_data_mapper_opts_out_of_assist():
    assert is_assist_enabled(DataMapperComponent) is False


def test_reference_component_has_guide():
    # Import the chosen reference component. Executor: update this import to match
    # whichever component you pick in Step 3 below.
    from lfx.components.processing.text_operations import TextOperationsComponent

    guide = resolve_guide(TextOperationsComponent)
    assert isinstance(guide, str) and len(guide) > 200
    assert is_assist_enabled(TextOperationsComponent) is True
```

- [ ] **Step 2: Run and confirm failure**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py -v
```
Expected: `AttributeError` / assertion failure on both tests.

- [ ] **Step 3: Add the opt-out to DataMapperComponent**

Open `src/lfx/src/lfx/components/processing/data_mapper.py`. Locate the `DataMapperComponent` class definition. Add **exactly one** class attribute (plus the `ClassVar` import if it isn't already present). Do not touch anything else.

```python
from typing import ClassVar  # only if not already imported

class DataMapperComponent(Component):
    # ... existing attributes ...
    assist_enabled: ClassVar[bool] = False  # ADP Assist opt-out — DataMapper has its own bespoke agent
    # ... rest of class unchanged ...
```

- [ ] **Step 4: Confirm DataMapper test passes; reference-guide test still fails**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py::test_data_mapper_opts_out_of_assist -v
```
Expected: pass.

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py::test_reference_component_has_guide -v
```
Expected: still fails (no guide yet).

### 12B · Reference guide on `TextOperationsComponent`

- [ ] **Step 5: Add `assist_guide` to the reference component**

Open `src/lfx/src/lfx/components/processing/text_operations.py`. If this component doesn't exist, grep `src/lfx/src/lfx/components/` for a high-traffic processing component with rich metadata (populated `description` and per-input `info` strings on at least 3 inputs) and substitute it throughout — then update the test's import line accordingly.

Add the `ClassVar` import if needed, then add the guide alongside existing class attributes:

```python
from typing import ClassVar  # if not already imported

class TextOperationsComponent(Component):
    # ... existing attributes ...

    assist_guide: ClassVar[str] = """
You help the user configure text operations on an input string.

Approach:
1. Ask (or infer from the user's message) which operation they want: split, join, trim, replace,
   uppercase, or lowercase.
2. Confirm the input source — the upstream neighbor's output field that feeds this component's
   text input. If the upstream snapshot doesn't make it obvious, ask.
3. Propose operation-specific settings: for split, the delimiter; for replace, the find/replace
   pair; for join, the separator; etc.

When proposing config:
- Propose a concrete, applyable patch — don't ask the user to fill in blanks they could reject.
- If the user seems to want something the component can't do (e.g., regex when only literal
  replace is available), say so plainly and suggest either rephrasing or a different component.
""".strip()
    # ... rest of class unchanged ...
```

- [ ] **Step 6: Run and confirm both tests pass**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Apply component-authoring ritual for modified components**

Per `.claude/skills/langflow-component-authoring/SKILL.md`, bump the `version` and append to the changelog for **both** `DataMapperComponent` (opt-out contract added) and the reference component (guide added). Minimal, literal changelog entries only — do not expand either file's scope beyond these additions.

- [ ] **Step 8: Rebuild the component index**

```bash
uv run python scripts/build_component_index.py
```

- [ ] **Step 9: Commit**

```bash
git add src/lfx/src/lfx/components/processing/data_mapper.py \
        src/lfx/src/lfx/components/processing/text_operations.py \
        src/lfx/tests/unit/components/processing/test_assist_opt_out_and_guide.py \
        src/lfx/src/lfx/_assets/component_index.json
git commit -m "feat(lfx): opt DataMapper out of ADP Assist + seed reference assist_guide"
```

---

## Task 13: End-to-end smoke test (non-excluded target component)

**Files:**
- Create: `src/backend/tests/integration/test_component_assist_smoke.py`
- Modify: `src/backend/tests/integration/conftest.py` (fixtures)

**⚠ DataMapper hands-off:** this smoke test must NOT use `DataMapperComponent` — that component has opted out of ADP Assist. Use any other non-excluded component (e.g., `TextOperationsComponent`, matching the reference guide added in Task 12).

- [ ] **Step 1: Write the smoke test**

```python
"""End-to-end smoke: Source → TextOperations, Assist proposes a config, apply succeeds."""
from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_text_operations_proposal_roundtrip(
    client_authed: AsyncClient,
    flow_with_source_and_text_ops: dict[str, Any],
    scripted_llm_proposes_config,
):
    """With a scripted LLM emitting a tool call, assert the SSE stream carries exactly one
    tool_call event whose patch keys are a subset of the target template."""
    flow = flow_with_source_and_text_ops
    target = next(
        n for n in flow["data"]["nodes"] if n["data"]["type"] == "TextOperationsComponent"
    )
    source = next(
        n for n in flow["data"]["nodes"] if n["data"]["type"] != "TextOperationsComponent"
    )

    body = {
        "flow_id": flow["id"],
        "node_id": target["id"],
        "node_snapshot": {
            "node_id": target["id"],
            "type": "TextOperationsComponent",
            "display_name": target["data"]["node"]["display_name"],
            "description": target["data"]["node"].get("description"),
            "template": target["data"]["node"]["template"],
            "outputs": target["data"]["node"].get("outputs", []),
        },
        "neighbor_snapshots": [
            {
                "node_id": source["id"],
                "type": source["data"]["type"],
                "display_name": source["data"]["node"]["display_name"],
                "description": None,
                "template": source["data"]["node"]["template"],
                "outputs": source["data"]["node"].get("outputs", []),
            }
        ],
        "thread": [],
        "user_message": "Split the upstream text on commas.",
    }

    async with client_authed.stream(
        "POST", "/api/v1/assistant/components/messages", json=body
    ) as resp:
        assert resp.status_code == 200
        events: list[dict] = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                payload = line[6:].strip()
                if payload:
                    events.append(json.loads(payload))

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "propose_config_update"
    patch = tool_calls[0]["args"]["patch"]
    template_keys = set(target["data"]["node"]["template"].keys())
    assert set(patch.keys()).issubset(template_keys)
    assert events[-1]["type"] == "done"


async def test_data_mapper_opts_out_endpoint_returns_400(
    client_authed: AsyncClient, own_flow_id: str
):
    """Direct endpoint call for DataMapperComponent must be refused."""
    body = {
        "flow_id": own_flow_id,
        "node_id": "dm-1",
        "node_snapshot": {
            "node_id": "dm-1",
            "type": "DataMapperComponent",
            "display_name": "Data Mapper",
            "description": None,
            "template": {"mapping": {"display_name": "Mapping", "value": {}}},
            "outputs": [],
        },
        "neighbor_snapshots": [],
        "thread": [],
        "user_message": "help",
    }
    resp = await client_authed.post("/api/v1/assistant/components/messages", json=body)
    assert resp.status_code == 400
```

Fixtures `flow_with_source_and_text_ops` and `scripted_llm_proposes_config` go into `src/backend/tests/integration/conftest.py`. Model them on the existing endpoint-test fixtures under `src/backend/tests/unit/api/v1/conftest.py`. The scripted LLM fixture monkeypatches `_build_llm_client` to return a stub that yields a `tool_call` event whose `patch` uses `TextOperationsComponent`'s actual template keys (at minimum the `operation` field). If `TextOperationsComponent` doesn't exist, substitute the component chosen in Task 12 Step 5 — update the fixture and the test's type names together.

- [ ] **Step 2: Run and confirm passing**

```bash
uv run pytest src/backend/tests/integration/test_component_assist_smoke.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add src/backend/tests/integration/test_component_assist_smoke.py \
        src/backend/tests/integration/conftest.py
git commit -m "test(component-assist): end-to-end smoke for DataMapper proposal roundtrip"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Covered by |
|---|---|
| §1 Architecture — stateless, SSE, single tool, guide registry | Tasks 2–6 |
| §1 ADP red CSS variable | Task 1 |
| §1 Opt-out contract (`assist_enabled`) | Task 3 (registry helper), Task 6 (endpoint 400), Task 11 (frontend icon gate), Task 12A (DataMapper opt-out) |
| §2 Backend files — schemas, registry, prompt, service, endpoint | Tasks 2, 3, 4, 5, 6 |
| §3 Frontend files — store, hook, ProposalBlock, popover, toolbar icon, CSS var | Tasks 1, 7, 8, 9, 10, 11 |
| §4 Data flow (single turn) | Tasks 5 (backend), 8 + 10 (frontend), 13 (smoke) |
| §5 Error handling — invalid patch retry, abort mid-stream, stale apply | Tasks 5 (retry), 8 (abort), 10 (skippedKeys) |
| §6 Testing matrix | Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10, 13 |
| §7 Initial component guide population | **Deferred to the follow-up plan** (Plan 2) — only one non-excluded reference guide lands here (Task 12B) |
| §7 YAML bundle directory | Task 3 (empty `.gitkeep` placeholder) |
| §7 DataMapper exclusion | Task 12A (adds `assist_enabled = False`) |
| §8 Out-of-scope items | Respected — no session cache, no badges, no multi-open |
| §9 Dependencies — flow store mutation reuse | Task 10 uses `setNode` from the existing flowStore |
| §9 DataMapper hands-off | Task 12A constrains DataMapper changes to exactly one line; Task 13 routes its smoke target to a non-excluded component |

**Placeholder scan:** No "TBD"/"TODO"/"implement later" markers. The two softest spots are (a) reliance on `_get_flow_with_org_check` and `_build_llm_client` being importable from `assistant.py` (called out in Task 6 Step 4 with a refactor fallback) and (b) fixture authoring for integration tests (called out explicitly in Task 13 with concrete file paths to mirror). Both are executor-actionable.

**Type consistency:** `ThreadMessage`, `ProposalPayload`, `NodeSnapshot`, and the `propose_config_update` tool name are used consistently across backend tasks 2–6 and frontend tasks 7–10. Event type strings (`token`, `tool_call`, `done`, `error`) match the existing flow-level assistant convention and are consistent across Tasks 5, 6, 8, 13.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-adp-assist-per-component.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good for a plan with this many tasks.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Plan 2 (bulk guide generator for the remaining ~400 components) is written separately and can run after this plan lands.
