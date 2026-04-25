# Assist Scenario Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADP Assist scenarios 2a (detailed prompt) and 2b (vague prompt) work end-to-end on a blank flow — assistant gathers (or accepts) field selection + SFTP credentials + filename pattern, builds the canonical `ADP Trigger → Agent → SFTP CSV Upload` shape, and surfaces the auto-provisioned webhook URL + API key in chat.

**Architecture:** Six code changes plus an upfront verification spike (already complete). (1) An `{datestamp}` filename alias on the SFTP CSV Upload component. (2) A backend bug fix: trigger webhook api_key provisioning from the assistant's persist path (today only the REST `create/update` paths trigger it). (3) A new generic `FlowInspectionTools.get_node_field_value` tool. (4) A new `get_webhook_credentials(flow_id)` tool that reads `endpoint` + `api_key` from the secret store (the api_key isn't in the node template). (5) A new `create_secret_variable(name, value)` tool — for password-typed fields, the assistant creates a variable first, then `set_field_value` with the variable name. (6) System-prompt additions to `SYSTEM_PROMPT_TEMPLATE`: pacing rules, an ADP integration playbook (using the corrected `output_schema` table-row shape and `component_as_tool` → `tools` edge handles), and a template-override note. Manual e2e at the end.

**Tech Stack:** Python 3.12, pytest. Backend assistant service in `src/backend/base/langflow/services/assistant/`. LFX components in `src/lfx/src/lfx/components/`. No frontend changes in this plan.

**Spec:** [`docs/superpowers/specs/2026-04-19-assist-scenario-readiness-design.md`](../specs/2026-04-19-assist-scenario-readiness-design.md)

**Commit discipline:** This plan follows the project's standing rule: stage per task, do NOT commit. The human batches commits at the end of each logical group.

---

## Spike findings (Task 1, complete)

The risk-verification spike confirmed three plan-level surprises. The plan below incorporates them.

1. **api_key surfacing path is broken in two ways.**
   - `_provision_webhook_api_key` (in `api/v1/flows.py:165`) is called only from REST `create_flow` (~line 315) and `update_flow` (~line 568). The assistant's persist path `_persist_assistant_turn` at `api/v1/assistant.py:218` writes `db_flow.data = final_flow_data` (line 272) and **never** invokes `_provision_webhook_api_key`. Result: when the assistant adds an ADP Trigger, no key is provisioned. → fixed in **Task 3**.
   - When provisioning runs, the api_key lives in the secret store keyed `{org_id}/webhooks/{flow_id}`, **not** in the node template. So `get_node_field_value(trigger, "api_key")` would never return it. → solved by the new **Task 5** tool `get_webhook_credentials(flow_id)`.

2. **Agent's structured-output input is `output_schema`, a `TableInput` of row dicts** — not a JSON schema. Each row: `{name, description, type ("str"|"int"|"float"|"bool"|"dict"), multiple (bool)}` (see `src/lfx/src/lfx/components/models_and_agents/agent.py:128-173`). The Agent builds the Pydantic model itself. → playbook in **Task 7** teaches this shape, with example rows.

3. **`SecretStrInput` routing through `set_field_value` is silently broken.** `SecretStrInput` has `load_from_db=True`, so the runtime treats the stored value as a *variable name* to look up. Setting `password = "P@ssword1!"` writes the literal but the SFTP component then fails looking up a variable named `P@ssword1!`. → solved by new **Task 6** tool `create_secret_variable(name, value)` plus playbook guidance (Task 7) telling the assistant to create the variable first and pass the variable name to `set_field_value`. Future metadata work will tag fields as "secret" so the assistant knows when to use this; for now the playbook lists the fields explicitly.

**No-op confirmations** (no plan change):
- Tool-attach edges work via `connect_edge` as-is. Source output handle: `component_as_tool`, target input field: `tools`. (Sample edge in `initial_setup/starter_projects/Simple Agent.json:36-63`.)
- SFTP test file exists at `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py` — Task 2 extends it.

---

## File Structure

**New files:**
- `src/backend/base/langflow/services/assistant/tools/inspection.py` — `FlowInspectionTools` class with `get_node_field_value` and `get_webhook_credentials`.
- `src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py`
- `src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py`
- `src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py` — covers the new mutation tool.
- `src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py` — covers Task 3.
- `src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py`
- `src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py`
- `src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py`

**Modified files:**
- `src/backend/base/langflow/api/v1/assistant.py` — `_persist_assistant_turn` calls `_provision_webhook_api_key` after writing `db_flow.data` (Task 3).
- `src/backend/base/langflow/services/assistant/tools/registry.py` — adds `INSPECTION_TOOLS` (with `get_node_field_value` + `get_webhook_credentials`); adds `create_secret_variable` to `MUTATION_TOOLS`; adds `is_inspection_tool` predicate; updates `ALL_TOOLS`.
- `src/backend/base/langflow/services/assistant/tools/mutation.py` — adds `create_secret_variable` method to `FlowMutationTools`.
- `src/backend/base/langflow/services/assistant/service.py` — imports `FlowInspectionTools` + `is_inspection_tool`; constructs `self.inspection_tools`; adds inspection dispatch branch in `_execute_tool`; extends `SYSTEM_PROMPT_TEMPLATE` (lines 41–98) with three new blocks.
- `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py` — `{datestamp}` alias in `_resolve_remote_path` (line 65) and the filename input's `info=` string (line 185).
- `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py` — adds the `{datestamp}` test case.

**Note on integration testing:** No scripted-LLM "integration tests" for Scenarios A/B. Without a real LLM, scripted-provider tests just assert your own scripts. Unit tests cover the contract (prompt content + tool wiring + alias rendering); manual e2e (Task 8) covers actual LLM behavior.

---

## Task 1: Discovery & risk verification spike

