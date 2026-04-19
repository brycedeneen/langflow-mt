# Assist Scenario Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADP Assist scenarios 2a (detailed prompt) and 2b (vague prompt) work end-to-end on a blank flow — assistant gathers (or accepts) field selection + SFTP credentials + filename pattern, builds the canonical `ADP Trigger → Agent → SFTP CSV Upload` shape, and surfaces the auto-provisioned webhook URL + API key in chat.

**Architecture:** Three small, mostly independent code changes plus an upfront verification spike. (1) System-prompt additions to the existing `SYSTEM_PROMPT_TEMPLATE` constant in `service.py` — pacing rules, an ADP integration playbook, and a template-override note. (2) A new `FlowInspectionTools.get_node_field_value` assistant tool (new file + registry entry + dispatch branch) so the assistant can read the trigger's auto-generated `endpoint` and `api_key` after wiring. (3) A `{datestamp}` filename alias on the SFTP CSV Upload component (one-line change in `_resolve_remote_path`). Integration tests script a fake LLM provider to replay each scenario end-to-end against the assistant service.

**Tech Stack:** Python 3.12, pytest. Backend assistant service in `src/backend/base/langflow/services/assistant/`. LFX components in `src/lfx/src/lfx/components/`. No frontend changes in this plan.

**Spec:** [`docs/superpowers/specs/2026-04-19-assist-scenario-readiness-design.md`](../specs/2026-04-19-assist-scenario-readiness-design.md)

**Commit discipline:** This plan follows the project's standing rule: stage per task, do NOT commit. The human batches commits at the end of each logical group.

---

## File Structure

**New files:**
- `src/backend/base/langflow/services/assistant/tools/inspection.py` — `FlowInspectionTools` class with `get_node_field_value` method. Read-only flow-state queries; sibling to `mutation.py`.
- `src/backend/tests/unit/services/assistant/tools/test_inspection.py` — unit tests for the new tool (happy path + both error cases).
- `src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py` — asserts the new pacing-rule bullets appear in `SYSTEM_PROMPT_TEMPLATE`.
- `src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py` — asserts the ADP playbook block appears in `SYSTEM_PROMPT_TEMPLATE`.
- `src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py` — asserts the template-override rule appears in `SYSTEM_PROMPT_TEMPLATE`.
- `src/lfx/tests/unit/components/sftp/test_resolve_remote_path.py` (or extends an existing test file if one exists — Task 2 confirms).

**Note on integration testing:** No scripted-LLM "integration tests" for Scenarios A/B. Without a real LLM, scripted-provider tests just assert your own scripts. The honest split is: unit tests cover the contract (prompt content + tool wiring + alias rendering), and manual e2e (Task 6) covers actual LLM behavior. Real-LLM behavior tests are a future "agent eval" effort, out of scope here.

**Modified files:**
- `src/backend/base/langflow/services/assistant/service.py` — extend `SYSTEM_PROMPT_TEMPLATE` (lines 41–98); add inspection-tool dispatch branch in `_execute_tool` (lines 200–217); construct `self.inspection_tools` in `__init__` (lines 121–139); add `is_inspection_tool` import (line 17).
- `src/backend/base/langflow/services/assistant/tools/registry.py` — add `INSPECTION_TOOLS` constant, `is_inspection_tool` predicate, include in `ALL_TOOLS`.
- `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py` — `_resolve_remote_path` (line 65) gains `{datestamp}` substitution; `info=` string at line 185 mentions the new alias.

---

## Task 1: Discovery & risk verification spike

**Files:** none modified. Output is a short findings note posted in the task report.

The spec calls out four assumptions that must be confirmed before coding. This task verifies each and reports back. If any assumption is wrong, downstream tasks adjust per the findings.

- [ ] **Step 1: Verify webhook api_key auto-provisioning timing**

The spec assumes that after the assistant calls `add_component("ADPTrigger")`, the trigger node's `api_key` field is populated immediately (because flow create/update auto-provisions it via commit `3f62cd1185`). Verify by reading:

- `src/backend/base/langflow/api/v1/flows.py` — find the create/update path; check whether api_key generation runs inline or async.
- `src/backend/base/langflow/services/assistant/tools/mutation.py` — check whether `add_component` saves the flow (which would trigger auto-provisioning) or only mutates an in-memory representation.

