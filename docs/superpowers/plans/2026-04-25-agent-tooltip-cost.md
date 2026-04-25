# Agent Tooltip Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show estimated USD cost in the per-vertex node-status tooltip, computed by the existing backend `PricingService` from the actual model used and recorded token counts.

**Architecture:** Backend-exact path. Add a precision-preserving `compute_cost_micros` to `PricingService`. Extend the LFx `Usage` schema with `model_name` + `cost_micros`. Components stash `_model_name` next to existing `_token_usage`. `Vertex.finalize_build` stamps both onto the per-vertex `Usage` before it ships in the build response. Frontend renders a conditional "Estimated cost" tooltip row, hidden when no cost is available.

**Tech Stack:** Python (Pydantic, pytest), TypeScript (React, Jest, RTL), LiteLLM cost map.

**Spec:** `docs/superpowers/specs/2026-04-25-agent-tooltip-cost-design.md`

---

## Task 1: Add `compute_cost_micros` to `PricingService`

**Files:**
- Modify: `src/backend/base/langflow/services/pricing/service.py`
- Test: `src/backend/tests/unit/services/pricing/test_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/backend/tests/unit/services/pricing/test_service.py`:

```python
def test_compute_cost_micros_unknown_model_returns_none():
    service = PricingService(overrides={})
    assert service.compute_cost_micros("totally-made-up/model", input_tokens=1000, output_tokens=1000) is None


def test_compute_cost_micros_zero_tokens_returns_zero():
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    assert service.compute_cost_micros("m", input_tokens=0, output_tokens=0) == 0


def test_compute_cost_micros_known_model_full_cents():
    # 5 cents input + 15 cents output = 20 cents = 200_000 micros
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    assert service.compute_cost_micros("m", input_tokens=1000, output_tokens=1000) == 200_000


def test_compute_cost_micros_sub_cent_positive():
    # 100 input tokens at 1 cent/1k = 0.1 cents = 1000 micros
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=1.0, output_cents_per_1k=0.0)}
    )
    micros = service.compute_cost_micros("m", input_tokens=100, output_tokens=0)
    assert 0 < micros < 10_000
    assert micros == 1000


def test_compute_cost_micros_does_not_affect_compute_cost_cents():
    # Sanity: existing behavior unchanged.
    service = PricingService(overrides={})
    assert service.compute_cost_cents("totally-made-up/model", input_tokens=1, output_tokens=1) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/backend/tests/unit/services/pricing/test_service.py -v`
Expected: 4 new tests FAIL with `AttributeError: 'PricingService' object has no attribute 'compute_cost_micros'`. The fifth (`test_compute_cost_micros_does_not_affect_compute_cost_cents`) should PASS.

- [ ] **Step 3: Add `compute_cost_micros` to PricingService**

In `src/backend/base/langflow/services/pricing/service.py`, append a method to the `PricingService` class right after `compute_cost_cents`:

```python
def compute_cost_micros(
    self, model: str, *, input_tokens: int, output_tokens: int
) -> int | None:
    """Return cost in micro-USD (millionths of a dollar) or None when the model has no pricing data.

    Distinct from compute_cost_cents because:
      - Returns None on unknown model (vs 0), so the caller can distinguish "unpriced" from "free".
      - Preserves sub-cent precision (1 cent = 10_000 micros), so the UI can render "<$0.01" for tiny costs.
    """
    price = self.get_price(model)
    if price is None:
        if model not in self._unknown_logged:
            logger.warning("unknown model for pricing: %s", model)
            self._unknown_logged.add(model)
        return None
    cents = (
        (input_tokens / 1000.0) * price.input_cents_per_1k
        + (output_tokens / 1000.0) * price.output_cents_per_1k
    )
    return int(round(cents * 10_000))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/backend/tests/unit/services/pricing/test_service.py -v`
Expected: all tests PASS (5 new + existing).

- [ ] **Step 5: Stop and ask the user before committing.** Per the user's standing rule, never run `git commit` without explicit permission for this turn. Show the user the staged diff and the proposed commit message:

```
feat(pricing): add compute_cost_micros for precision-preserving cost queries

Returns micro-USD as int, or None when the model has no pricing entry.
Lets callers distinguish "unpriced" from "$0.00" and render sub-cent costs.
Existing compute_cost_cents is untouched (metering still uses it).
```

Wait for the user to approve, then commit only the modified files (no `-A`):

```bash
git add src/backend/base/langflow/services/pricing/service.py \
        src/backend/tests/unit/services/pricing/test_service.py
git commit
```

---

## Task 2: Extend `Usage` schema with `model_name` and `cost_micros`

**Files:**
- Modify: `src/lfx/src/lfx/schema/properties.py`
- Test: `src/lfx/tests/unit/schema/test_properties.py` (create if missing)

- [ ] **Step 1: Write the failing test**

Create or append to `src/lfx/tests/unit/schema/test_properties.py`:

```python
from __future__ import annotations

from lfx.schema.properties import Usage


def test_usage_new_fields_default_to_none():
    u = Usage(input_tokens=10, output_tokens=5, total_tokens=15)
    assert u.model_name is None
    assert u.cost_micros is None


def test_usage_accepts_model_name_and_cost_micros():
    u = Usage(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_name="claude-opus-4-7",
        cost_micros=12345,
    )
    assert u.model_name == "claude-opus-4-7"
    assert u.cost_micros == 12345
```

- [ ] **Step 2: Run tests to verify they fail**

Run from repo root: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/schema/test_properties.py -v`
Expected: FAIL with `ValidationError` on the second test (extra fields not permitted) — first test may PASS only because the attributes don't exist (AttributeError) so confirm both fail.

- [ ] **Step 3: Extend the `Usage` model**

In `src/lfx/src/lfx/schema/properties.py`:

```python
class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    model_name: str | None = None
    cost_micros: int | None = None
```

(Only add the two new fields; leave the rest of the file alone.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/schema/test_properties.py -v`
Expected: PASS.

- [ ] **Step 5: Stop and ask the user before committing.** Show staged files and message:

```
feat(lfx): extend Usage schema with model_name and cost_micros

Both default to None. LFx stays pricing-agnostic; Langflow stamps the values
during finalize_build. Backwards-compatible — existing producers still work.
```

```bash
git add src/lfx/src/lfx/schema/properties.py \
        src/lfx/tests/unit/schema/test_properties.py
git commit
```

---

## Task 3: Add `_model_name` slot to `Component` base class

**Files:**
- Modify: `src/lfx/src/lfx/custom/custom_component/component.py:148` (the line that initializes `_token_usage`)
- Test: `src/lfx/tests/unit/custom/test_component_model_name_slot.py` (create)

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/custom/test_component_model_name_slot.py`:

```python
from __future__ import annotations

from lfx.custom.custom_component.component import Component


def test_fresh_component_has_model_name_slot_defaulted_to_none():
    component = Component()
    assert hasattr(component, "_model_name")
    assert component._model_name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/custom/test_component_model_name_slot.py -v`
Expected: FAIL with `AssertionError: assert hasattr(component, "_model_name")` returning `False`.

- [ ] **Step 3: Add the slot**

In `src/lfx/src/lfx/custom/custom_component/component.py`, find the existing line 148:

```python
self._token_usage: Usage | None = None
```

Add the new slot directly after it:

```python
self._token_usage: Usage | None = None
self._model_name: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/custom/test_component_model_name_slot.py -v`
Expected: PASS.

- [ ] **Step 5: Stop and ask the user before committing.** Message:

```
feat(lfx): add _model_name slot on Component base

Mirror of _token_usage. Token-emitting components will stamp the resolved
model name onto this slot so finalize_build can pair it with the Usage object.
```

```bash
git add src/lfx/src/lfx/custom/custom_component/component.py \
        src/lfx/tests/unit/custom/test_component_model_name_slot.py