**STATUS: COMPLETE.** See "Spike findings" section above. Downstream tasks already incorporate the findings.

---

## Task 2: SFTP `{datestamp}` filename alias

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py:65-73` (`_resolve_remote_path`) and line 185 (`info=` string).
- Modify: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py` — add the new test case.

Smallest, isolated change. Single-line addition + info-string update + one test.

- [x] **Step 1: Read the current function**

Open `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py:65-73` to confirm shape:

```python
def _resolve_remote_path(
    remote_directory: str, filename: str, *, now: _time.struct_time | None = None
) -> str:
    when = now if now is not None else _time.gmtime()
    rendered = filename.replace("{timestamp}", _time.strftime("%Y%m%d_%H%M%S", when))
    rendered = rendered.replace("{date}", _time.strftime("%Y%m%d", when))
    if "/" in rendered:
        msg = "filename must not contain path separator '/'; use remote_directory"
```

- [x] **Step 2: Add the failing test**

Open `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`. Read the existing test fixtures and patterns first, then add this test alongside the others (re-using existing imports if compatible):

```python
def test_resolve_remote_path_replaces_datestamp_alias_with_full_timestamp():
    import time as _time
    from lfx.components.sftp.sftp_csv_upload import _resolve_remote_path

    fixed = _time.strptime("2026-04-19 14:30:52", "%Y-%m-%d %H:%M:%S")
    result = _resolve_remote_path("/uploads", "test-{datestamp}.csv", now=fixed)
    assert result == "/uploads/test-20260419_143052.csv"
```

- [x] **Step 3: Run test to verify it fails**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py::test_resolve_remote_path_replaces_datestamp_alias_with_full_timestamp -v
```

Expected: FAIL with the literal `{datestamp}` left in the result.

- [x] **Step 4: Add the alias replacement**

Edit `_resolve_remote_path` to insert one line above the existing `{timestamp}` replacement:

```python
def _resolve_remote_path(
    remote_directory: str, filename: str, *, now: _time.struct_time | None = None
) -> str:
    when = now if now is not None else _time.gmtime()
    rendered = filename.replace("{datestamp}", _time.strftime("%Y%m%d_%H%M%S", when))
    rendered = rendered.replace("{timestamp}", _time.strftime("%Y%m%d_%H%M%S", when))
    rendered = rendered.replace("{date}", _time.strftime("%Y%m%d", when))
    if "/" in rendered:
        msg = "filename must not contain path separator '/'; use remote_directory"
```

- [x] **Step 5: Update the `info=` text on the filename input**

Edit line 185 of `sftp_csv_upload.py`:

```python
            info="Supports {timestamp} (UTC YYYYMMDD_HHMMSS), {datestamp} (alias for {timestamp}), and {date} (UTC YYYYMMDD).",
```

- [x] **Step 6: Run test to verify it passes + the rest of the SFTP tests**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: ALL PASS.

- [x] **Step 7: Stage**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py \
        src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
```

Do NOT commit. Human batches.

---

## Task 3: Trigger webhook api_key provisioning from the assistant persist path

**Files:**
- Modify: `src/backend/base/langflow/api/v1/assistant.py` — `_persist_assistant_turn` (~line 218; the function that writes `db_flow.data = final_flow_data` near line 272).
- Create: `src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py`.

Backend fix. The auto-provisioner `_provision_webhook_api_key` exists in `api/v1/flows.py:165`. It's called by `create_flow` and `update_flow` but not by the assistant's persist path. So when the assistant adds an ADP Trigger via mutation tools and writes the flow back, no api_key is provisioned. Mirror what `update_flow` does after writing `db_flow.data`.

- [x] **Step 1: Read the existing call sites in `api/v1/flows.py`**

```bash
grep -n "_provision_webhook_api_key" /Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v1/flows.py
```

Open the function definition at line ~165 and both call sites. Note exactly what they pass (typically: `session`, the loaded flow object, the org id) and any error handling. The assistant call needs to mirror the same arguments.

- [x] **Step 2: Read `_persist_assistant_turn`**

Open `src/backend/base/langflow/api/v1/assistant.py` around line 218 and read the function end to end. Find the exact line that writes `db_flow.data = final_flow_data` and the surrounding session/commit shape.

- [x] **Step 3: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py`. The test must:

1. Create a flow that has an ADP Trigger node (or generic webhook-like node — use `_is_webhook_like_node` from `services/database/models/flow/utils.py` to confirm what counts).
2. Call `_persist_assistant_turn` with that flow data.
3. Assert that an entry exists in the secret store at `{org_id}/webhooks/{flow_id}` with an `api_key` field.

Use the in-memory secret store backend (per the secret store factory in `services/secret_store/`). Inspect existing tests under `src/backend/tests/unit/api/v1/` for the assistant fixture pattern (e.g., `test_assistant_stream_partial_persistence.py`) and reuse it.

```python
# Sketch — fill in based on existing assistant test fixtures
import pytest
from langflow.api.v1.assistant import _persist_assistant_turn
from langflow.services.secret_store.factory import get_secret_store


@pytest.mark.asyncio
async def test_persist_provisions_api_key_when_assistant_adds_webhook(
    db_session, org_user, flow_with_no_webhook
):
    # Add a webhook-like node to the flow data the assistant produces
    final_flow_data = {
        "nodes": [
            {
                "id": "ADPTrigger-1",
                "data": {"node": {"template": {
                    "_type": {"value": "ADPTriggerComponent"},
                }}},
                "type": "genericNode",
            }
        ],
        "edges": [],
    }
    await _persist_assistant_turn(
        session=db_session,
        flow_id=flow_with_no_webhook.id,
        final_flow_data=final_flow_data,
        # ... other args per the real signature
    )
    store = get_secret_store()
    entry = await store.get(f"{flow_with_no_webhook.organization_id}/webhooks/{flow_with_no_webhook.id}")
    assert entry is not None
    assert entry.get("api_key")