Report: does `api_key` get written into the node template synchronously? If not, the assistant needs an explicit save+refresh between `add_component` and `get_node_field_value` — note that as an adjustment for Task 4.

- [ ] **Step 2: Verify Agent component's structured-output input shape**

The spec requires the assistant to set a JSON schema for the Agent's structured output via `set_field_value`. Locate the Agent component:

```bash
grep -rn "class.*Agent.*Component" src/lfx/src/lfx/components/agents/ src/backend/base/langflow/components/agents/ 2>/dev/null
```

Open the component file, find the structured-output input field. Report the field name and the value shape (string-encoded JSON? Python dict? list of dicts? Pydantic model?). This determines how the assistant constructs the schema in the playbook.

- [ ] **Step 3: Verify tool-attach edge type**

Agent ↔ Tools attachments may use a different edge variant than data-flow edges. Check:

- `src/backend/base/langflow/services/assistant/tools/mutation.py` `connect_edge` implementation — does it support tool-attachment, or only data-flow?
- Find an existing flow that has an Agent + Tools wiring (e.g., one of the starter projects in `src/backend/base/langflow/initial_setup/starter_projects/*.json` like `Simple Agent.json`). Open the JSON, find the edge connecting the tools to the agent, note the edge data shape (`source_handle` / `target_handle` / any `dataType` keys).

Report the edge shape. If `connect_edge` doesn't support tool-attachment, Task 4's assistant playbook either needs a workaround or this plan needs an extra step to extend `connect_edge`.

- [ ] **Step 4: Verify SecretStr routing via set_field_value**

The SFTP component's `password` is `SecretStrInput`. When the assistant calls `set_field_value(node_id, "password", "P@ssword1!")`, the framework should route through the secret store rather than persisting plain. Verify by:

- Reading `src/backend/base/langflow/services/assistant/tools/mutation.py` `set_field_value` implementation.
- Reading the secret store factory at `src/backend/base/langflow/services/secret_store/` (or wherever the recent secret store work landed — check commit `8f9d716dc3`).

Report: is `SecretStrInput` handled differently in `set_field_value`, or does the field type get respected automatically downstream? If neither, note as a follow-on (out of scope for this plan, but should be filed).

- [ ] **Step 5: Locate the SFTP test file**

```bash
find /Users/brycedeneen/dev/langflow/src/lfx -name "test*sftp*" -o -name "*sftp*test*" 2>/dev/null
find /Users/brycedeneen/dev/langflow -path "*tests*" -name "*sftp*" -not -path "*/node_modules/*" 2>/dev/null
```

If a file exists, Task 2 extends it. If not, Task 2 creates `src/lfx/tests/unit/components/sftp/test_resolve_remote_path.py`.

- [ ] **Step 6: Report findings**

Post a concise findings report. Pause for human review before continuing to Task 2. Format:

```
## Spike findings

1. api_key timing: [populated immediately | needs save+refresh | unclear]
2. Agent structured-output field: name=`...`, shape=`...`
3. Tool-attach edge shape: source_handle=`...`, target_handle=`...`, special keys=`...`. connect_edge supports: yes/no.
4. SecretStr routing: [auto | needs explicit handling | unclear]
5. SFTP test file: [path] (extend) | none (create new at <path>)

Recommended adjustments to plan: [...]
```

---

## Task 2: SFTP `{datestamp}` filename alias

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py:65-73` (function `_resolve_remote_path`) and line 185 (`info=` string).
- Test: path determined by Task 1 Step 5.

Smallest, isolated change. Single-line addition + info-string update + one test.

- [ ] **Step 1: Read the current function**

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

- [ ] **Step 2: Write the failing test**

Create or extend the file from Task 1 Step 5:

```python
import time as _time

from lfx.components.sftp.sftp_csv_upload import _resolve_remote_path


def test_datestamp_alias_renders_full_timestamp():
    fixed = _time.strptime("2026-04-19 14:30:52", "%Y-%m-%d %H:%M:%S")
    result = _resolve_remote_path("/uploads", "test-{datestamp}.csv", now=fixed)
    assert result == "/uploads/test-20260419_143052.csv"
