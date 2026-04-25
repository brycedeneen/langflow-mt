# ADP → SFTP Template + Sibling-Metadata Seeder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the **ADP Worker Sync to SFTP** starter-project template plus a generic sibling-metadata-file seeder convention so any future code-shipped template can carry its `agent_summary` + `agent_usage_notes` content alongside its flow JSON.

**Architecture:** Two co-located files in `initial_setup/starter_projects/` per template — the existing `<Name>.json` flow plus a new `<Name>.metadata.json` sidecar with the assistant content. A new `create_or_update_template_metadata` function in `initial_setup/setup.py` walks the directory after starter-project seeding completes, parses each `*.metadata.json`, and upserts a `TemplateMetadata` row pointing at the matching seeded flow. Idempotent: re-runs are no-ops once metadata is in place; if `updated_by IS NULL` (seed-only state), re-running overwrites with file content; if `updated_by IS NOT NULL` (admin has taken ownership via the existing admin API), the seeder skips. Two small platform prep changes are required before any of this works: making `TemplateMetadata.updated_by` nullable, and filtering `*.metadata.json` files out of the existing starter-project glob so the existing seeder doesn't try to load them as flows.

**Tech Stack:** Python 3.12, pytest, SQLModel, Alembic. Backend only — no frontend changes (existing template picker + Build with ADP Assist path covers it).

**Spec:** [`docs/superpowers/specs/2026-04-19-adp-sftp-template-design.md`](../specs/2026-04-19-adp-sftp-template-design.md)

**Commit discipline:** This plan follows the project's standing rule: stage per task, do NOT commit. The human batches commits at the end of each logical group.

---

## File Structure

**New files:**