git commit
```

---

## Task 4: Stamp `_model_name` at every `_token_usage` write site

**Why one task:** there are 8 sites, each a one-line addition adjacent to an existing `self._token_usage = ...` line. Splitting into 8 tasks is busywork; combining keeps the change atomic and easy to review.

**Sites to edit (search anchors):**

| File | Line (today) | Existing token_usage write | Source for model name |
|------|--------------|---------------------------|----------------------|
| `src/lfx/src/lfx/base/agents/agent.py` | 316 | `self._token_usage = usage_data` | `getattr(self, "model", None)` |
| `src/lfx/src/lfx/base/models/model.py` | 277 | `self._token_usage = usage_data` | `getattr(self, "model_name", None) or getattr(self, "model", None)` |
| `src/lfx/src/lfx/base/models/model.py` | 290 | `self._token_usage = lf_message.properties.usage` | same |
| `src/lfx/src/lfx/components/llm_operations/batch_run.py` | 244 | `self._token_usage = accumulate_usage(...)` | `getattr(self, "model_name", None) or getattr(self, "model", None)` |
| `src/lfx/src/lfx/components/llm_operations/llm_selector.py` | 362 | same | same |
| `src/lfx/src/lfx/components/llm_operations/guardrails.py` | 334 | same | same |
| `src/lfx/src/lfx/components/llm_operations/llm_conditional_router.py` | 255 | `self._token_usage = extract_usage_from_message(response)` | same |
| `src/lfx/src/lfx/components/llm_operations/lambda_filter.py` | 278 | same | same |
| `src/lfx/src/lfx/components/llm_operations/structured_output.py` | 192 | `self._token_usage = token_handler.get_usage()` | same |

(That's 9 sites — `model.py` has two writes. Re-grep at edit time in case lines drift: `rg "_token_usage\s*=" src/lfx/src/lfx`.)

**Files:**
- Modify: each of the files above.
- Test: extend `src/lfx/tests/unit/base/agents/test_agent_token_wiring.py` (Agent case) and add `src/lfx/tests/unit/base/models/test_model_token_wiring.py` (LM case). Other 7 sites are verified by inspection — they all use the identical `self._model_name = getattr(...)` pattern next to an existing tested line.

- [ ] **Step 1: Write the failing Agent test**

Open `src/lfx/tests/unit/base/agents/test_agent_token_wiring.py` and find the existing test that asserts `_token_usage` after a run (around line 79). Add a sibling assertion in the same test (or add a new test using the same fixtures):

```python
# Add inside the existing test that already exercises agent token wiring,
# after the existing `assert agent_component._token_usage == usage` line:
assert agent_component._model_name == agent_component.model
```

- [ ] **Step 2: Write the failing model-component test**

Create `src/lfx/tests/unit/base/models/test_model_token_wiring.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from lfx.base.models.model import LCModelComponent


@pytest.mark.asyncio
async def test_model_component_stamps_model_name_alongside_token_usage():
    """When LCModelComponent extracts usage from an AIMessage, it also stamps _model_name."""

    class FakeModel(LCModelComponent):
        display_name = "Fake"
        name = "fake_model"

        def build_model(self):
            class FakeRunnable:
                async def ainvoke(self, *_a, **_kw):
                    return AIMessage(
                        content="hi",
                        response_metadata={"token_usage": {"prompt_tokens": 3, "completion_tokens": 5}},
                    )

                def with_config(self, *_a, **_kw):
                    return self

            return FakeRunnable()

    component = FakeModel()
    component.model_name = "gpt-4o-mini"
    component.input_value = "hello"
    component.system_message = ""
    component.stream = False
    component.user_id = None

    # Drive the same code path that writes _token_usage today.
    with patch.object(component, "get_langchain_callbacks", return_value=[]), \
         patch.object(component, "get_project_name", return_value="test"):
        await component.get_chat_result(runnable=component.build_model(), stream=False, input_value="hi")

    assert component._token_usage is not None
    assert component._model_name == "gpt-4o-mini"
