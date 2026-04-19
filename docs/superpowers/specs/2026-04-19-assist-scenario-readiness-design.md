# ADP Assist — Scenario Readiness

**Date:** 2026-04-19
**Status:** Draft

## Overview

Make two client-shaped workflows work end-to-end on a blank flow with the **Build with ADP Assist** experience:

- **Scenario A (detailed prompt):** user provides every detail in one message and asks the assistant to build the flow and surface webhook credentials.
- **Scenario B (vague prompt):** user states intent only; assistant asks for the missing details one question at a time, then builds and surfaces credentials.

Both scenarios converge on the same flow shape: an ADP webhook that fires on hire and termination events, extracts a user-chosen set of worker fields, and uploads them as CSV to an SFTP server. The assistant returns the webhook URL and API key so the user can register them with ADP.

A pre-built **template** for this same shape is treated as a separate, smaller follow-on (template JSON + `agent_instructions` content). This spec is the platform work that makes the template — and any future blank-flow build of the same shape — succeed.

The `assist-polish-phase-1` plan (overlay CSS variables + pipeline-card icon styling) is unrelated and unaffected.

## Goals

- An assistant conversation that takes either prompt shape (detailed or vague) and ends with a working `ADP Trigger → Agent → SFTP CSV Upload` flow plus the webhook credentials surfaced in chat.
- Multi-source forward-compatibility: the same wiring pattern (`Trigger → Agent + tools → Sink`) extends to "ADP + Workday" or "ADP + Salesforce" cases by attaching more tools to the Agent. No new component categories required.
- Open behavior on blank flows; prescriptive behavior when a template's `agent_instructions` are present.

## Non-goals

- The Scenario 1 template JSON and `agent_instructions` content (separate follow-on once this work lands).
- Multi-source flows themselves (Workday, Salesforce). Architecture supports them; out of scope for this spec.
- UI work for editing the Agent's structured-output schema. The assistant configures it programmatically through `set_field_value`.
- `assist-polish-phase-1` items.

## Architecture

### The canonical wiring

For "ADP events → external system" intents, the assistant builds:

```
ADP Trigger ──► Agent (with ADP Worker Tools) ──► SFTP CSV Upload
```

- **ADP Trigger** filters incoming webhooks by `event_types`. For "hire and termination" the assistant selects `New Hire`, `Retirement`, and `Deceased`.
- **Agent (the bridge)** receives the trigger's `Data` output, extracts the user-chosen fields from the worker payload, and emits a flat JSON object the SFTP component can serialize as a CSV row. Configured by the assistant with:
  - A fast/cheap model default (e.g., Haiku) since events are infrequent but cost still matters.
  - A system prompt that names the requested fields and instructs the agent to use ADP Worker Tools to fetch anything missing from the trigger payload.
  - A structured-output JSON schema (one string property per field) so columns are deterministic and order-stable.
  - **ADP Worker Tools** attached as the agent's tools.
- **SFTP CSV Upload** writes the row to the configured server. Filename pattern supports `{datestamp}` (alias for `{timestamp}` — date+time, collision-safe).

The assistant explains the Agent in user terms ("the smart middleman that pulls together exactly the fields you asked for"), not as "an LLM agent."

### Why an Agent, not a dedicated mapper component

A dedicated `ADP Worker → CSV` mapper component would be simpler for this single scenario, but the real client need is composing data from multiple sources (multiple ADP datasets, or ADP + a third-party system) into a single CSV. The Agent + tools pattern is the design pattern for that case: adding a new source means registering a new tool, not introducing new component categories or merge/join glue.

## Code changes

Three changes total: an assistant system prompt addition, a new assistant tool, and a one-line component alias.

### 1. Assistant system prompt — three new blocks

Added to the existing system prompt assembled in `src/backend/base/langflow/services/assistant/service.py` (or wherever the prompt is composed today; the implementation plan will confirm the exact location).

**Block 1 — Conversation pacing rules** (applies to all blank-flow conversations, not just ADP):

- When the user gives information upfront, do not re-ask for it. Acknowledge what was provided, state the plan in one sentence, and proceed.
- When information is missing, ask one question at a time. Wait for the answer before asking the next.
- Use friendly, non-technical language. "What should we name the files?" not "Set the SFTP filename pattern."
- Confirm scope in one sentence before the first question. ("Got it — I'll set up X that does Y when Z. Let me ask a few questions:")
- Propose sensible defaults; only ask when the choice matters. Do not ask about SFTP port if 22 is fine — use it and mention it.
- After building, narrate what was done and surface anything the user must act on (for example, the webhook URL and API key needed by the upstream system).