```

- [ ] **Step 3: Run test to verify it fails**

Run from the repo-level venv with the lfx escape hatch (per `MEMORY.md`):

```bash
LFX_TEST_ALLOW_LANGFLOW=1 pytest <path-from-task-1-step-5>::test_datestamp_alias_renders_full_timestamp -v
```

Expected: FAIL with `AssertionError` showing the literal `{datestamp}` left unreplaced.

- [ ] **Step 4: Add the alias replacement**

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

`{datestamp}` is a friendly alias for `{timestamp}` (full date+time) — distinct from `{date}` (date only). Order doesn't matter functionally because the placeholder strings don't overlap, but putting the alias first is clearer.

- [ ] **Step 5: Update the `info=` text on the filename input**

Edit line 185 of `sftp_csv_upload.py`:

```python
            info="Supports {timestamp} (UTC YYYYMMDD_HHMMSS), {datestamp} (alias for {timestamp}), and {date} (UTC YYYYMMDD).",
```

- [ ] **Step 6: Run test to verify it passes**

Run the same command from Step 3. Expected: PASS.

Also run any existing tests that touch `_resolve_remote_path`:

```bash
LFX_TEST_ALLOW_LANGFLOW=1 pytest <sftp-test-file> -v
```

Expected: ALL PASS.

- [ ] **Step 7: Stage**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py <sftp-test-file>
```

Do NOT commit. Human batches.

---

## Task 3: Create `FlowInspectionTools` class with `get_node_field_value`

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/inspection.py`
- Create: `src/backend/tests/unit/services/assistant/tools/test_inspection.py`

The `mutation.py` module is the closest analog. Mirror its construction shape (a class taking `flow_data` in `__init__`) so `service.py` can construct `FlowInspectionTools(flow_data)` alongside `FlowMutationTools(flow_data)`.

- [ ] **Step 1: Read `mutation.py` to mirror its shape**

Open `src/backend/base/langflow/services/assistant/tools/mutation.py`. Confirm the class structure (constructor signature, how it accesses `flow_data["nodes"]`, return-shape conventions for tool methods). Use this as the template for `FlowInspectionTools`.

- [ ] **Step 2: Write the failing tests**

Create `src/backend/tests/unit/services/assistant/tools/test_inspection.py`:

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
    flow = _flow_with_node("trigger-1", {"api_key": "lf_abc123"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "api_key") == "lf_abc123"


def test_get_node_field_value_returns_empty_string_when_value_empty():
    flow = _flow_with_node("trigger-1", {"endpoint": ""})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "endpoint") == ""


def test_get_node_field_value_returns_node_not_found_error():
    flow = _flow_with_node("trigger-1", {"api_key": "lf_abc123"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("missing-id", "api_key") == "node not found: missing-id"


def test_get_node_field_value_returns_field_not_found_error():
    flow = _flow_with_node("trigger-1", {"api_key": "lf_abc123"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "missing_field") == "field not found on node: missing_field"


def test_get_node_field_value_coerces_non_string_values_to_string():
    flow = _flow_with_node("trigger-1", {"port": 22})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "port") == "22"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/brycedeneen/dev/langflow
pytest src/backend/tests/unit/services/assistant/tools/test_inspection.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'langflow.services.assistant.tools.inspection'`.

- [ ] **Step 4: Implement `FlowInspectionTools`**

Create `src/backend/base/langflow/services/assistant/tools/inspection.py`:

```python
from __future__ import annotations

from typing import Any


class FlowInspectionTools:
    """Read-only inspection of the active flow's node state.

    Sibling to FlowMutationTools. Used by the assistant to surface
    auto-generated values (e.g. webhook endpoint + api_key) back to
    the user after wiring.
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

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest src/backend/tests/unit/services/assistant/tools/test_inspection.py -v
```

Expected: 5 PASS.

- [ ] **Step 6: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/inspection.py \
        src/backend/tests/unit/services/assistant/tools/test_inspection.py
```

---

## Task 4: Register inspection tool + wire dispatch

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py`
- Modify: `src/backend/base/langflow/services/assistant/service.py:17` (import) and lines 121–139 (constructor) and lines 200–217 (`_execute_tool` dispatch).

- [ ] **Step 1: Add `INSPECTION_TOOLS` to registry**

Edit `src/backend/base/langflow/services/assistant/tools/registry.py`. Add a new constant block immediately after `MUTATION_TOOLS` (before `ALL_TOOLS`):