```

(If the existing model-test infrastructure looks materially different when you actually open the file, mirror its style — the goal is "after a successful usage-extraction call, `_model_name` is set to the component's resolved model".)

- [ ] **Step 3: Run tests to verify they fail**

Run:
```
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest \
  src/lfx/tests/unit/base/agents/test_agent_token_wiring.py \
  src/lfx/tests/unit/base/models/test_model_token_wiring.py -v
```
Expected: FAIL — `agent._model_name` is `None` (Agent doesn't stamp yet); model-component test fails the same way.

- [ ] **Step 4: Add `_model_name` stamps at all 9 sites**

For every site in the table above, insert a stamp line *immediately after* the existing `self._token_usage = ...` line. Use the source-for-model column to determine the right-hand side.

Example — `src/lfx/src/lfx/base/agents/agent.py:316`:

```python
# Before
self._token_usage = usage_data

# After
self._token_usage = usage_data
self._model_name = getattr(self, "model", None)
```

Example — `src/lfx/src/lfx/base/models/model.py:277`:

```python
# Before
self._token_usage = usage_data

# After
self._token_usage = usage_data
self._model_name = getattr(self, "model_name", None) or getattr(self, "model", None)
```

Same pattern for the other 7 sites (use the model-name resolution from the table). Do NOT change the `_token_usage` line itself.

After all edits, re-grep to verify every `_token_usage = ` line has an adjacent `_model_name = ` line:

```
rg -A1 "_token_usage\s*=" src/lfx/src/lfx
```

Every match should show `_model_name = ...` on the next line.

- [ ] **Step 5: Run tests to verify they pass**

Run:
```
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest \
  src/lfx/tests/unit/base/agents/test_agent_token_wiring.py \
  src/lfx/tests/unit/base/models/test_model_token_wiring.py -v
```
Expected: PASS.

- [ ] **Step 6: Run the broader LFx test suite to catch regressions**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit -q`
Expected: PASS (or unchanged from baseline — a previous failing-baseline noise is OK so long as no *new* failures are introduced).

- [ ] **Step 7: Stop and ask the user before committing.** Message:

```
feat(lfx): stamp _model_name alongside _token_usage at all token-emitting sites

Mirrors the existing _token_usage write convention across Agent, LCModelComponent,
batch_run, llm_selector, guardrails, llm_conditional_router, lambda_filter, and
structured_output. finalize_build will read this slot to attach a cost figure.
```

```bash
git add src/lfx/src/lfx/base/agents/agent.py \
        src/lfx/src/lfx/base/models/model.py \
        src/lfx/src/lfx/components/llm_operations/batch_run.py \
        src/lfx/src/lfx/components/llm_operations/llm_selector.py \
        src/lfx/src/lfx/components/llm_operations/guardrails.py \
        src/lfx/src/lfx/components/llm_operations/llm_conditional_router.py \
        src/lfx/src/lfx/components/llm_operations/lambda_filter.py \
        src/lfx/src/lfx/components/llm_operations/structured_output.py \
        src/lfx/tests/unit/base/agents/test_agent_token_wiring.py \
        src/lfx/tests/unit/base/models/test_model_token_wiring.py
git commit
```

---

## Task 5: Stamp model + cost in `Vertex.finalize_build`

**Files:**
- Modify: `src/lfx/src/lfx/graph/vertex/base.py:513-543` (the `_extract_token_usage` and `finalize_build` block)
- Test: `src/lfx/tests/unit/graph/vertex/test_finalize_build_cost.py` (create)

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/graph/vertex/test_finalize_build_cost.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lfx.graph.vertex.base import Vertex
from lfx.schema.properties import Usage


def _make_vertex_stub(*, model_name: str | None, usage: Usage | None) -> Vertex:
    """Construct just enough of a Vertex to invoke finalize_build."""
    stub = Vertex.__new__(Vertex)
    stub.is_output = False
    stub.custom_component = SimpleNamespace(_token_usage=usage, _model_name=model_name)
    stub.id = "vertex-1"
    stub.display_name = "Test"
    stub.outputs_logs = {}
    stub.logs = []
    stub.artifacts_raw = {}
    stub.artifacts = {}
    # Stub helpers used by finalize_build:
    stub.get_built_result = lambda: {}
    stub.set_artifacts = lambda: None
    stub.extract_messages_from_artifacts = lambda *_a, **_kw: []
    stub.set_result = MagicMock()
    return stub