```

If the existing fixtures don't expose what you need, BLOCK and report — don't fabricate state.

- [x] **Step 4: Run the test to verify it fails**

```bash
pytest src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py -v
```

Expected: FAIL — no secret store entry exists.

- [x] **Step 5: Implement the fix**

In `src/backend/base/langflow/api/v1/assistant.py`, after the `db_flow.data = final_flow_data` write and before the session commit, add a call mirroring what `update_flow` does. Reuse the same imports — `_provision_webhook_api_key` from `api.v1.flows` (or move it to a shared util if importing from flows.py creates a circular import; in that case factor it out into `api/v1/_webhook_provisioning.py` or similar and import from both sites).

The shape will look roughly like:

```python
db_flow.data = final_flow_data
await _provision_webhook_api_key(session, db_flow, current_org.id)
await session.commit()
```

(Exact arg order per the real function signature found in Step 1.)

- [x] **Step 6: Run test to verify it passes**

```bash
pytest src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py -v
```

Expected: PASS.

- [x] **Step 7: Run the broader assistant test suite to confirm nothing broke**

```bash
pytest src/backend/tests/unit/api/v1/test_assistant_stream_partial_persistence.py \
       src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py -v
```

Expected: ALL PASS.

- [x] **Step 8: Stage**

```bash
git add src/backend/base/langflow/api/v1/assistant.py \
        src/backend/tests/unit/api/v1/test_assistant_persist_provisions_api_key.py
```

(If you factored out a shared util, stage that file too.)

---

## Task 4: `FlowInspectionTools.get_node_field_value`

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/inspection.py`
- Create: `src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py`

Generic read-back tool. Useful for non-secret fields the assistant wants to surface (component model name an agent picked, endpoint URLs, etc.). The webhook api_key is NOT one of these (it's in the secret store, not the template) — that's Task 5.

- [x] **Step 1: Read `mutation.py` to mirror its shape**

Open `src/backend/base/langflow/services/assistant/tools/mutation.py`. Confirm the constructor signature (it takes `flow_data`) and how methods access `flow_data["nodes"]`. Mirror this for `FlowInspectionTools`.

- [x] **Step 2: Write the failing tests**

Create `src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py`:

```python
from langflow.services.assistant.tools.inspection import FlowInspectionTools


def _flow_with_node(node_id: str, template_fields: dict) -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "data": {
                    "node": {
                        "template": {
                            name: {"value": value} for name, value in template_fields.items()
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


def test_get_node_field_value_returns_string_value():
    flow = _flow_with_node("trigger-1", {"endpoint": "http://example.com/webhook/abc"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "endpoint") == "http://example.com/webhook/abc"


def test_get_node_field_value_returns_empty_string_when_value_empty():
    flow = _flow_with_node("trigger-1", {"endpoint": ""})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "endpoint") == ""


def test_get_node_field_value_returns_node_not_found_error():
    flow = _flow_with_node("trigger-1", {"endpoint": "x"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("missing-id", "endpoint") == "node not found: missing-id"


def test_get_node_field_value_returns_field_not_found_error():
    flow = _flow_with_node("trigger-1", {"endpoint": "x"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "missing_field") == "field not found on node: missing_field"


def test_get_node_field_value_coerces_non_string_values_to_string():
    flow = _flow_with_node("trigger-1", {"port": 22})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "port") == "22"
```

- [x] **Step 3: Run tests to verify they fail**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 4: Implement `FlowInspectionTools`**

Create `src/backend/base/langflow/services/assistant/tools/inspection.py`:

```python
from __future__ import annotations

from typing import Any


class FlowInspectionTools:
    """Read-only inspection of the active flow's node state.

    Sibling to FlowMutationTools. Used by the assistant to surface
    field values (e.g. an endpoint a component computed) back to the
    user. For webhook api_keys, use get_webhook_credentials — they
    live in the secret store, not the node template.
    """

    def __init__(self, flow_data: dict[str, Any]) -> None:
        self.flow_data = flow_data

    def get_node_field_value(self, node_id: str, field_name: str) -> str:
        """Return the current value of one field on one node as a string.

        Returns the string value, or a clear error string:
        - "node not found: <id>" when node_id doesn't exist.
        - "field not found on node: <name>" when field_name is absent.
        Empty values return "".
        """
        node = next((n for n in self.flow_data.get("nodes", []) if n.get("id") == node_id), None)
        if node is None:
            return f"node not found: {node_id}"
        template = node.get("data", {}).get("node", {}).get("template", {})
        if field_name not in template:
            return f"field not found on node: {field_name}"
        value = template[field_name].get("value", "")
        if value is None:
            return ""
        return str(value)
```

- [x] **Step 5: Run tests to verify they pass**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py -v
```

Expected: 5 PASS.

- [x] **Step 6: Add registry entry + dispatch wiring**

Open `src/backend/base/langflow/services/assistant/tools/registry.py`. Add a new constant block immediately after `MUTATION_TOOLS` (Task 5 will add a second entry to this same block):

```python
INSPECTION_TOOLS = [
    {
        "name": "get_node_field_value",
        "description": (
            "Read the current value of one field on one node in the active flow. "
            "Use for surfacing values like an endpoint URL a component computed. "
            "For webhook API keys use get_webhook_credentials instead — those "
            "live in the secret store, not the node template. Returns the value "
            "as a string, or an error string starting with 'node not found:' or "
            "'field not found on node:'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "The node's id from the canvas summary."},
                "field_name": {
                    "type": "string",
                    "description": "Template field name (backtick-style, e.g. 'endpoint'). Not the display name.",
                },
            },
            "required": ["node_id", "field_name"],
        },
    },
]


def is_inspection_tool(name: str) -> bool:
    return any(t["name"] == name for t in INSPECTION_TOOLS)
