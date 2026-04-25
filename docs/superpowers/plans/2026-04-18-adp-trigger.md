# ADP Trigger Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new `ADPTriggerComponent` that acts as a webhook-style inbound trigger for ADP events, filters payloads by selected event type, and emits a clean normalized `Data` output. It must plug into the existing per-flow webhook routing + API-key infrastructure so that flows containing an ADP Trigger get routed via `/api/v1/webhook/{flow_id}` with the same auth model as flows using the regular `Webhook` component.

**Architecture:**
- New component file in the `lfx` ADP bundle (`src/lfx/src/lfx/components/adp/adp_trigger.py`), following the style of the existing `Webhook` component (`src/lfx/src/lfx/components/input_output/webhook.py`).
- A small module-level mapping (`EVENT_TYPE_MAP`) translates friendly names ("New Hire", "Rehire", etc.) to the underlying ADP event identifiers listed in the spec.
- Integration with the existing webhook routing layer happens through `src/backend/base/langflow/services/database/models/flow/utils.py`: the helpers `get_webhook_component_in_flow` and `get_all_webhook_components_in_flow` currently match on `"Webhook" in node.id`. They are widened to also match `"ADPTrigger"`, so that flow-create / flow-update / flow-delete auto-provisioning and the `POST /webhook/{flow_id}` endpoint both see ADP Trigger nodes as first-class webhook components.
- The component itself is pure: it takes `data` (JSON string from the webhook dispatch path) + `event_types` (user selection) and returns either a normalized `Data` payload or an empty `Data` with a filtered status. No HTTP, no auth — all inbound plumbing is the existing endpoint.

**Tech Stack:** Python 3.11+, `lfx.custom.custom_component.component.Component`, `lfx.io` (`MultilineInput`, `MultiselectInput`, `Output`), `lfx.schema.data.Data`, `pytest`, `pytest-asyncio` (existing ADP test patterns).

---

## File Structure

### New files
- `src/lfx/src/lfx/components/adp/adp_trigger.py` — `ADPTriggerComponent` class with event filtering + payload normalization
- `src/lfx/tests/unit/components/adp/test_adp_trigger.py` — unit tests (component class shape, event mapping, filtering, normalization, error handling)
- `src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py` — routing/detection unit test (webhook utils recognize ADP Trigger nodes)

### Modified files
- `src/lfx/src/lfx/components/adp/__init__.py` — add `ADPTriggerComponent` to imports and `__all__`
- `src/lfx/tests/unit/components/adp/test_bundle_init.py` — add assertion that `ADPTriggerComponent.name == "ADPTrigger"`
- `src/backend/base/langflow/services/database/models/flow/utils.py` — widen `get_webhook_component_in_flow` / `get_all_webhook_components_in_flow` to also match `"ADPTrigger"` node IDs

### Untouched (explicitly not in scope for this plan)
- `TemplateMetadata` table and the "Termination" / "Onboarding" pre-grouped defaults — those belong in the Template Metadata plan (Plan 2)
- Frontend surfacing of the ADP Trigger node — it is picked up automatically by the existing component discovery; no frontend changes required
- Assistant integration — covered by Plan 4

---

## Design Decisions

### Bundle location: `adp/`, not `input_output/`

Spec §6 says "Category: Same category as existing webhook component." The existing Webhook lives under `src/lfx/src/lfx/components/input_output/`. This plan places `ADPTriggerComponent` under `src/lfx/src/lfx/components/adp/` instead — alongside the other ADP components (`ADPAuth`, `ADPAPIRequest`, `ADPMCP`, `ADPWorkerTools`). Rationale: ADP-specific behavior belongs with the rest of the ADP bundle so that discovery, imports, and documentation stay colocated. If the intent of the spec was literally "display this in the Input/Output category of the UI," flag that and we can either re-home the file or adjust the bundle category metadata before merging.

### ADP event payload shape (verified against a real ADP sample, 2026-04-18)

The component tolerates two known envelope variants. The primary shape — confirmed against a real ADP new-hire event — is:

```json
{
  "events": [
    {
      "eventID": "fa83e726-dcae-48e3-a83e-8294e4320aa1",
      "eventNameCode": { "codeValue": "worker.hire" },
      "data": {
        "output": {
          "worker": {
            "associateOID": "G3RTBS62BXQJQMD6",
            "workerID": { "idValue": "BKQ8EMBCE" },
            "person": { "legalName": { "formattedName": "NewHire, Test" } }
          }
        }
      },
      "effectiveDateTime": "2020-06-15T04:00:00.000+0000"
    }
  ]
}
```