```python
INSPECTION_TOOLS = [
    {
        "name": "get_node_field_value",
        "description": (
            "Read the current value of one field on one node in the active flow. "
            "Use after add_component to surface auto-generated values like a "
            "webhook trigger's endpoint or api_key back to the user. Returns the "
            "value as a string, or an error string starting with 'node not found:' "
            "or 'field not found on node:' on lookup failure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "The node's id from the canvas summary."},
                "field_name": {
                    "type": "string",
                    "description": (
                        "Template field name (backtick-style, e.g. 'api_key', 'endpoint'). "
                        "Not the display name."
                    ),
                },
            },
            "required": ["node_id", "field_name"],
        },
    },
]
```

Update `ALL_TOOLS`:

```python
ALL_TOOLS = CATALOG_TOOLS + MUTATION_TOOLS + INSPECTION_TOOLS
```

Add the predicate (mirroring `is_mutation_tool`):

```python
def is_inspection_tool(name: str) -> bool:
    return any(t["name"] == name for t in INSPECTION_TOOLS)
```

- [ ] **Step 2: Wire dispatch in `service.py`**

Open `src/backend/base/langflow/services/assistant/service.py`.

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

**(b)** Add a `FlowInspectionTools` import near the other tool imports at the top of the file (look for the existing `FlowMutationTools` import and add a sibling line):

```python
from langflow.services.assistant.tools.inspection import FlowInspectionTools
```

**(c)** In `__init__` (lines 121–139), add construction of inspection tools next to mutation tools:

```python
        self.mutation_tools = FlowMutationTools(flow_data)
        self.inspection_tools = FlowInspectionTools(flow_data)
```

**(d)** In `_execute_tool` (lines 200–217), add a third branch between the mutation branch and the unknown-tool fallback:

```python
            elif is_mutation_tool(name):
                method = getattr(self.mutation_tools, name)
                import asyncio
                result = method(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                return {"result": result}
            elif is_inspection_tool(name):
                method = getattr(self.inspection_tools, name)
                result = method(**args)
                return {"result": result}
            else:
                return {"error": f"Unknown tool: {name}"}
```

- [ ] **Step 3: Write a service-level integration test**

Create `src/backend/tests/unit/services/assistant/test_inspection_dispatch.py`:

```python
import pytest

from langflow.services.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_get_node_field_value_dispatches_to_inspection_tools():
    flow_data = {
        "nodes": [
            {
                "id": "trigger-1",
                "data": {"node": {"template": {"api_key": {"value": "lf_xyz"}}}},
            }
        ],
        "edges": [],
    }
    service = AssistantService.__new__(AssistantService)  # bypass full init
    service.flow_data = flow_data
    from langflow.services.assistant.tools.inspection import FlowInspectionTools
    from langflow.services.assistant.tools.mutation import FlowMutationTools

    service.mutation_tools = FlowMutationTools(flow_data)
    service.inspection_tools = FlowInspectionTools(flow_data)

    result = await service._execute_tool(
        "get_node_field_value", {"node_id": "trigger-1", "field_name": "api_key"}
    )
    assert result == {"result": "lf_xyz"}
```

If `AssistantService.__init__` requires more state to be runnable, switch to constructing it with mock collaborators per the pattern in `src/backend/tests/unit/test_assistant_service.py`. Inspect that file first to align.

- [ ] **Step 4: Run the dispatch test**

```bash
pytest src/backend/tests/unit/services/assistant/test_inspection_dispatch.py -v
```

Expected: PASS.

- [ ] **Step 5: Re-run the inspection unit tests + the broader assistant test suite**

```bash
pytest src/backend/tests/unit/services/assistant/ -v
pytest src/backend/tests/unit/test_assistant_service.py -v
pytest src/backend/tests/unit/test_assistant_mutation.py -v
pytest src/backend/tests/unit/test_assistant_catalog.py -v
```

Expected: ALL PASS. The new inspection branch shouldn't affect the existing catalog or mutation paths.

- [ ] **Step 6: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/test_inspection_dispatch.py
```

---

## Task 5: System prompt — three new blocks

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/service.py:41-98` (`SYSTEM_PROMPT_TEMPLATE`)
- Create: `src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py`
- Create: `src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py`
- Create: `src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py`