```

Update `ALL_TOOLS`:

```python
ALL_TOOLS = CATALOG_TOOLS + MUTATION_TOOLS + INSPECTION_TOOLS
```

Open `src/backend/base/langflow/services/assistant/service.py`:

**(a)** Update the import on line 17:

```python
from langflow.services.assistant.tools.registry import (
    get_tools_for_anthropic,
    get_tools_for_openai,
    is_catalog_tool,
    is_inspection_tool,
    is_mutation_tool,
)
```

**(b)** Add a `FlowInspectionTools` import alongside the existing `FlowMutationTools` import.

**(c)** In `__init__` (lines 121–139), add construction of inspection tools next to mutation tools:

```python
        self.mutation_tools = FlowMutationTools(flow_data)
        self.inspection_tools = FlowInspectionTools(flow_data)
```

**(d)** In `_execute_tool` (lines 200–217), add a third branch between the mutation branch and the unknown-tool fallback:

```python
            elif is_inspection_tool(name):
                method = getattr(self.inspection_tools, name)
                result = method(**args)
                return {"result": result}
```

- [x] **Step 7: Add a service-level dispatch test**

Append to the same test file (or create `test_inspection_dispatch.py` if you prefer a separate file):

```python
import pytest
from langflow.services.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_get_node_field_value_dispatches_to_inspection_tools():
    flow_data = {
        "nodes": [{"id": "trigger-1", "data": {"node": {"template": {"endpoint": {"value": "http://x"}}}}}],
        "edges": [],
    }
    service = AssistantService.__new__(AssistantService)
    from langflow.services.assistant.tools.inspection import FlowInspectionTools
    from langflow.services.assistant.tools.mutation import FlowMutationTools
    service.flow_data = flow_data
    service.mutation_tools = FlowMutationTools(flow_data)
    service.inspection_tools = FlowInspectionTools(flow_data)
    result = await service._execute_tool(
        "get_node_field_value", {"node_id": "trigger-1", "field_name": "endpoint"}
    )
    assert result == {"result": "http://x"}
```

If `AssistantService.__init__` requires more state, inspect `src/backend/tests/unit/test_assistant_service.py` for the canonical construction pattern and use that.

- [x] **Step 8: Run the dispatch + unit tests + the rest of the assistant suite**

```bash
pytest src/backend/tests/unit/services/assistant/ src/backend/tests/unit/test_assistant_service.py -v
```

Expected: ALL PASS.

- [x] **Step 9: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/inspection.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py
```

---

## Task 5: `get_webhook_credentials(flow_id)` tool

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/inspection.py` (add second method).
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py` (add second entry to `INSPECTION_TOOLS`).
- Create: `src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py`.

The webhook api_key lives in the secret store at `{org_id}/webhooks/{flow_id}` (per `_provision_webhook_api_key` in `api/v1/flows.py:165`). The endpoint URL is the well-known `<base>/api/v1/webhook/<flow_id>` path. This tool returns both for the assistant to surface in chat.

**Key constraint:** `FlowInspectionTools` was constructed with only `flow_data` in Task 4. To read from the secret store, `get_webhook_credentials` needs at minimum the `org_id` and `flow_id`. Two choices:

1. **Pass them at construction:** `FlowInspectionTools(flow_data, org_id, flow_id, base_url)`. The `AssistantService` already has these (`self.org_id`, `self.flow_id`). Wire them in.
2. **Pass them as method args:** `get_webhook_credentials(flow_id)` and have the tool internally look up `org_id` from a service ref.

Use **option 1** — keeps the tool signature minimal (the LLM doesn't need to know its own flow_id) and matches how `FlowMutationTools` is built. The tool's parameter list to the LLM is empty.

- [x] **Step 1: Update `FlowInspectionTools.__init__` to accept context**

Edit `inspection.py`:

```python
class FlowInspectionTools:
    def __init__(
        self,
        flow_data: dict[str, Any],
        *,
        flow_id: Any | None = None,
        org_id: Any | None = None,
        base_url: str | None = None,
    ) -> None:
        self.flow_data = flow_data
        self.flow_id = flow_id
        self.org_id = org_id
        self.base_url = base_url
```

The `*` keeps `flow_data` as the only positional arg so existing tests don't break. The new context fields default to `None` so existing call sites (Task 4's tests) keep working.

- [x] **Step 2: Update `AssistantService.__init__` to pass the context**

In `src/backend/base/langflow/services/assistant/service.py`, change:

```python
self.inspection_tools = FlowInspectionTools(flow_data)
```

to:

```python
self.inspection_tools = FlowInspectionTools(
    flow_data,
    flow_id=flow_id,
    org_id=org_id,
    base_url=self._get_base_url(),  # see Step 3
)
```

`flow_id` and `org_id` are already constructor args of `AssistantService` (see lines 121–139). The base URL needs sourcing — see Step 3.

- [x] **Step 3: Source the base URL**

Find how the existing webhook URL is rendered today (look for code that constructs the webhook URL in `api/v1/flows.py` or elsewhere). Common langflow pattern: read from app settings.

```bash
grep -rn "webhook" /Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/settings/ | head
grep -rn "base_url\|BASE_URL\|host_url" /Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/settings/ | head
```

If there's an existing setting, add a small helper `_get_base_url()` on `AssistantService` that reads it. If not, derive from the request context that constructed the service (`api/v1/assistant.py` should have access to the `Request` object — pass `base_url` down). Make a best-effort choice and document in the task report.

If sourcing the base URL turns out to be ambiguous, **report back as DONE_WITH_CONCERNS** with a recommendation, rather than guessing.

- [x] **Step 4: Write the failing tests**

Create `src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py`:

```python
import pytest
from uuid import uuid4

from langflow.services.assistant.tools.inspection import FlowInspectionTools


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_endpoint_and_api_key(monkeypatch):
    org_id = uuid4()
    flow_id = uuid4()
    fake_store = {f"{org_id}/webhooks/{flow_id}": {"api_key": "lf_secret_xyz"}}

    class FakeStore:
        async def get(self, key):
            return fake_store.get(key)

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=flow_id,
        org_id=org_id,
        base_url="https://example.com",
    )
    result = await tools.get_webhook_credentials()
    assert result == {
        "endpoint": f"https://example.com/api/v1/webhook/{flow_id}",
        "api_key": "lf_secret_xyz",
    }


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_error_when_no_key_provisioned(monkeypatch):
    class FakeStore:
        async def get(self, key):
            return None

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=uuid4(),
        org_id=uuid4(),
        base_url="https://example.com",
    )
    result = await tools.get_webhook_credentials()
    assert result == {
        "error": "no webhook api_key provisioned for this flow yet — make sure an ADP Trigger or Webhook component is in the flow and the change has been persisted",
    }
```

- [x] **Step 5: Run tests to verify they fail**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py -v
```

Expected: FAIL with `AttributeError: 'FlowInspectionTools' object has no attribute 'get_webhook_credentials'`.

- [x] **Step 6: Implement `get_webhook_credentials`**

Add to `inspection.py`:

```python
from langflow.services.secret_store.factory import get_secret_store


# ... inside FlowInspectionTools:

    async def get_webhook_credentials(self) -> dict[str, str]:
        """Return the webhook URL and API key for the active flow.

        Reads the api_key from the secret store at {org_id}/webhooks/{flow_id}
        (provisioned by _provision_webhook_api_key when the flow is saved).
        Returns {"endpoint": ..., "api_key": ...} on success or
        {"error": ...} when no key has been provisioned yet.
        """
        if self.org_id is None or self.flow_id is None or self.base_url is None:
            return {"error": "webhook credentials unavailable: missing flow context"}
        store = get_secret_store()
        entry = await store.get(f"{self.org_id}/webhooks/{self.flow_id}")
        if not entry or not entry.get("api_key"):
            return {
                "error": (
                    "no webhook api_key provisioned for this flow yet — make "
                    "sure an ADP Trigger or Webhook component is in the flow "
                    "and the change has been persisted"
                ),
            }
        return {
            "endpoint": f"{self.base_url}/api/v1/webhook/{self.flow_id}",
            "api_key": entry["api_key"],
        }