**Block 2 — ADP integration playbook** (specific to ADP-event-driven intents):

- Canonical wiring: `ADP Trigger → Agent (bridge) → Sink component`. Use this shape whenever the user wants to react to ADP events by sending data somewhere.
- Event groupings to recognize:
  - "hire" / "onboarding" / "new employee" → `New Hire` (optionally also `Rehire` — confirm).
  - "termination" / "leaving" / "offboarding" → `Retirement` + `Deceased` (confirm before applying).
  - "leave" / "out of office" → `Leave`.
- Bridge Agent configuration:
  - Default to a fast/cheap model (Haiku class).
  - Attach `ADP Worker Tools` so the agent can fetch additional worker data if the trigger payload is sparse.
  - System prompt template: "You receive an ADP worker event. Extract the following fields from the payload and return a single JSON object: <user's field list>. If any field is missing, use the tools to fetch it."
  - Set structured output: a JSON schema with one string property per requested field.
- Friendly field-name → ADP payload hints to give the agent in its prompt (not for the assistant's own translation):
  - name → `person.legalName.formattedName`
  - address → `person.legalAddress`
  - phone → `person.communication.mobiles[0]` or `landlines[0]`
  - email → `person.communication.emails[0].emailUri`
  - job → `workAssignments[0].jobTitle`
  - compensation → call the `get_employee_compensation` tool
- After wiring all three nodes, call `get_node_field_value(trigger_node_id, "endpoint")` and `get_node_field_value(trigger_node_id, "api_key")`. Present both in chat with: "Give this URL to ADP under Event Notification subscriptions; include the API key as the `x-api-key` header." Then suggest running Test mode.

**Block 3 — Template override:**

- If template `agent_instructions` are present in the conversation context, those instructions take precedence over the playbook. Use them as the starting point; fall back to the playbook only for things the template does not specify.

### 2. New assistant tool: `get_node_field_value`

**File:** new `src/backend/base/langflow/services/assistant/tools/inspection.py`. Separated from `mutation.py` because the semantics differ (read vs. write).

**Signature:**

```python
def get_node_field_value(node_id: str, field_name: str) -> str
```

Reads the current value of one field on one node in the active flow. Returns the value as a string, or a clear error string:

- `"node not found: <id>"` when `node_id` does not exist.
- `"field not found on node: <name>"` when `field_name` is not present on the node template.
- `""` when the field exists but the value is empty.

No redaction. The assistant operates on behalf of the user, who would see these values in the UI anyway. Redaction would defeat the api_key surfacing flow.

**Registration:** added to `tools/registry.py` alongside catalog/mutation tools. The existing tool dispatch in `service.py` (getattr-style lookup) supports it without changes.

**Tests:**

- After `add_component("ADPTrigger")` followed by a flow save, calling `get_node_field_value(node_id, "api_key")` returns a non-empty string (auto-provisioned).
- Bad `node_id` returns `"node not found: <id>"`.
- Bad `field_name` returns `"field not found on node: <name>"`.

**Verify-before-implement (called out in the implementation plan):**

- Webhook api_key auto-provisioning currently runs on flow create/update. Confirm that by the time the assistant calls `get_node_field_value` after `add_component`, the api_key field is populated. If a "save and refresh" round-trip is needed first, add it as an explicit step.

### 3. SFTP filename `{datestamp}` alias

**File:** `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`, in `_resolve_remote_path()`.

Add `{datestamp}` as an alias for `{timestamp}` (date+time, e.g., `20260419_143052`). Not for `{date}`: defaulting to date-only would silently overwrite files when multiple events fire on the same day.

If a user explicitly wants date-only filenames, the assistant offers `{date}` instead and confirms the trade-off.

**Test:** filename `test-{datestamp}.csv` resolves to `test-20260419_143052.csv` against a frozen test clock.

## Conversation walkthroughs

### Scenario A — detailed prompt

1. User clicks **Build with ADP Assist** on a blank flow → fullscreen → assistant greets.
2. User provides the full prompt (fields, host, username, password, filename, "give me URL + key").
3. Assistant recognizes the shape, sees nothing missing, skips question phase per pacing rule, and confirms scope in one line: "Got it — I'll set up an ADP webhook on hire and termination events, extract name/address/phone/email/job from each worker, and upload as CSV to localhost. Building now…"
4. Assistant builds the canonical 3-node flow, narrating each step:
   - `add_component("ADPTrigger")` with `event_types: [New Hire, Retirement, Deceased]`.
   - `add_component("Agent")` with model: Haiku-class; system prompt seeded with the 5 field names; structured output schema = `{name, address, phone, email, job}` (strings).
   - `add_component("ADPWorkerTools")` and tool-attach to the Agent.
   - `add_component("SFTPCSVUpload")` with `host: localhost`, `username: bryce`, `password: P@ssword1!`, `filename: test-{datestamp}.csv`.
   - `connect_edge` Trigger → Agent, Agent → SFTP.
5. Assistant calls `get_node_field_value(trigger_id, "endpoint")` and `("api_key")`, then closes:
   > "Done. Webhook URL: `…/api/v1/webhook/<flow_id>` — API key: `lf_…`. Add an ADP Event Notification to that URL with header `x-api-key: lf_…`. Files will be named like `test-20260419_143052.csv`. Want to test it?"

### Scenario B — vague prompt

1. User clicks **Build with ADP Assist** on a blank flow → fullscreen → assistant greets.
2. User states intent only.
3. Assistant confirms scope, then asks Q1: "Got it — I'll set up an ADP webhook on hire and termination events that uploads worker data to an SFTP server. Let me ask a few questions: **what fields do you want to include?**"
4. Q→A loop, one turn each, in this order: fields → host → username → password → filename pattern. Password acknowledgment: "(storing securely)".
5. Build phase identical to Scenario A from step 4 onward.

Same end state. Assistant volunteers URL + api_key even though the user did not explicitly request them — they are needed to make the trigger useful.

### Scenario 1 — template-driven (forward-compat check)

The user picks the (yet-to-be-built) **ADP Worker Sync to SFTP** template, then **Build with ADP Assist**. Template ships with the 3-node flow already wired but unconfigured, and `TemplateMetadata.agent_instructions` says: "Ask in order: fields → host → username → password → filename. Then update the Agent's prompt and structured-output schema and the SFTP component's credentials and filename. Then surface URL + api_key."

Per Block 3 (template override), the assistant follows that script instead of the playbook. Same five questions, but on a pre-wired canvas → fewer mutations, more deterministic, faster. The follow-on work is two items: (a) author the template JSON, (b) write the `agent_instructions` content. No code changes beyond this spec.

## Risks to verify before coding

The implementation plan must verify each of these as a "task 1" check, not assume them.

1. **Webhook api_key timing.** Auto-provisioning happens on flow create/update (commit `3f62cd1185`). Confirm that `get_node_field_value` reads a populated value immediately after `add_component`. If a save/refresh is required first, add it as an explicit step.
2. **Agent structured-output input shape.** Confirm what format `set_field_value` accepts for the structured-output field (JSON string, schema object, or other). The assistant must be able to set it programmatically.
3. **Tool-attach edge type.** Confirm `connect_edge` supports the tool-attachment edge variant for Agent ↔ ADP Worker Tools (vs. data-flow edges). If the edge type differs, expose the variant in the mutation tool's signature.
4. **SecretStr routing.** Confirm the LFX layer routes a password set via `set_field_value` through the secret store rather than persisting it plain. The SFTP component's `password` is `SecretStrInput`, so the framework should handle this; verify it does.

## Testing strategy

- **Unit tests** for the new `get_node_field_value` tool (happy path + both error cases).
- **Unit test** for the SFTP `{datestamp}` alias against a frozen clock.
- **Assistant integration test** that exercises Scenario A end-to-end against a fake LLM provider whose responses are scripted to mirror the playbook (asserts the right tool calls in the right order, including the trailing `get_node_field_value` calls).
- **Assistant integration test** that exercises Scenario B end-to-end, asserting the assistant asks five questions in the documented order before building.
- **Manual e2e** of both scenarios against a real assistant LLM and a local SFTP target to confirm the full-screen UX feels right and the webhook credentials are usable.

## Files touched (best estimate; plan will confirm)

### Backend

- `src/backend/base/langflow/services/assistant/service.py` — system prompt assembly.
- New: `src/backend/base/langflow/services/assistant/tools/inspection.py` — `get_node_field_value`.
- `src/backend/base/langflow/services/assistant/tools/registry.py` — register the new tool.

### LFX

- `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py` — `{datestamp}` alias.

### Tests

- `src/backend/tests/unit/services/assistant/tools/test_inspection.py` (new).
- `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py` — extend existing.
- `src/backend/tests/integration/assistant/` — Scenario A and Scenario B end-to-end tests (new).