def test_finalize_build_stamps_model_name_and_cost_when_pricing_known():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="my-model", usage=usage)

    pricing = MagicMock()
    pricing.compute_cost_micros.return_value = 123_456

    settings = SimpleNamespace(cost_tracking_enabled=True)

    with patch("lfx.graph.vertex.base.get_pricing_service", return_value=pricing), \
         patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_called_once_with("my-model", input_tokens=1000, output_tokens=500)
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "my-model"
    assert result_data.token_usage.cost_micros == 123_456


def test_finalize_build_skips_cost_when_tracking_disabled():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="my-model", usage=usage)

    pricing = MagicMock()
    settings = SimpleNamespace(cost_tracking_enabled=False)

    with patch("lfx.graph.vertex.base.get_pricing_service", return_value=pricing), \
         patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_not_called()
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "my-model"  # name still stamped
    assert result_data.token_usage.cost_micros is None


def test_finalize_build_skips_cost_when_model_name_missing():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name=None, usage=usage)

    pricing = MagicMock()
    settings = SimpleNamespace(cost_tracking_enabled=True)

    with patch("lfx.graph.vertex.base.get_pricing_service", return_value=pricing), \
         patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_not_called()
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name is None
    assert result_data.token_usage.cost_micros is None


def test_finalize_build_handles_unpriced_model():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="unpriced-model", usage=usage)

    pricing = MagicMock()
    pricing.compute_cost_micros.return_value = None  # unknown model

    settings = SimpleNamespace(cost_tracking_enabled=True)

    with patch("lfx.graph.vertex.base.get_pricing_service", return_value=pricing), \
         patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)):
        vertex.finalize_build()

    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "unpriced-model"
    assert result_data.token_usage.cost_micros is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/vertex/test_finalize_build_cost.py -v`
Expected: FAIL — `model_name` and `cost_micros` aren't being stamped yet; the `get_pricing_service` / `get_settings_service` import targets may not even resolve.

- [ ] **Step 3: Wire model + cost stamping into finalize_build**

In `src/lfx/src/lfx/graph/vertex/base.py`, modify `_extract_token_usage` and `finalize_build` (around lines 513-543).

First, add helper imports near the top of the file (where other lfx/langflow imports live — match existing import style):

```python
from lfx.services.deps import get_settings_service

# get_pricing_service lives in langflow.services.deps, not lfx — import lazily inside
# the helper to avoid a hard cross-package dep at module import time.
```

Then replace the existing `_extract_token_usage` and `finalize_build` methods with:

```python
def _extract_token_usage(self) -> Usage | None:
    """Extract token usage from the custom component if available.

    Output vertices don't show token usage on the node badge because
    the accumulated total is displayed on the chat message instead.
    """
    if self.is_output:
        return None
    if self.custom_component and self.custom_component._token_usage:  # noqa: SLF001
        return self.custom_component._token_usage  # noqa: SLF001
    return None

def _stamp_model_and_cost(self, usage: Usage | None) -> Usage | None:
    """Stamp model_name and cost_micros onto the vertex's Usage in place.

    - model_name is copied from custom_component._model_name when available.
    - cost_micros is computed via PricingService when cost tracking is enabled
      and a model name is set; otherwise left as None.
    Returns the same Usage instance (or None if input was None) for caller convenience.
    """
    if usage is None:
        return None
    model_name = getattr(self.custom_component, "_model_name", None)
    usage.model_name = model_name
    try:
        settings = get_settings_service().settings
        if settings.cost_tracking_enabled and model_name:
            from langflow.services.deps import get_pricing_service  # local import — see comment in extract_token_usage helper
            pricing = get_pricing_service()
            usage.cost_micros = pricing.compute_cost_micros(
                model_name,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
            )
    except Exception:  # noqa: BLE001
        # Pricing is a non-essential cosmetic; never let it break a build.
        usage.cost_micros = None
    return usage

