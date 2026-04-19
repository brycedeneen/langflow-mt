# ADP → SFTP Template + Sibling-Metadata Seeder

**Date:** 2026-04-19
**Status:** Draft

## Overview

Ship the first end-to-end template for the ADP Assist UX, plus the small platform piece that lets future code-shipped templates carry their assistant instructions alongside their flow JSON.

The user-facing artifact is a starter project named **ADP Worker Sync to SFTP**: a pre-wired four-node flow (`ADP Trigger → Agent + ADP Worker Tools → SFTP CSV Upload`) with sensible defaults already filled. Clicking it from the template picker and choosing **Build with ADP Assist** opens the full-screen assistant, which reads the template's `agent_usage_notes` and walks the user through five short questions (fields, SFTP host/user/password, filename pattern), wires the answers, and surfaces the auto-provisioned webhook URL and API key.

The platform piece is a **sibling-metadata-file convention**: any code-shipped template can ship a `<TemplateName>.metadata.json` next to its flow JSON in `initial_setup/starter_projects/`, and a new startup-time seeder upserts the corresponding `TemplateMetadata` row. The convention is generic; the ADP→SFTP template is the first consumer.

This work proves the template path of the ADP Assist experience end-to-end. The downstream Save-as-Template UX, admin metadata editor, and the `Template` SQLModel that replaces the starter-folder convention all live in a separate **template-management-phase-1** plan; the seeder we add here will be retargeted at that time.

## Goals

- A working ADP→SFTP template that a non-technical user can pick from the template grid and configure end-to-end with ADP Assist in about five back-and-forth turns.
- A reusable convention for shipping code-side templates with `agent_summary` + `agent_usage_notes` so future templates (ADP→Snowflake, ADP→Slack, Workday→S3, etc.) need no extra plumbing.
- Idempotent seeding that respects admin edits — once an admin has touched a template's metadata via the existing admin API, the seeder must not clobber it.

## Non-goals

- Template versioning and downstream-flow upgrade propagation (separate project).
- The `Template` SQLModel that replaces the starter-folder convention, the Save-as-Template modal, the admin metadata editor — all in `template-management-phase-1`.
- Other ADP-themed templates (Snowflake sink, Slack notify, etc.). Same pattern, future work.
- Frontend changes. The existing template picker + Build with ADP Assist button cover the UX.
- Hardening the seeder for non-Starter-Projects metadata files. Code-shipped only; user-created templates are template-management-phase-1's territory.

## Architecture

### Two artifacts

1. **The ADP→SFTP template, two co-located files in `src/backend/base/langflow/initial_setup/starter_projects/`:**
   - `ADP Worker Sync to SFTP.json` — the flow (four nodes pre-wired, defaults filled, structurally complete).
   - `ADP Worker Sync to SFTP.metadata.json` — the `agent_summary` (for blank-flow template-matching) and the `agent_usage_notes` script.

2. **A new metadata seeder** in `initial_setup/setup.py`. Walks the starter-projects directory, finds each `*.metadata.json` file, upserts a `TemplateMetadata` row pointing at the matching seeded flow. Runs at app startup, after the existing `create_or_update_starter_projects`, inside the same file lock (`/tmp/langflow_starter_projects.lock`) to avoid multi-worker races.

### Reused (no new code)

- The template appears in the standard template grid via `GET /flows/basic_examples/`.
- Build with ADP Assist creates a new flow with `based_on_template_flow_id` pointing at the template flow.
- The assistant reads `based_on_template_flow_id`, calls `get_template_instructions(template_flow_id)`, fetches `agent_usage_notes`, and follows the script.
- The playbook's mechanics (`create_secret_variable`, `set_field_value`, `list_user_variables`, `get_webhook_credentials`, the two-step secret-variable pattern, the required-fields check, the post-build credentials surfacing) are all in the system prompt from prior work. The script references those tools by name; it does not re-explain them.

## The template flow JSON

Four nodes, three edges. Per the design's "filled defaults" choice: structurally complete, defaults that don't depend on user input are pre-filled.

### Nodes