- `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.json` — the flow (4 nodes + 3 edges, defaults filled).
- `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.metadata.json` — the `agent_summary` + `agent_usage_notes` sibling.
- `src/backend/base/langflow/alembic/versions/<auto>_make_template_metadata_updated_by_nullable.py` — small alembic revision.
- `src/backend/tests/unit/initial_setup/__init__.py` (if the directory doesn't already exist).
- `src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py` — covers the new seeder.
- `src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py` — asserts the flow JSON's structural correctness.

**Modified files:**

- `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py` — make `updated_by` `UUID | None` (nullable).
- `src/backend/base/langflow/services/database/models/template_metadata/model.py` — update `TemplateMetadataRead.updated_by` to `UUID | None` to match.
- `src/backend/base/langflow/initial_setup/setup.py` — filter `*.metadata.json` in `load_starter_projects` (~line 560); add new `create_or_update_template_metadata` function near the existing `create_or_update_starter_projects` (~line 1105).
- `src/backend/base/langflow/main.py:220` — call the new seeder in the lifespan startup hook, after `create_or_update_starter_projects`.

---

## Task 1: Platform prep — nullable `updated_by` + glob filter

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py`
- Modify: `src/backend/base/langflow/services/database/models/template_metadata/model.py`
- Modify: `src/backend/base/langflow/initial_setup/setup.py:556-575` (`load_starter_projects`)
- Create: `src/backend/base/langflow/alembic/versions/<auto>_make_template_metadata_updated_by_nullable.py`

Two small platform changes that must land before the seeder can work. They're independent of each other but small enough to ship together.

- [x] **Step 1: Make `updated_by` nullable in the model**

Open `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py`. Change line 27 from:

```python
    updated_by: UUID = Field(foreign_key="user.id")
```

to:

```python
    updated_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
```

The `default=None` lets the seeder insert without an acting user. `nullable=True` makes the SQL column allow NULL.

- [x] **Step 2: Update the `TemplateMetadataRead` Pydantic schema to match**

Open `src/backend/base/langflow/services/database/models/template_metadata/model.py:25-29`. Change `updated_by: UUID` on line 28 to `updated_by: UUID | None`.

(`component_metadata/model.py` may have a similar `Read` model — grep for `updated_by: UUID` and update any non-nullable Pydantic schemas to match. Stage them with this task.)

- [x] **Step 3: Generate the alembic revision**

Run from the langflow backend dir:

```bash
cd /Users/brycedeneen/dev/langflow/src/backend/base
uv run alembic -c langflow/alembic.ini revision --autogenerate -m "make template_metadata.updated_by nullable"
```

Inspect the generated file. Expected diff: `op.alter_column('template_metadata', 'updated_by', existing_type=sa.Uuid(), nullable=True)`. Same for `component_metadata` if the mixin change cascaded.

If autogenerate produces additional unrelated changes (drift from prior schema), revert those — keep only the `nullable=True` alter. The downgrade should set `nullable=False`.

- [x] **Step 4: Apply the migration**

```bash
cd /Users/brycedeneen/dev/langflow/src/backend/base
uv run alembic -c langflow/alembic.ini upgrade head
```

Expected: clean upgrade. Verify with a quick sqlite query:

```bash
sqlite3 ~/.cache/langflow/langflow.db ".schema template_metadata" | grep updated_by
```

Expected: `updated_by` shown without `NOT NULL`.

- [x] **Step 5: Filter `.metadata.json` files out of `load_starter_projects`**

Open `src/backend/base/langflow/initial_setup/setup.py:556-575`. Find the loop:

```python
    async for file in folder.glob("*.json"):
        attempt = 0
        while attempt < retries:
            content = await file.read_text(encoding="utf-8")
            ...
```

Insert a skip immediately after the `async for` line:

```python
    async for file in folder.glob("*.json"):
        # Skip sibling metadata files (e.g. "Foo.metadata.json"); those are
        # consumed separately by create_or_update_template_metadata.
        if file.name.endswith(".metadata.json"):
            continue
        attempt = 0
        ...
```

This prevents the existing starter-project seeder from trying to parse our metadata JSON as a flow.

- [x] **Step 6: Run the existing assistant + initial-setup test surface to confirm nothing broke**

```bash
cd /Users/brycedeneen/dev/langflow
uv run pytest src/backend/tests/unit/services/assistant/ -v
```

Expected: ALL PASS (the metadata model change doesn't affect assistant tests, but a quick sanity check is cheap).

- [x] **Step 7: Stage**

```bash
git add src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py \
        src/backend/base/langflow/services/database/models/template_metadata/model.py \
        src/backend/base/langflow/alembic/versions/*make_template_metadata_updated_by_nullable.py \
        src/backend/base/langflow/initial_setup/setup.py
```

(Plus `component_metadata/model.py` if it was modified in Step 2.) Do NOT commit.

---

## Task 2: Author the ADP→SFTP flow JSON + sibling metadata JSON + shape test

**Files:**
- Create: `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.json`
- Create: `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.metadata.json`
- Create: `src/backend/tests/unit/initial_setup/__init__.py` (empty, only if missing)
- Create: `src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py`

The flow JSON's structure is complex (matches Langflow's serialization format with `data.nodes[].data.node.template` etc.) and risky to hand-write from scratch. Two paths — pick whichever lands faster:

**Authoring path A (recommended): use the existing `Simple Agent.json` as a scaffold.**

It already has Agent + tools wiring in the right shape, so most of the structure carries over. Replace the components, set the defaults from the spec, save under the new filename. Inspect with the shape test in this task.

**Authoring path B: build it in the running app, then export.**

Boot the dev environment, create a new flow, drag-and-drop the 4 components, wire them, fill defaults via the UI, then export the flow JSON. Save under `starter_projects/`. Trim any flow-instance fields (e.g., user_id, organization_id, timestamps) that don't belong in templates — compare against `Simple Agent.json` to know what to keep.

Either path, the shape test in this task is the safety net.

- [x] **Step 1: Create the flow JSON**

Place at `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.json`. Required structural properties (asserted by the shape test in Step 4):

- Top-level `name`: `"ADP Worker Sync to SFTP"`
- Top-level `description`: `"Sync ADP worker data to a CSV on an SFTP server when employees are hired or terminated. The assistant guides you through the SFTP details."`
- Top-level `data.nodes`: list of exactly 4 nodes
- Top-level `data.edges`: list of exactly 3 edges

**Required nodes** (each identified by `data.type` and the contained `data.node.template`):

| Node id (suggested) | `data.type` | Required template defaults |
|---|---|---|
| `ADPTriggerComponent-XXXXX` | `ADPTriggerComponent` | `event_types.value: ["New Hire", "Retirement", "Deceased"]` |
| `Agent-XXXXX` | `Agent` | `agent_llm.value: "Anthropic"`, `model_name.value: <a Haiku-class id, e.g. "claude-haiku-4-5-20251001">`, `system_prompt.value: ""` (empty), `tools.value: []` (assistant tool will append) |
| `ADPWorkerToolsComponent-XXXXX` | `ADPWorkerToolsComponent` | `client_id.value: "adp_client_id"`, `client_secret.value: "adp_client_secret"`, `client_certificate.value: "adp_client_certificate"`, `client_key.value: "adp_client_key"` |
| `SFTPCSVUploadComponent-XXXXX` | `SFTPCSVUploadComponent` | `host.value: ""`, `username.value: ""`, `password.value: ""`, `filename.value: ""`, `port.value: 22`, `remote_directory.value: "/"` |

(The `XXXXX` suffix is a 5-char hex slug per Langflow's add_component convention; the exact suffix doesn't matter — the shape test asserts on `data.type`, not full id.)

**Required edges:**

1. **ADP Trigger → Agent** (data flow). Source output = Trigger's `output_data` (or whatever its primary `Data` output is named — verify against the running ADP Trigger component's outputs). Target input on Agent = primary input.
2. **ADP Worker Tools → Agent** (tool attachment). Source handle includes `name: "component_as_tool"`, `output_types: ["Tool"]`. Target handle includes `fieldName: "tools"`, `inputTypes: ["Tool"]`, `type: "other"`.
3. **Agent → SFTP CSV Upload** (data flow). Source output on Agent = its primary structured output. Target input on SFTP = its primary `data` input.

If you build this via path A (scaffold from `Simple Agent.json`), the Agent ↔ tools edge in that file IS this exact shape — just retarget the `dataType` field on the source handle from the existing tool's component type to `ADPWorkerToolsComponent`.

If structural details differ from what the running components expose (e.g., the ADP Trigger's primary Data output is named differently), prefer path B (export from the running app) — that captures the truth.

- [x] **Step 2: Create the metadata sibling JSON**

Place at `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.metadata.json` with this exact content:

```json
{
  "agent_summary": "Sync ADP worker data to a CSV on an SFTP server when employees are hired or terminated. Pre-wired with ADP Trigger, an extraction Agent, and SFTP CSV Upload — the user provides the field list, SFTP credentials, and filename pattern.",
  "agent_usage_notes": "You are guiding a user through configuring the **ADP Worker Sync to SFTP** template. The flow is pre-wired — your job is to fill in the variable bits via a short, friendly conversation.\n\n## Opening\nOpen with one short sentence framing the experience:\n\n> \"I'll guide you through a few quick questions to set up your ADP→SFTP sync. Once it's running, you can customize anything — add fields, change the destination, swap components.\"\n\n## Pre-flight — ADP credentials\nBefore any other question:\n1. Call `list_user_variables`.\n2. Confirm these four exist: `adp_client_id`, `adp_client_secret`, `adp_client_certificate`, `adp_client_key`.\n3. If all four exist → say \"I found your ADP credentials.\" and proceed.\n4. If any are missing → tell the user which in plain language (\"I need your ADP credentials. Specifically: client ID, client secret, certificate, and key.\"). Ask one at a time. For each, call `create_secret_variable(name=<canonical_name>, value=<input>)` using the names above. After all four exist: \"Saved securely — these will be reused for any future ADP integrations.\"\n\n(The ADP Worker Tools node's credential fields are already wired to these variable names, so no per-flow `set_field_value` for credentials.)\n\n## The 5 questions\nAsk in order, one at a time, in friendly language. Skip any the user already answered in their first message.\n\n1. **Fields.** \"Which worker fields should we include in the CSV?\" Suggest defaults inline: \"(common ones: name, address, phone, email, job)\". Accept the user's list verbatim.\n2. **SFTP host.** \"What's the address, URL, or IP of your SFTP server?\"\n3. **SFTP username.** \"What username should we use to connect?\"\n4. **SFTP password.** \"What's the password? (I'll store it securely as a variable.)\"\n5. **Filename pattern.** \"What should each uploaded file be named?\" If the user says \"datestamp,\" use the `{datestamp}` placeholder (full date+time, collision-safe). Confirm with an example: \"Files will be named like `test-20260419_143052.csv` — one per event.\"\n\n## Wiring the answers\nAfter all 5 are collected:\n\n1. **Agent `output_schema`** — append one TableInput row per requested field: `{\"name\": \"<field>\", \"description\": \"<one-line>\", \"type\": \"str\", \"multiple\": false}`. Use the friendly-name → ADP payload hints from your playbook. Set via `set_field_value` on the Agent node.\n2. **Agent `system_prompt`** — set to:\n   > \"You receive an ADP worker event. Extract these fields from the payload and return a single JSON object: <comma-separated fields>. If a field is missing from the payload, use the available tools to fetch it.\"\n3. **SFTP node** — `set_field_value` for `host`, `username`, `filename` directly.\n4. **SFTP password** — two-step pattern from your playbook:\n   a. `create_secret_variable(name=\"sftp_password_<short_token>\", value=<password>)` — pick a short descriptive token so the variable is recognizable in the variable store.\n   b. `set_field_value(<sftp_node_id>, \"password\", \"<variable_name>\")`.\n\n## Final delivery\nAfter wiring, the flow auto-persists at end of turn. Then:\n\n1. Call `get_webhook_credentials`.\n2. Present in chat:\n   > \"Your sync is ready. Here's what to give to ADP:\n   > - **Webhook URL:** `<endpoint>`\n   > - **API Key:** `<api_key>`\n   >\n   > In ADP, create an Event Notification subscription pointing at this URL with header `x-api-key: <api_key>`.\"\n3. Suggest: \"Want to test it? Click **Test** in the header to send a sample payload through and verify each component.\"\n4. Remind the user they own the flow now: \"You can click into any component on the canvas to add fields, change credentials, or swap parts.\"\n\n## Variations\n- **Extra field beyond the standard 5** — add to `output_schema` + extend the system prompt's field list. Use `get_employee_compensation` for compensation; for rare fields, instruct the agent to pull from the payload directly.\n- **User wants Rehire too** — `set_field_value` to add `Rehire` to the trigger's `event_types`.\n- **User asks for a different sink (Slack, email, DB)** — this template isn't the right starting point. Suggest \"Let's use a blank flow with the assistant\" and exit the template script."
}
```

(The `agent_usage_notes` string is one big JSON-encoded string with `\n` line breaks. The content matches Section D of the spec verbatim.)

- [x] **Step 3: Create the test directory if missing**

Check whether `src/backend/tests/unit/initial_setup/` exists:

```bash
ls /Users/brycedeneen/dev/langflow/src/backend/tests/unit/initial_setup/ 2>/dev/null
```

If not, create it with an empty `__init__.py`:

```bash
mkdir -p /Users/brycedeneen/dev/langflow/src/backend/tests/unit/initial_setup
touch /Users/brycedeneen/dev/langflow/src/backend/tests/unit/initial_setup/__init__.py
```

- [x] **Step 4: Write the shape test**

Create `src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py`:

```python
"""Structural tests for the ADP Worker Sync to SFTP starter template.

The shape (4 specific components, 3 edges including a tool-attach edge with
the verified handle keys) is load-bearing for the ADP Assist UX. A hand-edit
that drifts from this shape would silently break the template.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "base"
    / "langflow"
    / "initial_setup"
    / "starter_projects"
    / "ADP Worker Sync to SFTP.json"
)


@pytest.fixture(scope="module")
def template() -> dict:
    with TEMPLATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_template_top_level_metadata(template):
    assert template["name"] == "ADP Worker Sync to SFTP"
    assert "ADP" in template["description"] and "SFTP" in template["description"]


def test_template_has_four_nodes_with_expected_types(template):
    nodes = template["data"]["nodes"]
    assert len(nodes) == 4
    types = sorted(n["data"]["type"] for n in nodes)
    assert types == sorted(
        ["ADPTriggerComponent", "Agent", "ADPWorkerToolsComponent", "SFTPCSVUploadComponent"]
    )


def test_template_has_three_edges(template):
    edges = template["data"]["edges"]
    assert len(edges) == 3


def _node_by_type(template, type_name):
    return next(n for n in template["data"]["nodes"] if n["data"]["type"] == type_name)


def test_adp_trigger_event_types_default(template):
    trigger = _node_by_type(template, "ADPTriggerComponent")
    event_types = trigger["data"]["node"]["template"]["event_types"]["value"]
    assert "New Hire" in event_types
    assert "Retirement" in event_types
    assert "Deceased" in event_types


def test_agent_defaults_filled(template):
    agent = _node_by_type(template, "Agent")
    template_dict = agent["data"]["node"]["template"]
    # Provider defaults to Anthropic; exact model id is implementation choice but must be Haiku-class
    assert template_dict["agent_llm"]["value"] == "Anthropic"
    assert "haiku" in template_dict["model_name"]["value"].lower()
    # System prompt is empty in the template; assistant fills it at build time
    assert template_dict["system_prompt"]["value"] == ""


def test_adp_worker_tools_credential_fields_reference_canonical_variable_names(template):
    tools_node = _node_by_type(template, "ADPWorkerToolsComponent")
    template_dict = tools_node["data"]["node"]["template"]
    assert template_dict["client_id"]["value"] == "adp_client_id"
    assert template_dict["client_secret"]["value"] == "adp_client_secret"
    assert template_dict["client_certificate"]["value"] == "adp_client_certificate"
    assert template_dict["client_key"]["value"] == "adp_client_key"


def test_sftp_node_per_flow_fields_empty(template):
    sftp = _node_by_type(template, "SFTPCSVUploadComponent")
    template_dict = sftp["data"]["node"]["template"]
    assert template_dict["host"]["value"] == ""
    assert template_dict["username"]["value"] == ""
    assert template_dict["password"]["value"] == ""
    assert template_dict["filename"]["value"] == ""
    assert template_dict["port"]["value"] == 22


def test_tool_attach_edge_uses_verified_handle_shape(template):
    """The Agent ↔ ADP Worker Tools edge must use component_as_tool / tools handles.
    A hand-edit that drifts from this would silently break tool attachment.
    """
    edges = template["data"]["edges"]
    tool_edges = [
        e for e in edges
        if e.get("data", {}).get("sourceHandle", {}).get("name") == "component_as_tool"
    ]
    assert len(tool_edges) == 1, "Expected exactly one tool-attach edge"
    edge = tool_edges[0]
    src_handle = edge["data"]["sourceHandle"]
    tgt_handle = edge["data"]["targetHandle"]
    assert "Tool" in src_handle.get("output_types", [])
    assert tgt_handle.get("fieldName") == "tools"
    assert "Tool" in tgt_handle.get("inputTypes", [])


def test_metadata_sibling_file_present_and_well_formed():
    """The sibling metadata file must exist alongside the flow JSON."""
    sibling = TEMPLATE_PATH.with_name("ADP Worker Sync to SFTP.metadata.json")
    assert sibling.exists(), f"Missing sibling metadata file at {sibling}"
    with sibling.open(encoding="utf-8") as f:
        meta = json.load(f)
    assert meta.get("agent_summary"), "agent_summary must be non-empty"
    assert meta.get("agent_usage_notes"), "agent_usage_notes must be non-empty"
    notes = meta["agent_usage_notes"]
    # Spot-check the script orients the assistant at the canonical tools and pattern
    assert "list_user_variables" in notes
    assert "create_secret_variable" in notes
    assert "get_webhook_credentials" in notes
    assert "adp_client_id" in notes
```

- [x] **Step 5: Run the shape test**

```bash
cd /Users/brycedeneen/dev/langflow
uv run pytest src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py -v
```

Expected: ALL PASS. If any test fails, the JSON authoring missed a structural requirement — fix the JSON, not the test (the test encodes the spec).

If the test reveals that a particular template field name (e.g., `agent_llm` vs `model_provider`, or `model_name` vs `model_id`) doesn't match the running Agent component's actual schema, escalate (DONE_WITH_CONCERNS) — the spec used illustrative names that may need to match real component output. Don't guess; confirm against the running component or against an exported `Simple Agent.json` snapshot.

- [x] **Step 6: Stage**

```bash
git add "src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.json" \
        "src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.metadata.json" \
        src/backend/tests/unit/initial_setup/__init__.py \
        src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py
```

---

## Task 3: Implement `create_or_update_template_metadata` seeder + unit tests

**Files:**
- Modify: `src/backend/base/langflow/initial_setup/setup.py` — add new function near `create_or_update_starter_projects` (~line 1105).
- Create: `src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py`

The seeder walks `starter_projects/` for `*.metadata.json` files, looks up the matching seeded flow by name within the Starter Projects folder, and upserts a `TemplateMetadata` row per the rules in the spec.

- [x] **Step 1: Locate / verify the Flow-by-name-and-folder helper**

Search `src/backend/base/langflow/initial_setup/setup.py` and `src/backend/base/langflow/services/database/models/flow/` for an existing query that finds a `Flow` row by `name` within a specific `folder_id`:

```bash
grep -rn "Flow.name\|name.*folder_id\|select.*Flow.*name" /Users/brycedeneen/dev/langflow/src/backend/base/langflow/initial_setup/ 2>/dev/null
```

Likely candidate: `get_all_flows_similar_to_project` (used at setup.py:1174). Inspect it; if its return shape works, reuse. Otherwise the seeder builds its own SQL inline (next step).

- [x] **Step 2: Write the failing tests**

Create `src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py`:

```python
"""Tests for create_or_update_template_metadata.

Seeder behavior (per spec):
- First seed (no row exists) → INSERT with updated_by=NULL.
- Re-seed when updated_by IS NULL → UPDATE (overwrite from file).
- Re-seed when updated_by IS NOT NULL → SKIP (admin took ownership).
- Missing matching flow → log + skip, no raise.
- Malformed JSON → log + skip, doesn't break sibling templates.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.initial_setup.setup import create_or_update_template_metadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.template_metadata.model import TemplateMetadata


@pytest.fixture
async def starter_folder(db_session):
    """Create the Starter Projects folder (matches existing constants.STARTER_FOLDER_NAME)."""
    from langflow.initial_setup.constants import STARTER_FOLDER_NAME

    folder = Folder(name=STARTER_FOLDER_NAME)
    db_session.add(folder)
    await db_session.commit()
    await db_session.refresh(folder)
    return folder


async def _seed_flow(db_session, folder_id, name: str) -> Flow:
    flow = Flow(
        name=name,
        description="test",
        folder_id=folder_id,
        data={"nodes": [], "edges": []},
    )
    db_session.add(flow)
    await db_session.commit()
    await db_session.refresh(flow)
    return flow


def _write_metadata_file(tmp_dir: Path, flow_name: str, summary: str, notes: str) -> Path:
    p = tmp_dir / f"{flow_name}.metadata.json"
    p.write_text(json.dumps({"agent_summary": summary, "agent_usage_notes": notes}))
    # Also create a placeholder flow JSON so the directory matches real layout
    (tmp_dir / f"{flow_name}.json").write_text(json.dumps({"name": flow_name, "data": {"nodes": [], "edges": []}}))
    return p


@pytest.mark.asyncio
async def test_first_seed_creates_row_with_null_updated_by(db_session, starter_folder, tmp_path):
    flow = await _seed_flow(db_session, starter_folder.id, "Sample Template")
    _write_metadata_file(tmp_path, "Sample Template", "Summary one", "Notes one")

    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = (await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.agent_summary == "Summary one"
    assert row.agent_usage_notes == "Notes one"
    assert row.updated_by is None


@pytest.mark.asyncio
async def test_reseed_overwrites_when_updated_by_is_null(db_session, starter_folder, tmp_path):
    flow = await _seed_flow(db_session, starter_folder.id, "Sample Template")
    _write_metadata_file(tmp_path, "Sample Template", "Summary one", "Notes one")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Edit the file and re-seed
    _write_metadata_file(tmp_path, "Sample Template", "Summary TWO", "Notes TWO")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = (await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id))).all()
    assert len(rows) == 1
    assert rows[0].agent_summary == "Summary TWO"
    assert rows[0].agent_usage_notes == "Notes TWO"


@pytest.mark.asyncio
async def test_reseed_skips_when_admin_has_edited(db_session, starter_folder, tmp_path):
    flow = await _seed_flow(db_session, starter_folder.id, "Sample Template")
    _write_metadata_file(tmp_path, "Sample Template", "Summary one", "Notes one")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Simulate admin edit: set updated_by to a non-null UUID
    row = (
        await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id))
    ).one()
    row.updated_by = uuid4()
    row.agent_summary = "Admin Edited Summary"
    db_session.add(row)
    await db_session.commit()

    # Edit the file again and re-seed
    _write_metadata_file(tmp_path, "Sample Template", "Summary THREE", "Notes THREE")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    refreshed = (
        await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id))
    ).one()
    assert refreshed.agent_summary == "Admin Edited Summary"  # unchanged


@pytest.mark.asyncio
async def test_missing_flow_is_logged_and_skipped(db_session, starter_folder, tmp_path):
    """Sibling metadata file present, but no matching seeded flow → skip, don't raise."""
    _write_metadata_file(tmp_path, "Nonexistent Template", "x", "y")

    # Should not raise
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = (await db_session.exec(select(TemplateMetadata))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_malformed_json_is_logged_and_skipped(db_session, starter_folder, tmp_path, caplog):
    flow = await _seed_flow(db_session, starter_folder.id, "Good Template")
    _write_metadata_file(tmp_path, "Good Template", "good summary", "good notes")

    # Add a malformed sibling for a different (also seeded) flow
    bad_flow = await _seed_flow(db_session, starter_folder.id, "Bad Template")
    (tmp_path / "Bad Template.json").write_text(json.dumps({"name": "Bad Template", "data": {"nodes": [], "edges": []}}))
    (tmp_path / "Bad Template.metadata.json").write_text("{this is not valid json")

    # Should not raise
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Good Template's metadata still got seeded
    good_rows = (await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id))).all()
    assert len(good_rows) == 1
    # Bad Template has no row
    bad_rows = (await db_session.exec(select(TemplateMetadata).where(TemplateMetadata.flow_id == bad_flow.id))).all()
    assert bad_rows == []
```

(`db_session` fixture: use the langflow test fixture pattern. Inspect existing test files like `src/backend/tests/unit/services/assistant/test_flow_template_context.py` for the canonical async DB-session fixture and reuse.)

- [x] **Step 3: Run the tests to verify they fail**

```bash
uv run pytest src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py -v
```

Expected: FAIL with `ImportError` (function doesn't exist yet).

- [x] **Step 4: Implement `create_or_update_template_metadata`**

Open `src/backend/base/langflow/initial_setup/setup.py`. Add the function after `create_or_update_starter_projects` (around line 1200, just below the existing seeder):

```python
async def create_or_update_template_metadata(
    starter_projects_dir: anyio.Path | Path | None = None,
) -> None:
    """Seed TemplateMetadata rows from sibling metadata JSON files.

    For each ``<TemplateName>.metadata.json`` in ``starter_projects_dir``
    (defaults to the standard starter-projects directory), upsert a
    TemplateMetadata row pointing at the matching seeded flow.

    Upsert policy:
    - No existing row → INSERT with ``updated_by=None``.
    - Existing row, ``updated_by IS NULL`` → UPDATE (re-seed).
    - Existing row, ``updated_by IS NOT NULL`` → SKIP (admin took ownership).

    Idempotent. Runs after ``create_or_update_starter_projects`` so the
    Flow rows the metadata references already exist.
    """
    if starter_projects_dir is None:
        starter_projects_dir = anyio.Path(__file__).parent / "starter_projects"
    else:
        starter_projects_dir = anyio.Path(starter_projects_dir)

    metadata_files: list[anyio.Path] = []
    async for f in starter_projects_dir.glob("*.metadata.json"):
        metadata_files.append(f)

    if not metadata_files:
        await logger.adebug("No template metadata files found; skipping metadata seeding.")
        return

    async with session_scope() as session:
        starter_folder = await get_or_create_starter_folder(session)

        for meta_file in metadata_files:
            template_name = meta_file.name[: -len(".metadata.json")]
            try:
                content = await meta_file.read_text(encoding="utf-8")
                payload = orjson.loads(content)
            except orjson.JSONDecodeError as e:
                await logger.aexception(
                    f"Skipping malformed metadata file {meta_file.name}: {e}"
                )
                continue
            except Exception as e:  # noqa: BLE001
                await logger.aexception(
                    f"Skipping metadata file {meta_file.name}: {e}"
                )
                continue

            agent_summary = payload.get("agent_summary")
            agent_usage_notes = payload.get("agent_usage_notes")

            # Look up the matching flow by name within the Starter Projects folder
            flow_stmt = select(Flow).where(
                Flow.name == template_name,
                Flow.folder_id == starter_folder.id,
            )
            flow = (await session.exec(flow_stmt)).first()
            if flow is None:
                await logger.awarning(
                    f"Template metadata file {meta_file.name} has no matching "
                    f"starter-project flow named '{template_name}' — skipping."
                )
                continue

            # Check for existing TemplateMetadata row
            existing_stmt = select(TemplateMetadata).where(TemplateMetadata.flow_id == flow.id)
            existing = (await session.exec(existing_stmt)).first()

            if existing is None:
                row = TemplateMetadata(
                    flow_id=flow.id,
                    agent_summary=agent_summary,
                    agent_usage_notes=agent_usage_notes,
                    updated_by=None,
                )
                session.add(row)
                await logger.adebug(
                    f"Seeded TemplateMetadata for '{template_name}' (flow_id={flow.id})."
                )
            elif existing.updated_by is None:
                existing.agent_summary = agent_summary
                existing.agent_usage_notes = agent_usage_notes
                session.add(existing)
                await logger.adebug(
                    f"Re-seeded TemplateMetadata for '{template_name}' (admin had not edited)."
                )
            else:
                await logger.adebug(
                    f"Skipping TemplateMetadata seed for '{template_name}': "
                    f"admin has taken ownership (updated_by={existing.updated_by})."
                )
```

Imports to add at the top of `setup.py` (next to existing imports):

```python
from sqlmodel import select  # if not already imported
from langflow.services.database.models.template_metadata.model import TemplateMetadata
```

(Check whether `select` is already imported via sqlmodel; setup.py likely uses a different ORM helper. If it imports from `sqlalchemy.future`, mirror that style.)

- [x] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py -v
```

Expected: 5 PASS.

If a test fails because of fixture-shape issues (e.g., `db_session` doesn't have `exec`), align with the project's actual async-session API by inspecting an existing similar test and matching its style.

- [x] **Step 6: Stage**

```bash
git add src/backend/base/langflow/initial_setup/setup.py \
        src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py
```

---

## Task 4: Wire seeder into the lifespan startup hook

**Files:**
- Modify: `src/backend/base/langflow/main.py:220` — add the new seeder call after `create_or_update_starter_projects`.

- [x] **Step 1: Read the existing lifespan hook context**

Open `src/backend/base/langflow/main.py:220`. Confirm the surrounding shape — there's a try/except around starter-project setup, and the line currently reads `await create_or_update_starter_projects(all_types_dict)`.

- [x] **Step 2: Update the import at top of `main.py`**

Add `create_or_update_template_metadata` alongside `create_or_update_starter_projects`. Find the import block around line 33:

```python
from langflow.initial_setup.setup import (
    ...
    create_or_update_starter_projects,
    ...
)
```

Add the new function name to that import group:

```python
from langflow.initial_setup.setup import (
    ...
    create_or_update_starter_projects,
    create_or_update_template_metadata,
    ...
)
```

- [x] **Step 3: Insert the call after the existing seeder**

In the lifespan hook, change:

```python
                    await create_or_update_starter_projects(all_types_dict)
```

to:

```python
                    await create_or_update_starter_projects(all_types_dict)
                    await create_or_update_template_metadata()
```

The same try/except wrapping (if present) covers both calls — the metadata seeder swallows individual file errors per its own contract, but a startup-level failure logs and continues.

- [x] **Step 4: Smoke test — boot the app once**

```bash
cd /Users/brycedeneen/dev/langflow
uv run langflow run --backend-only --no-open-browser 2>&1 | head -100
```

Watch for:
- `Loaded N starter projects` line (should be N+1 over baseline if the new template was added in Task 2 — but only if `update_starter_projects=true`).
- `Seeded TemplateMetadata for 'ADP Worker Sync to SFTP'` debug line (or similar — depends on log level).
- No tracebacks.

Kill the process (`Ctrl+C`) once startup logs settle.

- [x] **Step 5: Verify the metadata row exists**

```bash
sqlite3 ~/.cache/langflow/langflow.db "SELECT flow_id, agent_summary, length(agent_usage_notes), updated_by FROM template_metadata;"
```

Expected: at least one row for the ADP template with a non-null `agent_summary`, an `agent_usage_notes` length around 2000–3000 chars, and `updated_by` empty.

- [x] **Step 6: Run the broader test surface**

```bash
uv run pytest src/backend/tests/unit/initial_setup/ src/backend/tests/unit/services/assistant/ -v
```

Expected: ALL PASS.

- [x] **Step 7: Stage**

```bash
git add src/backend/base/langflow/main.py
```

---

## Task 5: Manual end-to-end verification

**Files:** none modified. Output is a verification report.

Validates that the template loads, appears in the picker, and the assistant follows `agent_usage_notes` end-to-end.

- [x] **Step 1: Boot the dev environment**

Backend running, frontend dev server up. LLM provider configured for the assistant. Wipe local sqlite if you want to test cold-start behavior, otherwise existing variables persist between Path 1 and Path 2.

- [x] **Step 2: Confirm template appears in picker**

In the app: **New Project** → template grid. Confirm `ADP Worker Sync to SFTP` shows up with the description from the JSON. Click it → confirm preview/details look right.

- [x] **Step 3: Path 1 — credentials missing (clean slate)**

If you have `adp_*` variables already, delete them via the variable store UI first.

Click **Build with ADP Assist** on the template card. Confirm:

- The fullscreen assistant opens.
- The opening message uses the script's framing: "I'll guide you through a few quick questions to set up your ADP→SFTP sync. Once it's running, you can customize anything…"
- Assistant immediately asks for the four ADP credentials in plain language (client ID, secret, certificate, key).
- Provide each — confirm a variable is created in the variable store after each (`adp_client_id`, `adp_client_secret`, `adp_client_certificate`, `adp_client_key`).
- Once all four are saved, assistant says "Saved securely — these will be reused for any future ADP integrations." and proceeds.

- [x] **Step 4: Path 1 continued — the 5 questions**

Walk through:

1. Fields → reply `name, address, phone, email, job`.
2. SFTP host → `localhost`.
3. SFTP username → `bryce`.
4. SFTP password → `P@ssword1!`. Confirm assistant says it's storing securely as a variable.
5. Filename pattern → `test, then a dash, then a datestamp and it'll be a csv file`. Confirm assistant confirms with an example like `test-20260419_143052.csv`.

Then watch for:

- Canvas shows 4 nodes wired: ADP Trigger → Agent (with ADP Worker Tools attached) → SFTP CSV Upload.
- Agent's `output_schema` shows 5 string rows.
- SFTP `password` field shows a variable reference (e.g., `sftp_password_<short_token>`), not the literal `P@ssword1!`.
- Assistant's final message contains the webhook URL + API key with `x-api-key` instructions.

- [x] **Step 5: Path 2 — credentials already configured (re-test)**

Open another new flow from the same template via Build with ADP Assist. Confirm:

- Assistant says "I found your ADP credentials." and **skips straight to the 5 questions** without re-asking for ADP creds.

- [x] **Step 6: Smoke test — fire a fake webhook**

Using the surfaced URL + API key from Path 1's flow:

```bash
curl -X POST "<surfaced_webhook_url>" \
  -H "x-api-key: <surfaced_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"eventNameCode":{"codeValue":"worker.hire"},"data":{"output":{"worker":{"person":{"legalName":{"formattedName":"Test User"},"legalAddress":{"lineOne":"123 Main"},"communication":{"emails":[{"emailUri":"test@example.com"}]}}}}},"effectiveDateTime":"2026-04-19T00:00:00Z"}]}'
```

Expected: the SFTP target receives a CSV file named like `test-20260419_143052.csv` containing one row with the requested fields.

- [x] **Step 7: Report readiness**

Post a verification report:

```
## Manual e2e findings — ADP→SFTP template

Template appears in picker: yes/no
Build with ADP Assist opens script: yes/no

Path 1 (creds missing):
- Asked for 4 ADP creds first: yes/no
- Variables created with canonical names: yes/no
- Then walked the 5 questions in order: yes/no
- Built canonical 4-node flow: yes/no
- output_schema has 5 rows: yes/no
- SFTP password is a variable reference: yes/no
- Surfaced webhook URL + API key: yes/no

Path 2 (creds already exist):
- Skipped ADP creds, jumped to 5 questions: yes/no

Smoke test (Step 6): pass/fail/skipped
Notes: [...]
Ready to commit: yes/no
```

If issues appear, file as follow-up tasks. Real-LLM behavior is expected to need at least one prompt-tuning iteration.

---

## Open items / call-outs

- **Commit batching.** All tasks stage only. Human batches commits at the end (matches the pattern of all prior assist plans).
- **Template-management-phase-1 retargeting.** When the new `Template` SQLModel lands, the seeder gets a small retarget: replace the Folder + Flow lookup with a Template lookup. Out of scope for this plan.
- **`agent_usage_notes` content iteration.** The script in Task 2 Step 2 is a tight first cut. Real LLM behavior will reveal phrasings that need tightening — those edits go through the file (with `updated_by IS NULL` policy keeping re-seeds safe) until the admin UI from template-management-phase-1 lands.
- **Other code-shipped templates.** Any future template just drops a `<Name>.json` + `<Name>.metadata.json` pair into `starter_projects/`. No code changes needed.