def finalize_build(self) -> None:
    result_dict = self.get_built_result()
    self.set_artifacts()
    artifacts = self.artifacts_raw
    messages = self.extract_messages_from_artifacts(artifacts) if isinstance(artifacts, dict) else []
    token_usage = self._extract_token_usage()
    token_usage = self._stamp_model_and_cost(token_usage)
    result_dict = ResultData(
        results=result_dict,
        artifacts=artifacts,
        outputs=self.outputs_logs,
        logs=self.logs,
        messages=messages,
        component_display_name=self.display_name,
        component_id=self.id,
        token_usage=token_usage,
    )
    self.set_result(result_dict)
```

The broad `except Exception` is intentional and narrowly scoped to the cost-stamp call — the build cycle should never break on a pricing lookup. `cost_micros` falls back to `None` (row hidden in UI), which is the exact "unknown" behavior the spec describes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/vertex/test_finalize_build_cost.py -v`
Expected: PASS.

- [ ] **Step 5: Run the existing vertex/graph tests for regressions**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph -q`
Expected: PASS (or unchanged from baseline).

- [ ] **Step 6: Stop and ask the user before committing.** Message:

```
feat(lfx): stamp model_name + cost_micros on per-vertex Usage in finalize_build

Reads custom_component._model_name and computes cost via PricingService
(gated on settings.cost_tracking_enabled). Pricing is best-effort — a failure
falls back to cost_micros=None and never breaks a build.
```

```bash
git add src/lfx/src/lfx/graph/vertex/base.py \
        src/lfx/tests/unit/graph/vertex/test_finalize_build_cost.py
git commit
```

---

## Task 6: Extend frontend `UsageType`

**Files:**
- Modify: `src/frontend/src/types/chat/index.ts:37-41`

(No standalone test — this is a type-only change. It is exercised end-to-end by Task 8.)

- [ ] **Step 1: Edit the type**

In `src/frontend/src/types/chat/index.ts` find the existing `UsageType`:

```ts
export type UsageType = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
};
```

Replace with:

```ts
export type UsageType = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  model_name?: string | null;
  cost_micros?: number | null;
};
```

- [ ] **Step 2: Verify TypeScript still compiles**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: clean exit, no new errors. (If pre-existing errors are present from other in-flight work, confirm none are new.)

- [ ] **Step 3: Stop and ask the user before committing.** Message:

```
feat(frontend): extend UsageType with model_name and cost_micros

Mirrors the backend Usage schema. Optional fields, default null when absent.
Consumed by the new tooltip cost row in NodeStatus.
```

```bash
git add src/frontend/src/types/chat/index.ts
git commit
```

---

## Task 7: Add `formatUsdFromMicros` helper

**Files:**
- Create: `src/frontend/src/utils/format-currency.ts`
- Test: `src/frontend/src/utils/__tests__/format-currency.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/utils/__tests__/format-currency.test.ts`:

```ts
import { formatUsdFromMicros } from "../format-currency";