| Node | Component type | Pre-filled fields | Empty fields (assistant fills) |
|---|---|---|---|
| ADP Trigger | `ADPTriggerComponent` | `event_types: ["New Hire", "Retirement", "Deceased"]` | none — `endpoint` and `api_key` are framework-managed |
| Agent | `Agent` | `model_provider: "Anthropic"`, `model_name: <Haiku-class id>` | `system_prompt` (assistant fills with field list); `output_schema` (`[]` initially; assistant appends one row per chosen field) |
| ADP Worker Tools | `ADPWorkerToolsComponent` | `client_id: "adp_client_id"`, `client_secret: "adp_client_secret"`, `client_certificate: "adp_client_certificate"`, `client_key: "adp_client_key"` (variable-name references via `SecretStrInput.load_from_db=True`) | none — credentials resolve from the user's variable store |
| SFTP CSV Upload | `SFTPCSVUploadComponent` | `port: 22`, `remote_directory: "/"`, plus the component's existing CSV defaults | `host`, `username`, `password`, `filename` |

The Agent's `model_provider` / `model_name` defaults assume Anthropic is the most common configuration; the assistant swaps at build time per the playbook's "fast/cheap default" rule if the tenant only has another provider configured.

### Edges

Three:

1. **ADP Trigger → Agent** (data flow). Source output: the trigger's primary `Data` output. Target input: the Agent's primary input.
2. **ADP Worker Tools → Agent** (tool attachment). Source handle uses `name: "component_as_tool"`, `output_types: ["Tool"]`. Target handle uses `fieldName: "tools"`, `inputTypes: ["Tool"]`. Verified shape from prior spike.
3. **Agent → SFTP CSV Upload** (data flow). The Agent's structured-output JSON object flows in as the row data.

### Top-level template fields

- `name: "ADP Worker Sync to SFTP"`
- `description: "Sync ADP worker data to a CSV on an SFTP server when employees are hired or terminated. The assistant guides you through the SFTP details."`
- Standard starter-project fields (folder reference, etc.) per the existing convention.

### Canvas layout

Cosmetic, not behavioral. Left-to-right: Trigger (x≈200) → Agent (x≈700, y centered) → SFTP (x≈1200). ADP Worker Tools sits below the Agent (x≈700, y offset down) since it's a tool attachment, not a data-flow node.

## The metadata sibling file

### File location

`src/backend/base/langflow/initial_setup/starter_projects/<Template Name>.metadata.json`. Filename matches the flow JSON's name minus the `.json` extension.

### Shape

```json
{
  "agent_summary": "<short summary for the assistant's Available Templates block>",
  "agent_usage_notes": "<the prescriptive script the assistant follows when this template is loaded>"
}
```

Two fields, both mapping 1:1 to columns on `TemplateMetadata`. No `template_version`, no extra metadata. Future versioning work introduces its own fields when needed.

### Seeder behavior

New function in `initial_setup/setup.py`, called from the lifespan startup hook *after* `create_or_update_starter_projects` completes. Per metadata file:

1. Read and parse the JSON. On parse failure: log and skip (don't break startup of other templates).
2. Look up the matching flow by `name` (= filename minus `.metadata.json`) within the Starter Projects folder. If no flow found: log and skip — the template wasn't seeded (e.g., `update_starter_projects` is false and the flow is missing).
3. Check for an existing `TemplateMetadata` row by `flow_id`:
   - **No row exists** → INSERT with `updated_by = NULL`, `updated_at = now()`.
   - **Row exists and `updated_by IS NULL`** → UPDATE (overwrite from file). The metadata is in its "seed-only" state; no admin has taken ownership; re-seeding lets developers iterate by editing the file and restarting.
   - **Row exists and `updated_by IS NOT NULL`** → SKIP. An admin has edited via the admin API; we do not clobber. Code-side updates require a manual DELETE of the row, or going through the admin API to merge.

### Why `updated_by IS NULL` as the marker

Clean signal, no schema additions. Forward-compatible: a future "system pseudo-user" approach can replace null with a sentinel without breaking the policy. Decoupled from versioning: editing `agent_usage_notes` does not change the template's version, and re-seeding the flow does not trash unrelated metadata edits.

### Idempotency

The seeder runs every startup, like the existing starter-projects seeder. Re-runs are no-ops once the metadata is in place (until either the file content changes and `updated_by IS NULL`, or the admin edits via UI).

### File lock

Runs inside the existing `/tmp/langflow_starter_projects.lock` to coexist with multi-worker startups.

## The ADP→SFTP `agent_usage_notes` content

The actual prescriptive script the assistant reads. Plain markdown so admins can edit without a syntax. Stored in the sibling JSON's `agent_usage_notes` field as a single string.

```markdown
You are guiding a user through configuring the **ADP Worker Sync to SFTP** template. The flow is pre-wired — your job is to fill in the variable bits via a short, friendly conversation.

## Opening
Open with one short sentence framing the experience:

> "I'll guide you through a few quick questions to set up your ADP→SFTP sync. Once it's running, you can customize anything — add fields, change the destination, swap components."

## Pre-flight — ADP credentials
Before any other question:
1. Call `list_user_variables`.
2. Confirm these four exist: `adp_client_id`, `adp_client_secret`, `adp_client_certificate`, `adp_client_key`.
3. If all four exist → say "I found your ADP credentials." and proceed.
4. If any are missing → tell the user which in plain language ("I need your ADP credentials. Specifically: client ID, client secret, certificate, and key."). Ask one at a time. For each, call `create_secret_variable(name=<canonical_name>, value=<input>)` using the names above. After all four exist: "Saved securely — these will be reused for any future ADP integrations."

(The ADP Worker Tools node's credential fields are already wired to these variable names, so no per-flow `set_field_value` for credentials.)

## The 5 questions
Ask in order, one at a time, in friendly language. Skip any the user already answered in their first message.

1. **Fields.** "Which worker fields should we include in the CSV?" Suggest defaults inline: "(common ones: name, address, phone, email, job)". Accept the user's list verbatim.
2. **SFTP host.** "What's the address, URL, or IP of your SFTP server?"
3. **SFTP username.** "What username should we use to connect?"
4. **SFTP password.** "What's the password? (I'll store it securely as a variable.)"
5. **Filename pattern.** "What should each uploaded file be named?" If the user says "datestamp," use the `{datestamp}` placeholder (full date+time, collision-safe). Confirm with an example: "Files will be named like `test-20260419_143052.csv` — one per event."

## Wiring the answers
After all 5 are collected:

1. **Agent `output_schema`** — append one TableInput row per requested field: `{"name": "<field>", "description": "<one-line>", "type": "str", "multiple": false}`. Use the friendly-name → ADP payload hints from your playbook. Set via `set_field_value` on the Agent node.
2. **Agent `system_prompt`** — set to:
   > "You receive an ADP worker event. Extract these fields from the payload and return a single JSON object: <comma-separated fields>. If a field is missing from the payload, use the available tools to fetch it."
3. **SFTP node** — `set_field_value` for `host`, `username`, `filename` directly.
4. **SFTP password** — two-step pattern from your playbook:
   a. `create_secret_variable(name="sftp_password_<short_token>", value=<password>)` — pick a short descriptive token so the variable is recognizable in the variable store.
   b. `set_field_value(<sftp_node_id>, "password", "<variable_name>")`.

## Final delivery
After wiring, the flow auto-persists at end of turn. Then:

1. Call `get_webhook_credentials`.
2. Present in chat:
   > "Your sync is ready. Here's what to give to ADP:
   > - **Webhook URL:** `<endpoint>`
   > - **API Key:** `<api_key>`
   >
   > In ADP, create an Event Notification subscription pointing at this URL with header `x-api-key: <api_key>`."
3. Suggest: "Want to test it? Click **Test** in the header to send a sample payload through and verify each component."
4. Remind the user they own the flow now: "You can click into any component on the canvas to add fields, change credentials, or swap parts."

## Variations
- **Extra field beyond the standard 5** — add to `output_schema` + extend the system prompt's field list. Use `get_employee_compensation` for compensation; for rare fields, instruct the agent to pull from the payload directly.
- **User wants Rehire too** — `set_field_value` to add `Rehire` to the trigger's `event_types`.
- **User asks for a different sink (Slack, email, DB)** — this template isn't the right starting point. Suggest "Let's use a blank flow with the assistant" and exit the template script.
```

The corresponding `agent_summary`:

```
Sync ADP worker data to a CSV on an SFTP server when employees are hired or terminated. Pre-wired with ADP Trigger, an extraction Agent, and SFTP CSV Upload — the user provides the field list, SFTP credentials, and filename pattern.
```

## Risks to verify before coding

The implementation plan must verify each of these as a "task 1" check.

1. **`TemplateMetadata.updated_by` nullability.** The model needs to allow null so seed-time inserts succeed (no acting user). Check the existing migration; if non-nullable, add a small alembic revision.
2. **Flow lookup-by-name within the Starter Projects folder.** The seeder needs a query that finds a Flow by name scoped to the starter folder. Confirm the helper exists or write one.
3. **Seeding order and timing.** The new seeder must run inside the lifespan hook, *after* `create_or_update_starter_projects` (FK requirement: the Flow row must exist before the metadata row references it), and inside the same file lock (`/tmp/langflow_starter_projects.lock`).
4. **`based_on_template_flow_id` is set when "Build with ADP Assist" creates the flow.** Existing behavior per the assist work; the manual e2e confirms it. Without it, the assistant won't fetch `agent_usage_notes` and the script never runs.
5. **Tool-attach edge handle shape.** The verified shape (`source_handle.name = "component_as_tool"`, `target_handle.fieldName = "tools"`) must be used exactly in the template JSON. A test asserts this so a future hand-edit can't silently break tool attachment.

## Testing strategy

### Backend unit tests

- **Seeder behavior** (`test_template_metadata_seeding.py`):
  - First-time seed creates a row with `updated_by IS NULL`.
  - Re-running with no admin edit overwrites with file content.
  - Re-running with `updated_by` non-null skips (admin-edit protection holds).
  - Missing flow (sibling file present, no matching starter project): logged + skipped, no raise.
  - Malformed JSON: logged + skipped, doesn't break sibling templates.
- **Flow JSON shape** (`test_adp_sftp_template_shape.py`): load `ADP Worker Sync to SFTP.json` programmatically, assert four nodes with the expected `component_type`s, three edges with correct handle shapes (especially the tool-attach edge).
- **`agent_summary` reachable**: after seeding, `fetch_template_summaries` returns the ADP entry with the seeded summary. Confirms the LLM's "Available Templates" block sees it.

### Manual end-to-end

- Open the template picker → confirm the new template appears with description.
- Click → **Build with ADP Assist** → confirm the assistant opens with the script's opening line. (Proves `agent_usage_notes` is loaded and being followed.)
- **Path 1 — credentials missing.** First-run user (no `adp_*` variables exist). Confirm the assistant asks for the four ADP credentials first, creates variables, then proceeds to the five questions.
- **Path 2 — credentials already configured.** Re-test: variables exist from Path 1. Confirm the assistant says "I found your ADP credentials" and skips straight to the five questions.
- Complete the five questions, confirm webhook URL + API key surface, confirm canvas matches the Scenario A end state.
- Smoke: send a fake ADP hire payload via curl using the surfaced URL+key, confirm a CSV lands on the SFTP target.

## Files touched (best estimate; plan confirms)

### New

- `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.json`
- `src/backend/base/langflow/initial_setup/starter_projects/ADP Worker Sync to SFTP.metadata.json`
- `src/backend/tests/unit/initial_setup/test_template_metadata_seeding.py`
- `src/backend/tests/unit/initial_setup/test_adp_sftp_template_shape.py`

### Modified

- `src/backend/base/langflow/initial_setup/setup.py` — add `create_or_update_template_metadata` function + call from the lifespan startup hook.

### Possibly

- A small alembic revision making `TemplateMetadata.updated_by` nullable, only if it isn't already.