The existing prompt has a `## Guidelines` section (line 50) of bullet points. Add three new sub-sections after the existing bullets but inside the same triple-quoted string. Each block gets its own test file (one fact per file makes failures readable).

Three TDD cycles, one per block.

### 5.A — Pacing rules

- [ ] **Step A1: Write the failing test**

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

- [ ] **Step A2: Run to verify failure**

```bash
pytest src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py -v
```

Expected: 7 FAIL.

- [ ] **Step A3: Add the pacing block to `SYSTEM_PROMPT_TEMPLATE`**

In `src/backend/base/langflow/services/assistant/service.py`, after the existing `[TEST_FAILURE]` bullet (line 87–97), and before the closing `"""` at line 98, add:

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

- [ ] **Step A4: Run to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py -v
```

Expected: 7 PASS.

### 5.B — ADP integration playbook

- [ ] **Step B1: Write the failing test**

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
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "haiku" in text


def test_adp_worker_tools_attached():
    assert "ADP Worker Tools" in SYSTEM_PROMPT_TEMPLATE


def test_friendly_field_hints_present():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "person.legalname.formattedname" in text
    assert "person.legaladdress" in text
    assert "person.communication.emails" in text


def test_post_wiring_credentials_surfacing():
    text = SYSTEM_PROMPT_TEMPLATE
    assert "get_node_field_value" in text
    assert "endpoint" in text
    assert "api_key" in text
    assert "x-api-key" in text
```

- [ ] **Step B2: Run to verify failure**

```bash
pytest src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py -v
```

Expected: 7 FAIL.

- [ ] **Step B3: Add the ADP playbook block to `SYSTEM_PROMPT_TEMPLATE`**

Append to the prompt template, after the pacing block:

```
## ADP integration playbook
Use this playbook when the user wants to react to ADP events (hire, \
termination, leave, etc.) by sending data to an external system.

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
if the trigger payload is sparse.
  - System prompt template: "You receive an ADP worker event. Extract the \
following fields from the payload and return a single JSON object: \
<user's field list>. If a field is missing from the payload, use the \
tools to fetch it."
  - Set structured output: a JSON schema with one string property per \
requested field.
- Friendly field-name → ADP payload hints to put inside the agent's prompt:
  - name → person.legalName.formattedName
  - address → person.legalAddress
  - phone → person.communication.mobiles[0] (or landlines[0])
  - email → person.communication.emails[0].emailUri
  - job → workAssignments[0].jobTitle
  - compensation → call the get_employee_compensation tool
- After wiring all three nodes, call \
`get_node_field_value(<trigger node id>, "endpoint")` and \
`get_node_field_value(<trigger node id>, "api_key")`. Present both in chat \
with: "Give this URL to ADP under Event Notification subscriptions; include \
the API key as the `x-api-key` header." Then suggest running Test mode.
- For SFTP filename patterns, prefer `{datestamp}` (full date+time, \
collision-safe) by default. Offer `{date}` only if the user explicitly \
wants one file per day and accepts the overwrite trade-off.
```

- [ ] **Step B4: Run to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py -v
```

Expected: 7 PASS.

### 5.C — Template override rule

- [ ] **Step C1: Write the failing test**

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

- [ ] **Step C2: Run to verify failure**

```bash
pytest src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py -v
```

Expected: 2 FAIL.

- [ ] **Step C3: Add the template override note**

Insert at the TOP of the ADP playbook section (immediately after the `## ADP integration playbook` heading, before the rest of the playbook content):

```
- Template override: if a template's `agent_instructions` are present in \
this conversation's context, those instructions take precedence over this \
playbook. Use them as your starting point; fall back to the playbook only \
for anything the template does not specify.
```

- [ ] **Step C4: Run to verify pass**

```bash
pytest src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py -v
```

Expected: 2 PASS.

### 5.D — Sanity check + stage

- [ ] **Step D1: Run all three new prompt tests + the existing prompt tests together**

```bash
pytest src/backend/tests/unit/services/assistant/ -v -k "prompt or guideline or playbook or override"
```

Expected: ALL PASS (the existing `test_greeting_guidelines_in_prompt.py` and `test_test_failure_guideline_in_prompt.py` tests should still pass — the new content was appended, not replacing existing bullets).

- [ ] **Step D2: Run the full assistant test suite**