describe("formatUsdFromMicros", () => {
  it("returns null for null input", () => {
    expect(formatUsdFromMicros(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(formatUsdFromMicros(undefined)).toBeNull();
  });

  it("returns null for negative input (defensive)", () => {
    expect(formatUsdFromMicros(-1)).toBeNull();
  });

  it("formats genuine zero as $0.00", () => {
    expect(formatUsdFromMicros(0)).toBe("$0.00");
  });

  it("formats sub-cent positives as <$0.01", () => {
    expect(formatUsdFromMicros(1)).toBe("<$0.01");
    expect(formatUsdFromMicros(9_999)).toBe("<$0.01");
  });

  it("formats one cent as $0.01", () => {
    expect(formatUsdFromMicros(10_000)).toBe("$0.01");
  });

  it("formats multi-cent values as $X.XX", () => {
    expect(formatUsdFromMicros(1_234_567)).toBe("$1.23");
    expect(formatUsdFromMicros(99_990_000)).toBe("$99.99");
  });

  it("rounds half-cent up to next cent", () => {
    // 15_000 micros = $0.015, rounded to nearest cent = $0.02 (banker's-style toFixed gives $0.02)
    expect(formatUsdFromMicros(15_000)).toBe("$0.02");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/utils/__tests__/format-currency.test.ts`
Expected: FAIL — `Cannot find module '../format-currency'`.

- [ ] **Step 3: Implement the helper**

Create `src/frontend/src/utils/format-currency.ts`:

```ts
export function formatUsdFromMicros(
  micros: number | null | undefined,
): string | null {
  if (micros == null) return null;
  if (micros < 0) return null;
  if (micros === 0) return "$0.00";
  if (micros < 10_000) return "<$0.01";
  // Round in integer-cent space to avoid IEEE-754 surprises with toFixed(2).
  // (e.g., 0.015.toFixed(2) === "0.01" because 0.015 is stored as 0.01499...)
  const cents = Math.round(micros / 10_000);
  return `$${(cents / 100).toFixed(2)}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/utils/__tests__/format-currency.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 5: Stop and ask the user before committing.** Message:

```
feat(frontend): add formatUsdFromMicros helper

Renders micro-USD as $X.XX. Sub-cent positives render as "<$0.01"; null/undefined/negative return null so callers can hide the row.
```

```bash
git add src/frontend/src/utils/format-currency.ts \
        src/frontend/src/utils/__tests__/format-currency.test.ts
git commit
```

---

## Task 8: Add cost row to `TokenUsageDisplay`

**Why this file (not `NodeStatus/index.tsx`):** the tooltip *content* is already extracted into `BuildStatusDisplay`, with a small `TokenUsageDisplay` component owning the Input/Output token rows. The cost row belongs adjacent to those tokens — same data family. This component is pure (props in, JSX out), so the test renders it directly without zustand/react-flow mocks.

**Files:**
- Modify: `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx`
- Test: `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/__tests__/build-status-display.test.tsx` (create — file + dir)

- [ ] **Step 1: Inspect the existing component**

Open `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx` and read it (it's ~104 lines). Note:
- `TokenUsageDisplay` accepts `tokenUsage: UsageType` and renders two flex rows: one for `input_tokens`, one for `output_tokens`, each `text-xxs` label + `ml-auto font-mono text-xs` value.
- The cost row must match that styling exactly. No coin icon (coins signify token counts, not money).

- [ ] **Step 2: Write the failing test**

Create `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/__tests__/build-status-display.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import BuildStatusDisplay from "../build-status-display";
import { BuildStatus } from "@/constants/enums";
import type { UsageType } from "@/types/chat";

const baseValidationStatus = (token_usage: UsageType | null | undefined) => ({
  data: {
    duration: "1.2s",
    token_usage,
  },
});

const renderTooltip = (token_usage: UsageType | null | undefined) =>
  render(
    <BuildStatusDisplay
      buildStatus={BuildStatus.BUILT}
      validationStatus={baseValidationStatus(token_usage)}
      validationString=""
      lastRunTime="4/25/2026, 7:44:00 AM"
    />,
  );

describe("BuildStatusDisplay cost row", () => {
  it("renders the Estimated cost row with $X.XX when cost_micros is multi-cent", () => {
    renderTooltip({
      input_tokens: 100,
      output_tokens: 50,
      total_tokens: 150,
      cost_micros: 1_234_567,
    });
    expect(screen.getByText(/Estimated cost/i)).toBeInTheDocument();
    expect(screen.getByText("$1.23")).toBeInTheDocument();
  });

  it("renders <$0.01 for sub-cent positive cost", () => {
    renderTooltip({
      input_tokens: 1,
      output_tokens: 0,
      total_tokens: 1,
      cost_micros: 500,
    });
    expect(screen.getByText("<$0.01")).toBeInTheDocument();
  });

  it("renders $0.00 for genuine zero cost", () => {
    renderTooltip({
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_micros: 0,
    });
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  it("hides the cost row when cost_micros is null", () => {
    renderTooltip({
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
      cost_micros: null,
    });
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });

  it("hides the cost row when cost_micros is undefined", () => {
    renderTooltip({
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
    });
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });

  it("does not render any usage rows when token_usage itself is undefined", () => {
    renderTooltip(undefined);
    expect(screen.queryByText(/Input tokens/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/CustomNodes/GenericNode/components/NodeStatus/components/__tests__/build-status-display.test.tsx`
Expected: FAIL — first three assertions error because the cost row doesn't exist yet.

- [ ] **Step 4: Extend `TokenUsageDisplay` with the cost row**

In `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx`:

1. Add the import at the top:

```ts
import { formatUsdFromMicros } from "@/utils/format-currency";
```

2. Replace the existing `TokenUsageDisplay` component with:

```tsx
const TokenUsageDisplay = ({ tokenUsage }: { tokenUsage: UsageType }) => {
  const formattedCost = formatUsdFromMicros(tokenUsage.cost_micros);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center">
        <div className="text-xxs">Input tokens:</div>
        <div className="ml-auto flex items-center gap-1 font-mono text-xs">
          <ForwardedIconComponent name="Coins" className="h-3 w-3" />
          {formatTokenCount(tokenUsage.input_tokens)}
        </div>
      </div>
      <div className="flex items-center">
        <div className="text-xxs">Output tokens:</div>
        <div className="ml-auto flex items-center gap-1 font-mono text-xs">
          <ForwardedIconComponent name="Coins" className="h-3 w-3 text-xs" />
          {formatTokenCount(tokenUsage.output_tokens)}
        </div>
      </div>
      {formattedCost != null && (
        <div className="flex items-center">
          <div className="text-xxs">Estimated cost:</div>
          <div className="ml-auto font-mono text-xs">{formattedCost}</div>
        </div>
      )}
    </div>
  );
};
```

The rest of the file (StatusMessage, TimeStamp, Duration, ValidationDetails, BuildStatusDisplay) is unchanged.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/CustomNodes/GenericNode/components/NodeStatus/components/__tests__/build-status-display.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 6: Manual smoke test in the dev UI**

The user has had problems with NodeStatus rendering in the past (see project memory note about `useGetBuildsQuery` side-effect landmine). Verify in a real browser:

1. Start the backend: `make backend`
2. Start the frontend: `make frontend`
3. Open the UI, drop an Agent component, select a model that's in the LiteLLM cost map (e.g. `gpt-4o-mini`), wire it minimally (input + output), and run it.
4. Hover the green pill on the Agent node. Confirm the tooltip shows an "Estimated cost: $X.XX" row.
5. Drop a Language Model component, run it, confirm the same row appears.
6. Set a model that's NOT in the cost map (e.g. a custom name), run it, confirm the row is HIDDEN.

Document the result in the commit body.

- [ ] **Step 7: Stop and ask the user before committing.** Message:

```
feat(frontend): show estimated cost in node status tooltip

Extended TokenUsageDisplay with an "Estimated cost" row beneath Output tokens,
fed by the new backend-stamped token_usage.cost_micros. Hidden when cost is
unknown or cost-tracking is disabled. Sub-cent costs render as "<$0.01";
genuine zeros render as "$0.00".

Verified in dev UI against gpt-4o-mini (Agent + Language Model components).
```

```bash
git add src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx \
        src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/__tests__/build-status-display.test.tsx
git commit
```

---

## Final verification

After all 8 tasks land, before declaring done:

- [ ] Run the full backend pricing tests: `uv run pytest src/backend/tests/unit/services/pricing/ -v`
- [ ] Run the full LFx unit suite: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit -q`
- [ ] Run the frontend unit suite: `cd src/frontend && npx jest`
- [ ] Confirm the manual smoke test from Task 8 still passes after a clean restart.
- [ ] Skim `git log --oneline` to confirm 8 focused commits, no `git add -A` collateral, no amends.