```

The exact import path for `get_secret_store` may differ — confirm by reading `src/backend/base/langflow/services/secret_store/`. If the actual signature returns `dict | None` directly vs. a wrapper, adjust the test fakes accordingly.

- [x] **Step 7: Add the registry entry**

Append to `INSPECTION_TOOLS` in `registry.py`:

```python
    {
        "name": "get_webhook_credentials",
        "description": (
            "Return the webhook URL and API key for the active flow as "
            "{endpoint, api_key}. Use after adding a webhook-like component "
            "(ADP Trigger or Webhook) and confirming persistence. Returns "
            "{error: ...} if no key has been provisioned yet."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
```

(No parameters — context comes from the service's flow.)

- [x] **Step 8: Update the dispatch branch to await async inspection tools**

Task 4 wrote the inspection branch as synchronous. Now we need it to handle async methods. Edit `_execute_tool` in `service.py`:

```python
            elif is_inspection_tool(name):
                import asyncio
                method = getattr(self.inspection_tools, name)
                result = method(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                return {"result": result}
```

(Mirrors the mutation branch's coroutine handling.)

- [x] **Step 9: Run tests to verify they pass**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py \
       src/backend/tests/unit/services/assistant/tools/test_inspection_get_node_field_value.py -v
```

Expected: ALL PASS.

- [x] **Step 10: Run the broader assistant suite**

```bash
pytest src/backend/tests/unit/services/assistant/ src/backend/tests/unit/test_assistant_service.py -v
```

Expected: ALL PASS.

- [x] **Step 11: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/inspection.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/tools/test_inspection_get_webhook_credentials.py
```

---

## Task 6: `create_secret_variable(name, value)` mutation tool

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/mutation.py` — add `create_secret_variable` method to `FlowMutationTools`.
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py` — add to `MUTATION_TOOLS`.
- Create: `src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py`.

For password-typed fields the assistant cannot pass a literal to `set_field_value` — `SecretStrInput.load_from_db=True` causes the runtime to treat the stored string as a variable *name*. The assistant flow becomes:

1. `create_secret_variable("sftp_password_<short>", "P@ssword1!")` → creates a variable in the variable store.
2. `set_field_value(node_id, "password", "sftp_password_<short>")` → writes the variable name into the field. At runtime, the SFTP component looks up the variable and gets the real value.

Forward-compat note (per user direction): future metadata work will tag fields as "secret" so the assistant knows when to use this tool. For now the playbook (Task 7) lists the known secret fields explicitly.

- [x] **Step 1: Locate the variable store API**

```bash
grep -rn "class.*VariableService\|create_variable\|variable_service" \
  /Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/variable/ | head -30
grep -rn "user_variables\|/variables" \
  /Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v1/ | head -20
```

Find the canonical Python entry point (probably `VariableService.create_variable(...)` or similar). Note its signature (does it require `user_id`? `org_id`? a session?). Note where the value gets encrypted/persisted.

- [x] **Step 2: Confirm the FlowMutationTools constructor**

Open `src/backend/base/langflow/services/assistant/tools/mutation.py`. Read the `__init__` signature. Variables need at least `user_id` (variables are scoped per user in most Langflow installs). If the constructor doesn't already have it, add it as a kwarg-only param the same way Task 5 added context to `FlowInspectionTools`.

- [x] **Step 3: Update `AssistantService` to pass user_id (and any other needed context) to mutation_tools**

If the mutation_tools constructor needs new params, update `service.py:138` to pass them. (`AssistantService.__init__` already takes `user_id` per the existing file.)

- [x] **Step 4: Write the failing test**

Create `src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py`:

```python
import pytest
from uuid import uuid4

from langflow.services.assistant.tools.mutation import FlowMutationTools


@pytest.mark.asyncio
async def test_create_secret_variable_writes_to_variable_store(monkeypatch):
    user_id = uuid4()
    captured = []

    class FakeVariableService:
        async def create_variable(self, *, user_id, name, value, **_):
            captured.append({"user_id": user_id, "name": name, "value": value})
            return {"id": uuid4(), "name": name}

    # Patch the import path your implementation uses
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: FakeVariableService(),
    )

    tools = FlowMutationTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.create_secret_variable(name="sftp_password_abc", value="P@ssword1!")

    assert result == {"variable_name": "sftp_password_abc"}
    assert captured == [{"user_id": user_id, "name": "sftp_password_abc", "value": "P@ssword1!"}]


@pytest.mark.asyncio
async def test_create_secret_variable_returns_error_when_user_id_missing(monkeypatch):
    tools = FlowMutationTools({"nodes": [], "edges": []})
    result = await tools.create_secret_variable(name="x", value="y")
    assert result == {"error": "cannot create secret variable: missing user context"}
```

- [x] **Step 5: Run tests to verify they fail**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py -v
```

Expected: FAIL.

- [x] **Step 6: Implement `create_secret_variable`**

Add to `FlowMutationTools` in `mutation.py`:

```python
    async def create_secret_variable(self, name: str, value: str) -> dict[str, Any]:
        """Create a user-scoped secret variable in the variable store.

        Use before set_field_value when the target field is a SecretStrInput
        (password, api_key, token). After creating the variable, call
        set_field_value with the variable NAME — the runtime will look it up
        and substitute the secret value.

        Returns {variable_name: <name>} on success or {error: ...} on failure.
        """
        if self.user_id is None:
            return {"error": "cannot create secret variable: missing user context"}
        try:
            service = get_variable_service()
            await service.create_variable(user_id=self.user_id, name=name, value=value)
            return {"variable_name": name}
        except Exception as e:  # noqa: BLE001
            return {"error": f"failed to create secret variable: {e}"}
```

Adjust the `get_variable_service` import to match what Step 1 found.

- [x] **Step 7: Add the registry entry**

Append to `MUTATION_TOOLS` in `registry.py`:

```python
    {
        "name": "create_secret_variable",
        "description": (
            "Create a user-scoped secret variable in the variable store and "
            "return its name. Use BEFORE set_field_value when the target "
            "field is a secret/password (e.g. SFTP password, an API token). "
            "After this call, pass the returned variable_name to "
            "set_field_value — the runtime substitutes the real value at "
            "execution time. Choose a descriptive name like "
            "'sftp_password_<flow_short>' so the user can recognize it later."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The variable name (will appear in the variable store)."},
                "value": {"type": "string", "description": "The secret value (will be encrypted at rest)."},
            },
            "required": ["name", "value"],
        },
    },
```

- [x] **Step 8: Run tests to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py -v
```

Expected: PASS.

- [x] **Step 9: Run the broader assistant + mutation suites**

```bash
pytest src/backend/tests/unit/services/assistant/ \
       src/backend/tests/unit/test_assistant_mutation.py \
       src/backend/tests/unit/test_assistant_service.py -v
```

Expected: ALL PASS.

- [x] **Step 10: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/mutation.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/tools/test_create_secret_variable.py
```

---

## Task 7: System prompt — three new blocks

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/service.py:41-98` (`SYSTEM_PROMPT_TEMPLATE`)
- Create: `src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py`
- Create: `src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py`
- Create: `src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py`

The existing prompt has a `## Guidelines` section (line 50) of bullet points. Add three new sub-sections after the existing bullets but inside the same triple-quoted string. Each block gets its own test file. Three TDD cycles, one per block.

### 7.A — Pacing rules

- [x] **Step A1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py`:

```python
from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_pacing_guidelines_present():
    assert "## Conversation pacing" in SYSTEM_PROMPT_TEMPLATE


def test_pacing_rule_dont_re_ask_when_user_provided_info():
    assert "do not re-ask" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_one_question_at_a_time():
    assert "one question at a time" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_friendly_language():
    assert "friendly, non-technical language" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_confirm_scope_before_questions():
    assert "confirm scope" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_propose_defaults():
    assert "propose sensible defaults" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_surface_actionables_after_build():
    assert "surface anything the user must act on" in SYSTEM_PROMPT_TEMPLATE.lower()
```

- [x] **Step A2: Run to verify failure**

```bash
pytest src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py -v
```

Expected: 7 FAIL.

- [x] **Step A3: Add the pacing block**

In `service.py`, after the existing `[TEST_FAILURE]` bullet (line 87–97) and before the closing `"""` at line 98, add:

```
## Conversation pacing
- When the user gives information upfront, do not re-ask for it. Acknowledge \
what was provided, state your plan in one sentence, and proceed.
- When information is missing, ask one question at a time. Wait for the \
answer before asking the next.
- Use friendly, non-technical language. Ask "what should we name the files?" \
not "set the SFTP filename pattern".
- Confirm scope in one sentence before the first question. Example: "Got it \
— I'll set up an ADP webhook on hire and termination events that uploads \
worker data to an SFTP server. Let me ask a few questions:".
- Propose sensible defaults; only ask when the choice matters. Don't ask \
about SFTP port if 22 is fine — use it and mention it.
- After building, narrate what you did and surface anything the user must \
act on (for example, the webhook URL and API key the upstream system needs).
```

- [x] **Step A4: Run to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py -v
```

Expected: 7 PASS.

### 7.B — ADP integration playbook (with corrected mechanics)

- [x] **Step B1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py`:

```python
from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_adp_playbook_section_present():
    assert "## ADP integration playbook" in SYSTEM_PROMPT_TEMPLATE


def test_canonical_wiring_documented():
    assert "ADP Trigger" in SYSTEM_PROMPT_TEMPLATE
    assert "Agent" in SYSTEM_PROMPT_TEMPLATE
    assert "Sink" in SYSTEM_PROMPT_TEMPLATE


def test_event_groupings_named():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "new hire" in text
    assert "retirement" in text
    assert "deceased" in text


def test_bridge_agent_uses_fast_cheap_model():
    assert "haiku" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_adp_worker_tools_attached():
    assert "ADP Worker Tools" in SYSTEM_PROMPT_TEMPLATE


def test_friendly_field_hints_present():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "person.legalname.formattedname" in text
    assert "person.legaladdress" in text
    assert "person.communication.emails" in text


def test_output_schema_table_row_shape_documented():
    # The Agent's structured output is output_schema (TableInput),
    # not a JSON schema. The playbook must teach the row shape.
    assert "output_schema" in SYSTEM_PROMPT_TEMPLATE
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "name" in text and "description" in text and "type" in text and "multiple" in text


def test_tool_attach_handles_documented():
    # source output handle = "component_as_tool", target field = "tools"
    assert "component_as_tool" in SYSTEM_PROMPT_TEMPLATE
    assert "tools" in SYSTEM_PROMPT_TEMPLATE


def test_post_wiring_credentials_surfacing():
    # Use get_webhook_credentials, NOT get_node_field_value, for api_key
    assert "get_webhook_credentials" in SYSTEM_PROMPT_TEMPLATE
    assert "x-api-key" in SYSTEM_PROMPT_TEMPLATE


def test_secret_field_routing_via_create_secret_variable():
    assert "create_secret_variable" in SYSTEM_PROMPT_TEMPLATE
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "password" in text
```

- [x] **Step B2: Run to verify failure**

```bash
pytest src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py -v
```

Expected: 10 FAIL.

- [x] **Step B3: Add the ADP playbook block to `SYSTEM_PROMPT_TEMPLATE`**

Append to the prompt template, after the pacing block:

```
## ADP integration playbook
Use this playbook when the user wants to react to ADP events (hire, \
termination, leave, etc.) by sending data to an external system.

- Template override: if a template's `agent_instructions` are present in \
this conversation's context, those instructions take precedence over this \
playbook. Use them as your starting point; fall back to the playbook only \
for anything the template does not specify.

- Canonical wiring: `ADP Trigger → Agent (bridge) → Sink component`.

- Event groupings to recognize:
  - "hire" / "onboarding" / "new employee" → New Hire (optionally also \
Rehire — confirm with the user).
  - "termination" / "leaving" / "offboarding" → Retirement + Deceased \
(confirm with the user before applying).
  - "leave" / "out of office" → Leave.

- Bridge Agent configuration:
  - Default to a fast, cheap model (Haiku class).
  - Attach ADP Worker Tools so the agent can fetch additional worker data \
if the trigger payload is sparse. Tool-attach via `connect_edge` with \
`source_output: "component_as_tool"` on the tools component and \
`target_input: "tools"` on the agent.
  - System prompt template: "You receive an ADP worker event. Extract the \
following fields from the payload and return a single JSON object: \
<user's field list>. If a field is missing from the payload, use the \
tools to fetch it."
  - Set `output_schema` (the Agent's TableInput) to one row per requested \
field. Each row is a dict: `{"name": "<field>", "description": "<short>", \
"type": "str", "multiple": false}`. Example for the SFTP scenario:
    ```
    [
      {"name": "name",    "description": "Employee full name",          "type": "str", "multiple": false},
      {"name": "address", "description": "Employee legal address",      "type": "str", "multiple": false},
      {"name": "phone",   "description": "Employee mobile or landline", "type": "str", "multiple": false},
      {"name": "email",   "description": "Employee primary email",      "type": "str", "multiple": false},
      {"name": "job",     "description": "Employee job title",          "type": "str", "multiple": false}
    ]
    ```

- Friendly field-name → ADP payload hints to put inside the agent's prompt:
  - name → person.legalName.formattedName
  - address → person.legalAddress
  - phone → person.communication.mobiles[0] (or landlines[0])
  - email → person.communication.emails[0].emailUri
  - job → workAssignments[0].jobTitle
  - compensation → call the get_employee_compensation tool

- Secret/password fields (e.g. SFTP `password`, API keys) — DO NOT pass the \
literal value via `set_field_value`. The runtime treats those fields as \
variable lookups. Instead:
  1. Call `create_secret_variable(name=<descriptive>, value=<secret>)`. \
Choose a name like "sftp_password_<short>" so the user can recognize it.
  2. Call `set_field_value(node_id, <field>, <variable_name>)` with the \
variable name returned in step 1.

- After all three nodes are wired AND the flow is persisted (this happens \
automatically at end of turn), call `get_webhook_credentials` (no args). \
Present the returned `endpoint` and `api_key` in chat with: "Give this URL \
to ADP under Event Notification subscriptions; include the API key as the \
`x-api-key` header." Then suggest running Test mode.

- For SFTP filename patterns, prefer `{datestamp}` (full date+time, \
collision-safe) by default. Offer `{date}` only if the user explicitly \
wants one file per day and accepts the overwrite trade-off.
```

- [x] **Step B4: Run to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py -v
```

Expected: 10 PASS.

### 7.C — Template override (separate test file because the rule lives inside the playbook block but is still worth asserting independently)

- [x] **Step C1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py`:

```python
from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_template_override_rule_present():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "template" in text and "agent_instructions" in text and "take precedence" in text


def test_template_override_falls_back_to_playbook():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "fall back to" in text or "fallback to" in text
```

- [x] **Step C2: Run to verify pass (the rule is already in 7.B)**

```bash
pytest src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py -v
```

Expected: 2 PASS (because Step B3 already includes the template override bullet).

If they fail, the wording in Step B3's "Template override" bullet doesn't match the test phrases. Adjust the bullet's wording to use "take precedence" and "fall back to" verbatim.

### 7.D — Sanity check + stage

- [x] **Step D1: Run all three new prompt tests + the existing prompt tests**

```bash
pytest src/backend/tests/unit/services/assistant/ -v -k "prompt or guideline or playbook or override"
```

Expected: ALL PASS. The existing `test_greeting_guidelines_in_prompt.py` and `test_test_failure_guideline_in_prompt.py` tests should still pass — the new content was appended, not replacing existing bullets.

- [x] **Step D2: Run the full assistant test suite**

```bash
pytest src/backend/tests/unit/services/assistant/ src/backend/tests/unit/test_assistant_service.py -v
```

Expected: ALL PASS.

- [x] **Step D3: Stage**

```bash
git add src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py \
        src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py \
        src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py
```

---

## Task 8: Manual end-to-end verification

**Files:** none modified. Output is a verification report.

This task validates that a real LLM following the system prompt actually emits the playbook-prescribed behavior — including the new `create_secret_variable`/`get_webhook_credentials` flow.

- [x] **Step 1: Boot the dev environment**

Backend running, frontend dev server up, an LLM provider configured for the assistant.

- [x] **Step 2: Run Scenario A end-to-end**

1. Open the app, click **New Project** → blank template → **Build with ADP Assist**.
2. Wait for the assistant greeting.
3. Paste the Scenario A prompt:
   > "I want to sync employee name, address, phone, email, and job to a csv file on an sftp server when any employee is hired or terminated. host: localhost username bryce password P@ssword1! and each file should be named test-{datestamp}.csv. The trigger should be a webhook, please provide me back the address and api key."
4. Confirm:
   - Assistant does NOT ask redundant questions.
   - Assistant gives a one-sentence scope confirmation, then builds.
   - Canvas shows ADP Trigger, Agent, ADP Worker Tools, SFTP CSV Upload — wired in that order; ADP Worker Tools attached to the Agent's `tools` input.
   - Agent's `output_schema` has the 5 expected rows.
   - SFTP `password` field shows a variable reference (not the literal); the variable exists in the variable store.
   - Final assistant message contains the webhook URL and the API key, with instructions to use the `x-api-key` header.

- [x] **Step 3: Run Scenario B end-to-end**

1. Open a new blank flow → Build with ADP Assist.
2. Paste the Scenario B prompt:
   > "I want to sync my ADP worker data with the following fields to an csv file on an SFTP server when any employee is hired or terminated."
3. Confirm:
   - Assistant gives a one-sentence scope confirmation, then asks Q1 (fields).
   - Reply "name, address, phone, email, and job" → Q2 (host).
   - Reply `localhost` → Q3 (username).
   - Reply `bryce` → Q4 (password).
   - Reply `P@ssword1!` → assistant acknowledges "(storing securely)" → Q5 (filename).
   - Reply "test, then a dash, then a datestamp, csv" → assistant builds the same flow as Scenario A.
   - Final message contains URL + API key.

- [x] **Step 4: Verify the SFTP filename rendering**

Inspect the SFTP CSV Upload component on the canvas. Confirm the filename field shows `test-{datestamp}.csv`. Hover the filename input — confirm the info tooltip mentions `{datestamp}`.

- [x] **Step 5: Verify the webhook actually fires end-to-end (optional smoke test)**

Use the surfaced URL + API key to send a fake ADP webhook payload via curl:

```bash
curl -X POST "<url>" \
  -H "x-api-key: <key>" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"eventNameCode":{"codeValue":"worker.hire"},"data":{"output":{"worker":{"person":{"legalName":{"formattedName":"Test User"}}}}},"effectiveDateTime":"2026-04-19T00:00:00Z"}]}'
```

Confirm the request is accepted (no 401/403) and that a CSV file appears on the SFTP target with the expected name format.

- [x] **Step 6: Report readiness**

Post a verification report:

```
## Manual e2e findings

Scenario A:
- Skipped questions: yes/no
- Built canonical 4-node shape: yes/no
- Tool-attach edge correct (component_as_tool → tools): yes/no
- Agent output_schema has 5 expected rows: yes/no
- SFTP password is a variable reference (not literal): yes/no
- Surfaced URL + API key: yes/no
- Filename pattern correct: yes/no
- Notes: [...]

Scenario B:
- Asked 5 questions in order: yes/no
- Built canonical 4-node shape: yes/no
- Surfaced URL + API key: yes/no
- Notes: [...]

Webhook smoke test (Step 5): pass/fail/skipped
Issues found: [...]
Ready to commit: yes/no
```

If issues are found, file them as follow-up tasks. Real-LLM behavior is expected to need at least one prompt-tuning iteration.

---

## Open items / call-outs

- **Commit batching.** All tasks stage only. Human batches commits at the end (matches polish-phase-1 and earlier assist plans).
- **Worktree.** Running on `platform-multi-tenant` in place. No file conflicts with the polish-phase-1 plan.
- **Template (Scenario 1) follow-on.** After this plan lands, the next step is authoring the "ADP Worker Sync to SFTP" template JSON + its `agent_instructions` content. That's a separate, smaller plan.
- **Future: tag fields as "secret" in metadata.** Will let the assistant detect secret fields automatically and use `create_secret_variable` without playbook-level enumeration. Out of scope for this plan.
- **Base-URL sourcing in Task 5.** May require a small extension if no app-settings field exists today. If it does, the implementer should escalate (DONE_WITH_CONCERNS) so we can scope a follow-on rather than guessing.