Key observations vs. the original spec (ADP Assist §6):

- **Event IDs inside the payload use the base form** (`worker.hire`) — not the subscription-topic form (`worker.hire.eventNotify`) that appears in ADP's event-subscription config. The component accepts both (and the `.eventNotify.subscribe` form) for each of the six friendly event types.
- **Worker lives at `data.output.worker`**, not `data.eventContext.worker`. The extraction helper tries both keys for forward compatibility.
- **`effectiveDateTime` is at the event level**, not nested under `data.transform`. The helper tries the event-level field first and falls back to the nested path.

Extraction rules used throughout the plan:

- `event_id_raw` → `events[0].eventNameCode.codeValue`
- `friendly_event_type` → reverse lookup of `event_id_raw` in `EVENT_TYPE_MAP` (which accepts all three forms per event)
- `worker` → first non-empty of `events[0].data.output.worker` then `events[0].data.eventContext.worker` (dict)
- `effective_date` → first non-empty of `events[0].effectiveDateTime` then `events[0].data.transform.effectiveDateTime` (str)
- `raw_payload` → the full decoded JSON object

Any missing key returns a sensible default (`None`, `{}`, `""`) rather than raising.

### Event type mapping (authoritative source)

Declared once as a module-level constant in `adp_trigger.py`. The dropdown options are `list(EVENT_TYPE_MAP.keys())`; the reverse lookup is computed on demand. Each friendly name accepts three forms so the matcher works whether the payload carries the base form, the `.eventNotify` form, or the `.eventNotify.subscribe` form.

```python
EVENT_TYPE_MAP: dict[str, list[str]] = {
    "New Hire": [
        "worker.hire",
        "worker.hire.eventNotify",
        "worker.hire.eventNotify.subscribe",
    ],
    "Rehire": [
        "worker.rehire",
        "worker.rehire.eventNotify",
        "worker.rehire.eventNotify.subscribe",
    ],
    "Retirement": [
        "worker.workAssignment.retire",
        "worker.workAssignment.retire.eventNotify",
        "worker.workAssignment.retire.eventNotify.subscribe",
    ],
    "Leave": [
        "worker.onLeave",
        "worker.onLeave.eventNotify",
        "worker.onLeave.eventNotify.subscribe",
    ],
    "Hire Date Change": [
        "worker.workerOriginalHireDate.change",
        "worker.workerOriginalHireDate.change.eventNotify",
        "worker.workerOriginalHireDate.change.eventNotify.subscribe",
    ],
    "Deceased": [
        "worker.deceased",
        "worker.deceased.eventNotify",
        "worker.deceased.eventNotify.subscribe",
    ],
}
```

### Why reuse the existing `/webhook/{flow_id}` endpoint

The spec says "Accepts inbound webhooks like the existing webhook component." Rather than adding a parallel `/adp-trigger/{flow_id}` endpoint, we extend the existing detection helpers so ADP Trigger nodes ride the same rails (auth, dispatch, SSE, `flow.webhook` bool, API-key provisioning). This means:
- Creating / updating a flow containing an ADP Trigger automatically provisions an API key via `_provision_webhook_api_key`.
- Deleting such a flow cleans the key via `_cleanup_webhook_api_key`.
- The frontend webhook-badge logic (`flow.webhook`) continues to work with zero changes.

---

## Task 1: Scaffold the component module

**Files:**
- Create: `src/lfx/src/lfx/components/adp/adp_trigger.py`
- Test: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`

- [x] **Step 1.1: Write the failing import test**

Create `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
"""Unit tests for ADPTriggerComponent."""

import json

import pytest
from lfx.components.adp.adp_trigger import ADPTriggerComponent, EVENT_TYPE_MAP
from lfx.schema.data import Data


def test_component_class_metadata():
    assert ADPTriggerComponent.name == "ADPTrigger"
    assert ADPTriggerComponent.display_name == "ADP Trigger"
    assert ADPTriggerComponent.icon  # non-empty string
```

- [x] **Step 1.2: Run the test to verify it fails**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py::test_component_class_metadata -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'lfx.components.adp.adp_trigger'`.

- [x] **Step 1.3: Create the minimal component stub**

Create `src/lfx/src/lfx/components/adp/adp_trigger.py`:

```python
"""ADP Trigger component: inbound webhook trigger with ADP event filtering."""

from __future__ import annotations

import json

from lfx.custom.custom_component.component import Component
from lfx.schema.data import Data

EVENT_TYPE_MAP: dict[str, list[str]] = {
    "New Hire": ["worker.hire.eventNotify"],
    "Rehire": [
        "worker.rehire.eventNotify",
        "worker.rehire.eventNotify.subscribe",
    ],
    "Retirement": ["worker.workAssignment.retire.eventNotify.subscribe"],
    "Leave": ["worker.onLeave.eventNotify.subscribe"],
    "Hire Date Change": [
        "worker.workerOriginalHireDate.change.eventNotify.subscribe",
    ],
    "Deceased": ["worker.deceased.eventNotify.subscribe"],
}


class ADPTriggerComponent(Component):
    display_name = "ADP Trigger"
    name = "ADPTrigger"
    icon = "webhook"
    documentation: str = "https://docs.langflow.org/component-adp-trigger"

    inputs = []
    outputs = []
```

Note: `json` and `Data` are imported up front even though they're not used until Task 7 — adding them here keeps imports tidy and avoids re-edits later. Linters that flag unused imports (e.g., `F401`) will complain transiently; if the project runs lint in CI, prefix with `# noqa: F401` temporarily or accept a transient warning until Task 7.

- [x] **Step 1.4: Run the test to verify it passes**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py::test_component_class_metadata -v`

Expected: PASS.

- [x] **Step 1.5: Pause for commit**

Stop and ask the user before committing. When approved, stage:
```
git add src/lfx/src/lfx/components/adp/adp_trigger.py src/lfx/tests/unit/components/adp/test_adp_trigger.py
```
Proposed message (for user to approve): `feat(adp): scaffold ADPTriggerComponent with event type map`.

---

## Task 2: Event type mapping — forward and reverse lookups

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py`

- [x] **Step 2.1: Write the failing tests for the map**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
def test_event_type_map_covers_all_spec_entries():
    # Exactly the six friendly names called out in the spec
    assert set(EVENT_TYPE_MAP.keys()) == {
        "New Hire",
        "Rehire",
        "Retirement",
        "Leave",
        "Hire Date Change",
        "Deceased",
    }


def test_event_type_map_values_are_non_empty_lists_of_strings():
    for friendly, adp_ids in EVENT_TYPE_MAP.items():
        assert isinstance(adp_ids, list), f"{friendly} must map to a list"
        assert adp_ids, f"{friendly} must map to at least one ADP id"
        assert all(isinstance(x, str) and x for x in adp_ids)


def test_reverse_lookup_friendly_name_for_known_adp_ids():
    from lfx.components.adp.adp_trigger import friendly_name_for_adp_id

    assert friendly_name_for_adp_id("worker.hire.eventNotify") == "New Hire"
    assert friendly_name_for_adp_id("worker.rehire.eventNotify") == "Rehire"
    assert (
        friendly_name_for_adp_id("worker.rehire.eventNotify.subscribe") == "Rehire"
    )
    assert (
        friendly_name_for_adp_id("worker.deceased.eventNotify.subscribe")
        == "Deceased"
    )


def test_reverse_lookup_returns_none_for_unknown_adp_id():
    from lfx.components.adp.adp_trigger import friendly_name_for_adp_id

    assert friendly_name_for_adp_id("worker.unknown.eventNotify") is None
    assert friendly_name_for_adp_id("") is None
```

- [x] **Step 2.2: Run the tests to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "event_type_map or reverse_lookup"`