```bash
pytest src/backend/tests/unit/services/assistant/ src/backend/tests/unit/test_assistant_service.py -v
```

Expected: ALL PASS.

- [ ] **Step D3: Stage**

```bash
git add src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/test_pacing_guidelines_in_prompt.py \
        src/backend/tests/unit/services/assistant/test_adp_playbook_in_prompt.py \
        src/backend/tests/unit/services/assistant/test_template_override_in_prompt.py
```

---

## Task 6: Manual end-to-end verification

**Files:** none modified. Output is a verification report.

This task validates that a real LLM following the system prompt actually emits the playbook-prescribed behavior. The integration tests in Tasks 6–7 assert the contract; this confirms reality matches.

- [ ] **Step 1: Boot the dev environment**

Backend running, frontend dev server up, an LLM provider configured for the assistant.

- [ ] **Step 2: Run Scenario A end-to-end**

1. Open the app, click **New Project** → blank template → **Build with ADP Assist**.
2. Wait for the assistant greeting.
3. Paste the Scenario A prompt:
   > "I want to sync employee name, address, phone, email, and job to a csv file on an sftp server when any employee is hired or terminated. host: localhost username bryce password P@ssword1! and each file should be named test-{datestamp}.csv. The trigger should be a webhook, please provide me back the address and api key."
4. Confirm:
   - Assistant does NOT ask redundant questions (it has all info).
   - Assistant gives a one-sentence scope confirmation, then builds.
   - Canvas shows ADP Trigger, Agent, ADP Worker Tools, SFTP CSV Upload — wired in that order.
   - Final assistant message contains the webhook URL and the API key, with instructions to use the `x-api-key` header.

- [ ] **Step 3: Run Scenario B end-to-end**

1. Open a new blank flow → Build with ADP Assist.
2. Paste the Scenario B prompt:
   > "I want to sync my ADP worker data with the following fields to an csv file on an SFTP server when any employee is hired or terminated."
3. Confirm:
   - Assistant gives a one-sentence scope confirmation, then asks Q1 (fields).
   - Reply: "name, address, phone, email, and job."
   - Assistant asks Q2 (host). Reply: `localhost`.
   - Assistant asks Q3 (username). Reply: `bryce`.
   - Assistant asks Q4 (password). Reply: `P@ssword1!`. Acknowledge "(storing securely)".
   - Assistant asks Q5 (filename). Reply: "test, then a dash, then a datestamp, csv".
   - Assistant builds the same flow as Scenario A.
   - Final message contains URL + API key.

- [ ] **Step 4: Verify the SFTP filename rendering**

Inspect the SFTP CSV Upload component on the canvas. Confirm the filename field shows `test-{datestamp}.csv`. Hover the filename input — confirm the info tooltip mentions `{datestamp}`.

- [ ] **Step 5: Report readiness**

Post a verification report:

```
## Manual e2e findings

Scenario A:
- Skipped questions: yes/no
- Built canonical 4-node shape: yes/no
- Surfaced URL + API key: yes/no
- Filename pattern correct: yes/no
- Notes: [...]

Scenario B:
- Asked 5 questions in order: yes/no
- Built canonical 4-node shape: yes/no
- Surfaced URL + API key: yes/no
- Notes: [...]

Issues found: [...]
Ready to commit: yes/no
```

If issues are found, file them as follow-up tasks. The plan doesn't mandate that real-LLM behavior matches perfectly on the first pass — prompt tuning is a known iteration loop.

---

## Open items / call-outs

- **Commit batching.** All tasks stage only. Human batches commits at the end (matches polish-phase-1 and earlier assist plans).
- **Worktree.** This plan is self-contained and TDD'd; running it in a worktree is optional but recommended for isolation. No file conflicts with the polish-phase-1 plan.
- **Template (Scenario 1) follow-on.** After this plan lands, the next step is authoring the "ADP Worker Sync to SFTP" template JSON + its `agent_instructions` content. That's a separate, smaller plan.
- **If Task 1 spike reveals a save+refresh requirement** for api_key visibility: insert an explicit task between Task 4 and Task 5 (or extend `add_component`/`set_field_value` semantics) per the spike's recommendation.
- **If Task 1 spike reveals `connect_edge` doesn't support tool-attach edges:** scope a small extension to `connect_edge` (and update the playbook in Task 5.B to match the new signature) before integration testing.