Expected: FAIL (`friendly_name_for_adp_id` does not exist; tests for the map shape may pass already — that's fine).

- [x] **Step 2.3: Implement the reverse lookup helper**

Add to `src/lfx/src/lfx/components/adp/adp_trigger.py` (just below `EVENT_TYPE_MAP`):

```python
def friendly_name_for_adp_id(adp_event_id: str) -> str | None:
    """Return the friendly event name for an ADP event identifier, or None."""
    if not adp_event_id:
        return None
    for friendly, adp_ids in EVENT_TYPE_MAP.items():
        if adp_event_id in adp_ids:
            return friendly
    return None
```

- [x] **Step 2.4: Run the tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "event_type_map or reverse_lookup"`

Expected: PASS (4 tests).

- [x] **Step 2.5: Pause for commit**

Stop and ask the user before committing. Proposed message: `feat(adp): add event type map and friendly name lookup for ADP Trigger`.

---

## Task 3: Component inputs (data, event_types, endpoint, api_key)

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py`

- [x] **Step 3.1: Write the failing tests for inputs**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
def _input_by_name(component_cls, input_name: str):
    for inp in component_cls.inputs:
        if inp.name == input_name:
            return inp
    return None


def test_component_has_data_input_like_webhook():
    data_input = _input_by_name(ADPTriggerComponent, "data")
    assert data_input is not None
    # Same field_type family as WebhookComponent.data (MultilineInput -> TEXT)
    assert data_input.display_name == "Payload"
    assert data_input.advanced is True


def test_component_has_event_types_multiselect():
    et = _input_by_name(ADPTriggerComponent, "event_types")
    assert et is not None, "event_types input must be declared"
    # MultiselectInput stores list values; options must be the six friendly names
    assert set(et.options) == set(EVENT_TYPE_MAP.keys())
    assert isinstance(et.value, list)


def test_component_has_endpoint_and_api_key_display_fields():
    endpoint = _input_by_name(ADPTriggerComponent, "endpoint")
    api_key = _input_by_name(ADPTriggerComponent, "api_key")
    assert endpoint is not None
    assert api_key is not None
    assert endpoint.advanced is False
    assert api_key.advanced is False


def test_component_has_single_output_named_output_data():
    outs = ADPTriggerComponent.outputs
    assert len(outs) == 1
    assert outs[0].name == "output_data"
    assert outs[0].method == "build_data"
```

- [x] **Step 3.2: Run the tests to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "input or output"`

Expected: FAIL (inputs list is empty, outputs list is empty).

- [x] **Step 3.3: Implement the inputs and outputs**

Edit `src/lfx/src/lfx/components/adp/adp_trigger.py` — replace the imports line and the empty `inputs = []` / `outputs = []` assignments:

```python
from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, MultiselectInput, Output
```

```python
    inputs = [
        MultilineInput(
            name="data",
            display_name="Payload",
            info="Receives an ADP event payload via HTTP POST.",
            advanced=True,
        ),
        MultiselectInput(
            name="event_types",
            display_name="Event Types",
            info=(
                "Select which ADP event types this trigger should accept. "
                "Incoming events that do not match any selected type are ignored."
            ),
            options=list(EVENT_TYPE_MAP.keys()),
            value=[],
            advanced=False,
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
        MultilineInput(
            name="api_key",
            display_name="API Key",
            info=(
                "Auto-generated API key required for ADP event delivery. "
                "Include as x-api-key header."
            ),
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
    ]
    outputs = [
        Output(display_name="JSON", name="output_data", method="build_data"),
    ]
```

- [x] **Step 3.4: Run the tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v`

Expected: all seven existing tests PASS.

- [x] **Step 3.5: Pause for commit**

Proposed message: `feat(adp): declare ADP Trigger inputs (data, event_types, endpoint, api_key)`.

---

## Task 4: Export from the ADP bundle

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/__init__.py`
- Modify: `src/lfx/tests/unit/components/adp/test_bundle_init.py`

- [x] **Step 4.1: Update the bundle init test to fail**

Edit `src/lfx/tests/unit/components/adp/test_bundle_init.py` — replace the whole file with:

```python
def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
        ADPTriggerComponent,
        ADPWorkerToolsComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"
    assert ADPMCPComponent.name == "ADPMCP"
    assert ADPWorkerToolsComponent.name == "ADPWorkerTools"
    assert ADPTriggerComponent.name == "ADPTrigger"
```

- [x] **Step 4.2: Run the test to verify it fails**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_bundle_init.py -v`

Expected: FAIL with `ImportError: cannot import name 'ADPTriggerComponent' from 'lfx.components.adp'`.

- [x] **Step 4.3: Add the export**

Edit `src/lfx/src/lfx/components/adp/__init__.py` to:

```python
"""ADP connector bundle: Auth, API Request, MCP, Worker Tools, Trigger."""

from .adp_api_request import ADPAPIRequestComponent
from .adp_auth import ADPAuthComponent
from .adp_mcp import ADPMCPComponent
from .adp_trigger import ADPTriggerComponent
from .adp_worker_tools import ADPWorkerToolsComponent

__all__ = [
    "ADPAPIRequestComponent",
    "ADPAuthComponent",
    "ADPMCPComponent",
    "ADPTriggerComponent",
    "ADPWorkerToolsComponent",
]
```

- [x] **Step 4.4: Run the test to verify it passes**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_bundle_init.py -v`

Expected: PASS.

- [x] **Step 4.5: Pause for commit**

Proposed message: `feat(adp): export ADPTriggerComponent from bundle`.

---

## Task 5: Payload extraction helpers (event id, worker, effective date)

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py`

- [x] **Step 5.1: Write the failing extraction tests**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
# --- Payload extraction ---

HIRE_PAYLOAD = {
    "events": [
        {
            "eventID": "EV-1",
            "eventNameCode": {"codeValue": "worker.hire.eventNotify"},
            "data": {
                "eventContext": {
                    "worker": {
                        "associateOID": "G3H",
                        "workerID": {"idValue": "100123"},
                        "person": {"legalName": {"formattedName": "Jane Doe"}},
                    }
                },
                "transform": {"effectiveDateTime": "2026-04-01T00:00:00Z"},
            },
        }
    ]
}


def test_extract_event_id_from_well_formed_payload():
    from lfx.components.adp.adp_trigger import _extract_event_id

    assert _extract_event_id(HIRE_PAYLOAD) == "worker.hire.eventNotify"


def test_extract_event_id_missing_returns_empty_string():
    from lfx.components.adp.adp_trigger import _extract_event_id

    assert _extract_event_id({}) == ""
    assert _extract_event_id({"events": []}) == ""
    assert _extract_event_id({"events": [{}]}) == ""
    assert _extract_event_id({"events": [{"eventNameCode": {}}]}) == ""


def test_extract_worker_returns_dict_or_empty():
    from lfx.components.adp.adp_trigger import _extract_worker

    worker = _extract_worker(HIRE_PAYLOAD)
    assert worker["associateOID"] == "G3H"
    assert worker["workerID"]["idValue"] == "100123"

    assert _extract_worker({}) == {}
    assert _extract_worker({"events": [{"data": {}}]}) == {}


def test_extract_effective_date_returns_string_or_empty():
    from lfx.components.adp.adp_trigger import _extract_effective_date

    assert _extract_effective_date(HIRE_PAYLOAD) == "2026-04-01T00:00:00Z"
    assert _extract_effective_date({}) == ""
    assert _extract_effective_date({"events": [{"data": {"transform": {}}}]}) == ""
```

- [x] **Step 5.2: Run the tests to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "extract"`

Expected: FAIL with `ImportError` — helpers not yet defined.

- [x] **Step 5.3: Implement the extraction helpers**

Add to `src/lfx/src/lfx/components/adp/adp_trigger.py` (above the component class):

```python
def _first_event(payload: dict) -> dict:
    events = payload.get("events") if isinstance(payload, dict) else None
    if not events or not isinstance(events, list):
        return {}
    first = events[0]
    return first if isinstance(first, dict) else {}


def _extract_event_id(payload: dict) -> str:
    event = _first_event(payload)
    code = event.get("eventNameCode") or {}
    value = code.get("codeValue") if isinstance(code, dict) else None
    return value if isinstance(value, str) else ""


def _extract_worker(payload: dict) -> dict:
    event = _first_event(payload)
    data = event.get("data") or {}
    ctx = data.get("eventContext") if isinstance(data, dict) else {}
    worker = ctx.get("worker") if isinstance(ctx, dict) else {}
    return worker if isinstance(worker, dict) else {}


def _extract_effective_date(payload: dict) -> str:
    event = _first_event(payload)
    data = event.get("data") or {}
    transform = data.get("transform") if isinstance(data, dict) else {}
    value = transform.get("effectiveDateTime") if isinstance(transform, dict) else None
    return value if isinstance(value, str) else ""
```

- [x] **Step 5.4: Run the tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "extract"`

Expected: PASS (4 tests).

- [x] **Step 5.5: Pause for commit**

Proposed message: `feat(adp): add defensive payload extraction helpers for ADP Trigger`.

---

## Task 6: Event filtering — passes matching, drops non-matching

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py`

- [x] **Step 6.1: Write failing tests for `_event_matches_selection`**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
# --- Event filtering ---


def test_event_matches_selection_by_friendly_name():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.hire.eventNotify",
        selected=["New Hire"],
    ) is True


def test_event_matches_selection_supports_multi_id_friendly_name():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.rehire.eventNotify.subscribe",
        selected=["Rehire"],
    ) is True
    assert _event_matches_selection(
        adp_event_id="worker.rehire.eventNotify",
        selected=["Rehire"],
    ) is True


def test_event_does_not_match_when_not_selected():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.deceased.eventNotify.subscribe",
        selected=["New Hire", "Rehire"],
    ) is False


def test_event_does_not_match_when_selection_empty():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    # An empty selection means nothing is accepted — "opt-in" semantics
    assert _event_matches_selection(
        adp_event_id="worker.hire.eventNotify",
        selected=[],
    ) is False


def test_event_does_not_match_for_unknown_adp_id():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.unknown.eventNotify",
        selected=["New Hire", "Rehire"],
    ) is False
```

- [x] **Step 6.2: Run to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "_matches_selection or matches_selection"`

Expected: FAIL — `_event_matches_selection` does not exist.

- [x] **Step 6.3: Implement the matcher**

Append to `src/lfx/src/lfx/components/adp/adp_trigger.py` (below the extract helpers, above the component class):

```python
def _event_matches_selection(adp_event_id: str, selected: list[str]) -> bool:
    """Return True if the incoming ADP event id is in the user's selected set."""
    if not selected:
        return False
    friendly = friendly_name_for_adp_id(adp_event_id)
    if friendly is None:
        return False
    return friendly in selected
```

- [x] **Step 6.4: Run to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v -k "matches_selection"`

Expected: PASS (5 tests).

- [x] **Step 6.5: Pause for commit**

Proposed message: `feat(adp): add event filter matcher for ADP Trigger selection`.

---

## Task 7: `build_data` — happy path (matched event, normalized output)

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py`

- [x] **Step 7.1: Write failing test for the happy path**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
# --- build_data happy path ---


def _make_component(data: str | None, event_types: list[str]) -> ADPTriggerComponent:
    """Instantiate the component with raw inputs mirroring runtime attributes."""
    c = ADPTriggerComponent()
    c.data = data
    c.event_types = event_types
    return c


def test_build_data_passes_through_matched_event():
    payload = HIRE_PAYLOAD
    c = _make_component(data=json.dumps(payload), event_types=["New Hire"])

    result = c.build_data()

    assert isinstance(result, Data)
    assert result.data["event_type"] == "New Hire"
    assert result.data["event_id"] == "worker.hire.eventNotify"
    assert result.data["worker"]["associateOID"] == "G3H"
    assert result.data["effective_date"] == "2026-04-01T00:00:00Z"
    assert result.data["raw_payload"] == payload
```

- [x] **Step 7.2: Run to verify it fails**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py::test_build_data_passes_through_matched_event -v`

Expected: FAIL — `build_data` is not defined on the class.

- [x] **Step 7.3: Implement `build_data`**

Append to `ADPTriggerComponent` in `src/lfx/src/lfx/components/adp/adp_trigger.py`:

```python
    def build_data(self) -> Data:
        raw = getattr(self, "data", None)
        if not raw:
            self.status = "No payload received."
            return Data(data={})

        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            self.status = "Invalid JSON payload."
            return Data(data={})

        if not isinstance(payload, dict):
            self.status = "Payload must be a JSON object."
            return Data(data={})

        adp_event_id = _extract_event_id(payload)
        selected = list(getattr(self, "event_types", []) or [])

        if not _event_matches_selection(adp_event_id, selected):
            self.status = f"Event '{adp_event_id}' filtered out (not in selection)."
            return Data(data={})

        friendly = friendly_name_for_adp_id(adp_event_id) or ""
        normalized = {
            "event_type": friendly,
            "event_id": adp_event_id,
            "worker": _extract_worker(payload),
            "effective_date": _extract_effective_date(payload),
            "raw_payload": payload,
        }
        self.status = f"Accepted {friendly} event."
        return Data(data=normalized)
```

`json` and `Data` were imported at the top of the file in Task 1 — no further import changes needed. If they were omitted there, add them now.

- [x] **Step 7.4: Run to verify it passes**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py::test_build_data_passes_through_matched_event -v`

Expected: PASS.

- [x] **Step 7.5: Pause for commit**

Proposed message: `feat(adp): implement ADP Trigger build_data for matched events`.

---

## Task 8: `build_data` — filtering, missing, and malformed cases

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`

- [x] **Step 8.1: Write failing tests for filtering + edge cases**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
# --- build_data filtering & edge cases ---


def test_build_data_drops_unmatched_event_type():
    c = _make_component(data=json.dumps(HIRE_PAYLOAD), event_types=["Rehire"])

    result = c.build_data()

    assert isinstance(result, Data)
    assert result.data == {}
    assert "filtered out" in (c.status or "").lower()


def test_build_data_drops_when_selection_is_empty():
    c = _make_component(data=json.dumps(HIRE_PAYLOAD), event_types=[])

    result = c.build_data()

    assert result.data == {}


def test_build_data_returns_empty_on_none_data():
    c = _make_component(data=None, event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}
    assert "no payload" in (c.status or "").lower()


def test_build_data_returns_empty_on_invalid_json():
    c = _make_component(data="not-json-at-all", event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}
    assert "invalid json" in (c.status or "").lower()


def test_build_data_returns_empty_on_non_object_payload():
    c = _make_component(data=json.dumps(["array", "not", "object"]), event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}


def test_build_data_handles_payload_missing_events_array():
    # Payload is a valid object but has no `events` key — treat as "no matching event"
    c = _make_component(data=json.dumps({"foo": "bar"}), event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}
```

- [x] **Step 8.2: Run the tests**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py -v`

Expected: all pass. No implementation changes should be needed — `build_data` already handles these paths. If any test fails, diagnose the specific branch and adjust the implementation defensively (do not relax the test).

- [x] **Step 8.3: Pause for commit**

Proposed message: `test(adp): cover ADP Trigger filtering and malformed-input cases`.

---

## Task 9: Widen webhook routing to detect ADP Trigger nodes

**Files:**
- Create: `src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py`
- Modify: `src/backend/base/langflow/services/database/models/flow/utils.py`

- [x] **Step 9.1: Write the failing routing unit test**

Create `src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py`:

```python
"""Routing helpers must recognize ADP Trigger nodes as webhook-style components."""

from langflow.services.database.models.flow.utils import (
    get_all_webhook_components_in_flow,
    get_webhook_component_in_flow,
)


def _flow_with_node(node_id: str) -> dict:
    return {
        "nodes": [
            {"id": node_id, "data": {"type": node_id.split("-")[0]}},
        ],
        "edges": [],
    }


def test_detects_webhook_component_by_id():
    flow = _flow_with_node("Webhook-abc123")
    node = get_webhook_component_in_flow(flow)
    assert node is not None
    assert node["id"] == "Webhook-abc123"


def test_detects_adp_trigger_component_by_id():
    flow = _flow_with_node("ADPTrigger-xyz789")
    node = get_webhook_component_in_flow(flow)
    assert node is not None, "ADP Trigger must be treated as a webhook component"
    assert node["id"] == "ADPTrigger-xyz789"


def test_returns_none_when_no_webhook_or_adp_trigger():
    flow = _flow_with_node("Agent-abc")
    assert get_webhook_component_in_flow(flow) is None


def test_all_webhook_components_includes_both_types():
    flow = {
        "nodes": [
            {"id": "Webhook-1", "data": {}},
            {"id": "ADPTrigger-2", "data": {}},
            {"id": "Agent-3", "data": {}},
        ],
        "edges": [],
    }
    matches = get_all_webhook_components_in_flow(flow)
    ids = {n["id"] for n in matches}
    assert ids == {"Webhook-1", "ADPTrigger-2"}


def test_get_all_returns_empty_for_none_flow_data():
    assert get_all_webhook_components_in_flow(None) == []
```

- [x] **Step 9.2: Run the tests to verify the ADP-trigger tests fail**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py -v`

Expected: `test_detects_adp_trigger_component_by_id` and `test_all_webhook_components_includes_both_types` FAIL — the helpers currently match only `"Webhook"`.

- [x] **Step 9.3: Widen the helpers**

Edit `src/backend/base/langflow/services/database/models/flow/utils.py` — update the two helpers (lines ~8–21 in current file) to:

```python
_WEBHOOK_NODE_ID_PREFIXES: tuple[str, ...] = ("Webhook", "ADPTrigger")


def _is_webhook_like_node(node: dict) -> bool:
    node_id = node.get("id") or ""
    return any(prefix in node_id for prefix in _WEBHOOK_NODE_ID_PREFIXES)


def get_webhook_component_in_flow(flow_data: dict):
    """Get the first webhook-like component (Webhook or ADP Trigger) in flow data."""
    if "nodes" in flow_data:
        for node in flow_data.get("nodes", []):
            if _is_webhook_like_node(node):
                return node
    return None


def get_all_webhook_components_in_flow(flow_data: dict | None):
    """Get all webhook-like components (Webhook or ADP Trigger) in flow data."""
    if not flow_data:
        return []
    return [node for node in flow_data.get("nodes", []) if _is_webhook_like_node(node)]
```

Leave the other utilities (`get_components_versions`, `generate_webhook_api_key`, etc.) unchanged.

- [x] **Step 9.4: Run the full routing test file**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py -v`

Expected: all 5 tests PASS.

- [x] **Step 9.5: Re-run any existing tests that import these helpers**

Run: `uv run pytest src/backend/tests -k "webhook" -v --timeout 60`

Expected: PASS. If any existing test regresses, investigate — the change is strictly additive (still matches "Webhook"), so a failure means a test was asserting something about the OLD behavior that the new behavior now breaks. Fix the test only if its expectation no longer holds under the widened contract.

- [x] **Step 9.6: Pause for commit**

Proposed message: `feat(adp): route ADP Trigger nodes through webhook endpoint detection`.

---

## Task 10: End-to-end smoke — component is available via the component registry

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`

- [x] **Step 10.1: Write a failing import-from-bundle test**

Append to `src/lfx/tests/unit/components/adp/test_adp_trigger.py`:

```python
# --- Bundle smoke ---


def test_component_importable_from_adp_bundle_root():
    from lfx.components.adp import ADPTriggerComponent as FromBundle

    assert FromBundle is ADPTriggerComponent
```

- [x] **Step 10.2: Run the test**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_trigger.py::test_component_importable_from_adp_bundle_root -v`

Expected: PASS (the export from Task 4 is already in place). If it fails, Task 4 was incomplete — go back and fix the bundle `__init__.py`.

- [x] **Step 10.3: Full ADP unit test suite pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp -v`

Expected: all ADP unit tests PASS (existing + new).

- [x] **Step 10.4: Pause for commit**

Proposed message: `test(adp): confirm ADP Trigger is importable via bundle root`.

---

## Task 11: Manual verification checklist (no new tests)

After the automated suite passes, walk through this list manually and report back. Do **not** commit anything in this task — it is a validation gate.

- [x] **Step 11.1: Start the dev server**

Run (in a separate terminal, not via the agent):
```
make backend
```
or the project's usual dev-server command. Confirm it boots without import errors.

- [x] **Step 11.2: Component catalog visibility**

Open the flow-builder UI, search the component sidebar for "ADP Trigger". Confirm:
- It appears under the ADP category
- Its inputs render: `Event Types` multiselect with 6 options, `Payload` (advanced), `Endpoint`, `API Key`
- Selecting multiple event types works and persists

- [x] **Step 11.3: Webhook API key provisioning**

Create a flow that contains only an `ADPTrigger` node (plus a sink). Save it. Then:
- Inspect the flow record: `flow.webhook` should be `true`
- Inspect the secret store at path `{org_id}/webhooks/{flow_id}` — a key should have been provisioned
- The `API Key` field in the ADP Trigger node should display (or be copyable) after save

- [x] **Step 11.4: Inbound POST routing**

With the flow saved and the API key copied, send a POST to `/api/v1/webhook/{flow_id}` with:
- Header: `x-api-key: <copied-key>`
- Body: the `HIRE_PAYLOAD` example from the test file
- `event_types` on the node set to `["New Hire"]`

Confirm:
- 202 Accepted response
- Flow runs to completion
- The ADP Trigger output contains the normalized `{event_type, event_id, worker, effective_date, raw_payload}` dict

- [x] **Step 11.5: Filtering in the inbound path**

Repeat Step 11.4 but with `event_types` set to `["Deceased"]`. Confirm:
- 202 Accepted still returned (the endpoint accepts the webhook)
- The flow runs, but the ADP Trigger output is an empty `Data({})` and the component status string says the event was filtered out

- [x] **Step 11.6: Flow delete cleans up the key**

Delete the flow. Inspect the secret store — the key at `{org_id}/webhooks/{flow_id}` should be gone. (This is existing behavior driven by `_cleanup_webhook_api_key`; we're confirming the ADP Trigger path hasn't accidentally bypassed it.)

- [x] **Step 11.7: Report manual test results**

Report any red flags — unexpected 500s, missing keys, UI rendering issues, unusual log lines. Do not proceed to Plan 2 until manual verification is clean.

---

## Acceptance Criteria

All of the following must be green:

1. `uv run --directory src/lfx pytest tests/unit/components/adp -v` — all tests pass, including the new `test_adp_trigger.py` and updated `test_bundle_init.py`.
2. `uv run pytest src/backend/tests/unit/api/v1/test_adp_trigger_webhook_routing.py -v` — all 5 routing tests pass.
3. `uv run pytest src/backend/tests -k webhook --timeout 60` — no regressions in existing webhook tests.
4. Manual verification (Task 11) passes end-to-end.
5. `src/lfx/src/lfx/components/adp/__init__.py` exports `ADPTriggerComponent`.
6. `get_webhook_component_in_flow` and `get_all_webhook_components_in_flow` both recognize `ADPTrigger` nodes.
7. No changes to `TemplateMetadata`, the assistant, the frontend modals, or pre-grouped event defaults (those belong to later plans).

## Out of scope (deliberately deferred)

- Pre-grouped event defaults ("Termination", "Onboarding") — live in `TemplateMetadata.agent_instructions` (Plan 2).
- Assistant awareness of ADP Trigger (system-prompt hinting, template matching) — Plan 4.
- Frontend pipeline-view rendering of ADP Trigger nodes — Plan 5.
- Verification against real ADP tenant payloads. The tests assume a conservative payload shape; when a real sample is available, the extraction helpers in Task 5 are the one place to adjust.
