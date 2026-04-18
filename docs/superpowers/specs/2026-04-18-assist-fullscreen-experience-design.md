# ADP Assist Full-Screen Experience

**Date:** 2026-04-18
**Status:** Draft

## Overview

Plan 4 of the ADP Assist roadmap. Makes the fullscreen assistant **proactive** (speaks first on empty conversations) and **context-aware** (knows which template the flow was cloned from). Realizes §4 and the template-matching portions of §7 from `2026-04-18-adp-assist-flow-builder-design.md`. Builds on the layout shell from Plan 3 and the metadata layer from Plan 2.

This spec deliberately does not implement:
- Test Mode (pipeline view + per-node status) — Plan 5.
- Component-level test-failure → credential-guidance conversation — Plan 5 (wires test SSE into assistant context; this plan only seeds the prompt guidelines).
- Template management UI, versioning, field-level blanking — Plan 7 candidate (deferred).
- "Request Professional Services" intake + proposals — Plan 8 candidate (deferred).
- MCP ext-apps rich UI widgets — Plan 6 candidate (deferred).

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Proactive greeting mechanism | **New `POST /api/v1/assistant/flows/{flow_id}/greet` endpoint; LLM-authored; persisted as `AssistantMessage`.** | LLM-authored greeting handles template-selected and blank-flow cases without conditional string templates. Persistence means the greeting survives reloads and second-tab opens. Endpoint guard makes it idempotent (409 on already-greeted). |
| Linking a user flow back to its source template | **New `Flow.based_on_template_flow_id: UUID \| null` column; FK → `flow.id`, `ON DELETE SET NULL`.** | Nullable FK is cheap and queryable. Migrates cleanly to a `template_version_id` when Plan 7 ships. Prevents orphaned user flows when a template is deleted. |
| Applying a matched template to a blank flow | **New `apply_template(target_flow_id, template_flow_id)` assistant tool — atomic bulk operation.** | One tool call, idempotent, re-uses existing `flow_patch` SSE for frontend animation. Replaces the fool's errand of "LLM replays nodes via granular tools". Also sets the template pointer, so subsequent messages pick up template context for free. |
| "Opinionated" behavior | **Pure prompt engineering: three new `## Guidelines` bullets.** | YAGNI. The LLM is very good at opinionated narration when the prompt tells it to be. Reversible, cheap, no new code paths or UI. Upgrade path to a proposal-card UI exists if prompt-only proves insufficient. |
| "Ready to test?" transition | **Conversational only — LLM says "click Test", user clicks the header Test button from Plan 3.** | Simplest, zero new tools, reuses existing affordance. Avoids "mode whiplash" from the assistant flipping layout state behind the user's back. |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  User lands on a flow with fullscreen-mode assistant open.      │
│  useAssistantConversation hook loads the conversation.          │
│  Empty conversation + fullscreen mode → greet mutation fires.   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  POST /assistant/flows/{id}/greet                               │
│    1. Load/create AssistantConversation                         │
│    2. Guard: 409 if any assistant message already exists        │
│    3. Build system prompt incl. flow_template_context           │
│       (if flow.based_on_template_flow_id is set)                │
│    4. Send synthetic user turn "__greet__" to LLM               │
│    5. Persist LLM response as AssistantMessage(role=assistant)  │
│    6. Return the stored message                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend re-hydrates conversation → greeting appears.          │
│  User types a real reply → existing /messages SSE path.         │
└─────────────────────────────────────────────────────────────────┘

Supporting additions:

  Flow.based_on_template_flow_id (UUID, nullable, FK → flow.id, ON DELETE SET NULL)
    • Set at addFlow({ flow: template, built_with_assist: true }) time
    • Set by apply_template tool when LLM applies a template to a blank flow
    • Read per-message by build_flow_template_context() to inject
      TemplateMetadata.agent_usage_notes into system prompt

  apply_template(target_flow_id, template_flow_id) assistant tool
    • Atomically replaces target flow.data with template.data (ids regenerated)
    • Sets target.based_on_template_flow_id = template_flow_id
    • Returns {applied_patch, template_name}
    • Errors if target not empty or template not a starter project

  SYSTEM_PROMPT_TEMPLATE additions
    • flow_template_context placeholder before available_templates
    • 4 new Guidelines bullets: greeting trigger, opinionated narration,
      non-technical vocabulary, test hand-off
```

**What's untouched:**
- Existing `/messages` SSE endpoint, streaming, tool loop.
- Plan 3's layout modes, fullscreen shell, panel/test shells.
- Plan 2's `TemplateMetadata`, catalog-merge, `get_template_instructions`.

## Section 1: Data Model

### New column on `Flow`

Location: `src/backend/base/langflow/services/database/models/flow/model.py`. Added to `FlowBase` directly after `built_with_assist`:

```python
based_on_template_flow_id: UUID | None = Field(
    default=None,
    sa_column=Column(
        Uuid(),
        ForeignKey("flow.id", ondelete="SET NULL"),
        nullable=True,
    ),
    description=(
        "For flows cloned from a template via ADP Assist: the template "
        "flow's id, used to resolve TemplateMetadata for conversation context"
    ),
)
```

**When set:**
- The "Build with ADP Assist" path in `useAddFlow` passes both `built_with_assist: true` and the template's `flow.id` → `usePostAddFlow` body threads it → backend persists via `Flow.model_validate(flow, from_attributes=True)`.
- The `apply_template` tool sets it when the LLM applies a template to a blank flow.

**`ON DELETE SET NULL` rationale:** if a super admin deletes a template, user flows cloned from it should keep working — they just lose their template-context enrichment (the `flow_template_context` block becomes empty). `CASCADE` would orphan user work.

**Alembic migration:** single revision chained from `93e68a94275a` (Plan 3's head). Upgrade adds the column + FK + index; downgrade drops it.

### What's NOT changing

- `TemplateMetadata` — unchanged. Already keyed by `flow_id` which is the template's flow id.
- `built_with_assist` — stays a boolean; the new column adds the missing "which template" piece.
- Pydantic `FlowCreate` / `FlowRead` / `FlowUpdate` — auto-propagate via `FlowBase` inheritance.

## Section 2: Greet Endpoint

### HTTP surface

`POST /api/v1/assistant/flows/{flow_id}/greet`

- Request body: empty.
- Response: the newly-created `AssistantMessage` as JSON.
- Auth: same as `/messages` — `CurrentActiveUser` + org membership check.

### Handler behavior

Location: `src/backend/base/langflow/api/v1/assistant.py`, alongside the existing `/messages` handler. Steps:

1. Load or create `AssistantConversation` for `flow_id` (same helper as `/messages`).
2. **Idempotency guard.** If any `AssistantMessage` with `role = "assistant"` exists for this conversation, return `409 Conflict` with detail `"Conversation already greeted"`. Prevents double-greetings from tab races or accidental re-fires.
3. **Settings check.** Confirm provider / model / api_key are configured. If not, `400 Bad Request` with `settings_required: true` (shape matches the existing `/messages` settings-unconfigured path so frontend error handling is shared).
4. **Build the system prompt.** Same assembly as `/messages`, including the new `flow_template_context` block (see Section 4).
5. **Synthetic user turn.** Call the LLM with one message: `{role: "user", content: "__greet__"}`. This token is documented in the system prompt (guideline bullet) as a greeting trigger. The token is NOT persisted.
6. **Persist the response.** Create `AssistantMessage(conversation_id, role="assistant", content=<llm text>)`.
7. Return the persisted message as JSON.

### Why non-streaming

The greeting is one or two sentences, no tool calls. Regular JSON over an `await` costs ~1 second and skips the SSE plumbing. Reserving SSE for the real conversational path keeps the code paths cleanly separated.

### Error paths

- **LLM failure** (timeout, provider error): 500. Frontend shows a toast; user can type the first message manually to fall back to `/messages`. No stuck state — the guard in step 2 is based on stored messages, and no message was stored.
- **Tab race**: second tab sees 409; re-fetches conversation and renders the first tab's greeting.
- **No template + no context**: `flow_template_context` is empty; LLM generates a generic *"What would you like to build?"* from `available_templates`.

### Frontend integration

Existing `useAssistantConversation` hook gains a post-load step. After messages/settings hydrate:

```typescript
if (
  data?.conversation_id !== null &&
  (data?.messages ?? []).length === 0 &&
  useAssistantStore.getState().layoutMode === "fullscreen"
) {
  await greet(flowId);
  await reloadConversation(flowId);
}
```

The `greet` mutation comes from a new hook `useGreetConversation` under `controllers/API/queries/assistant/`. Panel-mode mounts deliberately skip this — keeps the sidebar assistant's existing silent-until-asked UX.

### Observability

On the backend, log (at debug level) whether `flow_template_context` was empty vs. populated for each greeting. Useful for confirming the linkage post-deploy.

## Section 3: System Prompt Additions

### `flow_template_context` placeholder

New placeholder in `SYSTEM_PROMPT_TEMPLATE` (in `service.py`), inserted between `{canvas_summary}` and `{available_templates}`:

```python
SYSTEM_PROMPT_TEMPLATE = """\
You are the Langflow Flow Builder Assistant.
...

## Current Canvas
{canvas_summary}

{flow_template_context}
{available_templates}
## Guidelines
...
"""
```

Built per message in `service.py`:

```python
async def build_flow_template_context(flow: Flow) -> str:
    if flow.based_on_template_flow_id is None:
        return ""
    notes = await fetch_template_usage_notes(str(flow.based_on_template_flow_id))
    if notes is None or notes["agent_usage_notes"] is None:
        return ""
    return (
        f"## Current Flow Template\n\n"
        f'This flow was created from the "{notes["flow_name"]}" template.\n'
        f"{notes['agent_usage_notes']}\n\n"
    )
```

Empty string when no template is linked — keeps the prompt clean for ordinary flows. `fetch_template_usage_notes` already exists (Plan 2, `services/assistant/tools/metadata_lookup.py`); no new lookup code.

### Four new `## Guidelines` bullets

Appended to the existing guidelines:

> - When the user's most recent message is exactly `__greet__`, you are opening the conversation. Do not treat it as a question. Respond with a short, friendly greeting appropriate to the Current Flow Template (if present) or invite the user to describe what they want to build (if no template is present). One or two sentences.
> - When adding components, make an opinionated choice and narrate it — e.g., "I've added a Slack node — which channel should it post to?" Do not ask "which component should I use?" unless the user's intent is genuinely ambiguous. Offer alternatives inline: "I'm using a Slack node; say 'use Discord' if you'd rather."
> - Frame configuration in the user's terms, not the product's. Ask "which Slack channel?" not "what's the value for the `channel_id` field on the SlackNotifier component?". Avoid referencing internal node ids, field names, or component class names in your messages unless the user asks for that level of detail.
> - When you believe the flow is fully assembled and configured, invite the user to test it by saying something like: "Your flow is ready — click the Test button in the header to run each component and check the connections." Do not trigger the mode switch yourself; the user clicks the header Test button.

### System-prompt test

`tests/unit/services/assistant/test_greeting_trigger_in_prompt.py`: assert the prompt contains the greeting-trigger bullet and the `__greet__` literal. Prevents accidental deletion.

## Section 4: `apply_template` Tool

### Tool declaration

New file: `src/backend/base/langflow/services/assistant/tools/template_apply.py`.

```python
"""Tool: apply_template — atomically load a template's nodes+edges into a flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.services.database.models import Flow
from langflow.services.database.models.flow.starter import is_flow_a_starter_project
from langflow.services.deps import session_scope


async def apply_template(
    target_flow_id: str,
    template_flow_id: str,
) -> dict[str, Any]:
    """Replace a flow's nodes/edges with a template's data. Also sets
    target.based_on_template_flow_id so subsequent messages pick up the
    template's usage notes in system-prompt context.

    Returns: {"applied_patch": {"added_nodes": [...], "added_edges": [...]},
              "template_name": str}
    Errors: {"error": "..."} when target is non-empty OR template isn't a
    starter project OR either flow can't be loaded.
    """
    # ...implementation in Plan 4 Task
```

### Registration

Appended to `CATALOG_TOOLS` in `registry.py`:

```python
{
    "name": "apply_template",
    "description": (
        "Load a starter-project template's nodes and edges into the current "
        "flow atomically. Use this after matching a template from the Available "
        "Templates list in the system prompt. Sets the current flow's template "
        "pointer so later messages carry the template's instructions. Returns "
        "the applied patch (added nodes and edges) and the template's name."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_flow_id": {
                "type": "string",
                "description": "UUID of the flow to apply the template to (typically the current flow).",
            },
            "template_flow_id": {
                "type": "string",
                "description": "UUID of the template flow (from the Available Templates list).",
            },
        },
        "required": ["target_flow_id", "template_flow_id"],
    },
},
```

Add the name → callable mapping in the same dispatch dict the assistant service uses for other catalog tools (`CATALOG_DISPATCH` in `service.py`).

### Behavior

1. Load `target_flow` by `target_flow_id`. If not found → `{"error": "Target flow not found"}`.
2. Load `template_flow` by `template_flow_id`. If not found → `{"error": "Template flow not found"}`.
3. Check `target_flow.organization_id == template_flow.organization_id` (or equivalent tenancy guard) → otherwise `{"error": "Template is not accessible from this flow"}`.
4. Validate that `template_flow` is a starter project via `is_flow_a_starter_project`. Otherwise → `{"error": "Flow is not a template"}`.
5. **Emptiness check.** If `target_flow.data.nodes` is non-empty → `{"error": "Target flow is not empty. Start from a blank flow to apply a template."}`. Prevents overwriting user work.
6. Deep-copy `template_flow.data`. Regenerate node and edge ids (reuse the existing backend id-regeneration helper if one exists — otherwise, simple "append random suffix" replacement across `data["nodes"][*].id` and `data["edges"][*]`: source+target references must be updated consistently).
7. Overwrite `target_flow.data`; set `target_flow.based_on_template_flow_id = template_flow_id`; commit.
8. Build a `flow_patch` payload equivalent to what `add_component` + `connect_edge` would have emitted for all nodes and edges in aggregate.
9. Emit the patch via the existing SSE `flow_patch` event (same mechanism `add_component` uses today).
10. Return `{"applied_patch": patch, "template_name": template_flow.name}`.

**No new SSE event type.** Reuses `flow_patch` with a large batch. Frontend already handles multi-node patches.

### Error dict pattern

Errors are returned as a `{"error": "..."}` dict rather than raised exceptions. Matches the pattern used by other tools. Lets the LLM see the error and adapt in conversation (e.g., "I can't apply that template to this flow — it already has components. Want me to add to what's there instead?").

## Section 5: Frontend Changes

### `useAddFlow` extension

In `src/frontend/src/hooks/flows/use-add-flow.ts`, when `params.flow` is provided AND `params.flow.folder_id` matches the starter-project folder, set `based_on_template_flow_id: params.flow.id` on the new flow object before posting. Pseudocode:

```typescript
const newFlow = {
  ...baseFlow,
  name: newName,
  folder_id: folder_id,
  built_with_assist:
    params?.built_with_assist ?? flow?.built_with_assist ?? false,
  based_on_template_flow_id:
    params?.flow?.folder_id === starterFolderId ? params.flow.id : null,
};
```

`starterFolderId` comes from the folders store (the folder named "Starter Projects"). If unavailable (the store hasn't loaded), default to null — the backend will persist null, which is fine.

### `usePostAddFlow` extension

Add `based_on_template_flow_id?: string | null` to `IPostAddFlow` and include it in the POST body. Same pattern as Plan 3's `built_with_assist` addition.

### `useGreetConversation` hook

New file `src/frontend/src/controllers/API/queries/assistant/use-greet-conversation.ts`. Small mutation wrapper around `POST /api/v1/assistant/flows/{flowId}/greet`. On success, invalidates the conversation query so the list re-hydrates.

### `useAssistantConversation` extension

Add the empty-plus-fullscreen trigger after conversation hydration. See Section 2 "Frontend integration" for the exact snippet.

### TS type update

`FlowType` in `src/frontend/src/types/flow/index.ts` gains `based_on_template_flow_id?: string | null;` — same shape as the existing `built_with_assist?: boolean`.

### No UI component changes

The greeting renders as a normal `AssistantMessage`; the message list already handles role=`"assistant"` messages. No new components, no layout changes. Plan 3's fullscreen shell is reused as-is.

## Section 6: Testing Strategy

### Backend unit tests

- `tests/unit/services/database/models/test_flow_based_on_template.py`
  - Column accepts UUIDs.
  - Column defaults to `None`.
  - `ON DELETE SET NULL`: deleting the template flow nulls the pointer on cloned flows (not cascade-deletes them).

- `tests/unit/api/v1/test_assistant_greet_endpoint.py`
  - Empty conversation + valid settings → greeting message persists, response returns it.
  - Already-greeted → 409.
  - Settings unconfigured → 400 with `settings_required: true`.
  - LLM failure → 500, no message persisted.
  - Conversation created on-demand when absent.

- `tests/unit/services/assistant/tools/test_apply_template.py`
  - Happy path: template applied, `based_on_template_flow_id` set, patch returned.
  - Non-empty target → error dict.
  - Non-starter template → error dict.
  - Unknown flow id → error dict.
  - Cross-tenant attempt → error dict.

- `tests/unit/services/assistant/test_flow_template_context.py`
  - Flow without pointer → empty string.
  - Flow with pointer + metadata → block includes flow name and `agent_usage_notes`.
  - Flow with pointer but no metadata row → empty string (graceful degradation).

- `tests/unit/services/assistant/test_greeting_trigger_in_prompt.py`
  - Assembled system prompt contains the `__greet__` bullet and the four new guideline bullets.

### Frontend unit tests (Jest)

- `modals/AssistantPanel/__tests__/greet-on-fullscreen.test.tsx`
  - Mount with `layoutMode="fullscreen"` + empty conversation → greet mutation fires once.
  - Mount with `layoutMode="panel"` + empty conversation → greet does NOT fire.
  - Mount with `layoutMode="fullscreen"` + existing messages → greet does NOT fire.
  - Greet fires only once even if the effect re-runs.

- `controllers/API/queries/assistant/__tests__/use-greet-conversation.test.ts`
  - POSTs to `/api/v1/assistant/flows/{flowId}/greet`, empty body.
  - Invalidates the conversation query on success.

### Fake-provider integration tests

Extend the existing `FakeClient` pattern:
- Assert the `__greet__` synthetic user message reaches the provider.
- Assert `flow_template_context` is present in the outbound system prompt when the flow has a template pointer.
- Assert `flow_template_context` is absent when the pointer is null.

### Manual verification checklist (before merging)

1. New flow via "Build with ADP Assist" from a template → fullscreen opens → greeting appears within 1–2 seconds referencing the template name.
2. Close + re-open fullscreen on the same flow → greeting is loaded from the DB, no second LLM call.
3. New flow via "Build with ADP Assist" from Blank Flow → greeting asks "What would you like to build?".
4. In a blank-flow conversation, say "I want a Slack notifier for new hires" → LLM matches the template, calls `apply_template`, flow populates, convo continues in template-aware mode.
5. Ask to add a specific component not proposed (e.g., "also add a Discord node") → LLM adds + narrates, never asks the user to pick a component type.
6. When the flow looks complete, the assistant invites clicking the Test button.
7. Delete a template flow → any user flow with `based_on_template_flow_id` pointing at it gets `NULL` (confirm via psycopg query); subsequent message responses no longer include the template block.

### Rollback

- Migration is reversible (`downgrade` drops the column).
- Greet endpoint is additive; panel-mode flows never hit it.
- `apply_template` tool can be disabled by removing the entry from `CATALOG_TOOLS`; no migration.
- System-prompt bullets are additive text — removing them is a code edit with no schema impact.

## Section 7: Out of Scope (Hard Boundaries)

- **Test mode itself** — Plan 5.
- **Component-level test-failure → credential-guidance conversation** — Plan 5 wires test SSE events into the assistant; this plan only seeds the prompt guidelines for non-technical framing.
- **Proactive greeting in panel mode** — deliberately gated to fullscreen.
- **Template application to a flow that already has nodes** — `apply_template` refuses. If the user wants to switch templates mid-build, they start over.
- **Multi-turn template-customization state machine** — guided entirely by prompt; no backend state beyond normal conversation history.
- **Assistant-driven mode switches** — the LLM asks the user to click the Test button; it does not emit an SSE event that flips `layoutMode`.
- **Template management UI / versioning / field-blanking** — Plan 7 candidate.
- **"Request Professional Services" proposals** — Plan 8 candidate.
- **MCP ext-apps integration** — Plan 6 candidate.

## Relationship to Other Specs

- **Depends on** Plan 2 (`2026-04-18-metadata-infrastructure-design.md`): `TemplateMetadata`, `fetch_template_usage_notes`, `get_template_instructions`, `available_templates` in system prompt.
- **Depends on** Plan 3 (`2026-04-18-assist-layout-and-entry-points.md`): fullscreen shell, `layoutMode` state, `built_with_assist` column, `openFlowInFullscreenAssist` entry helper.
- **Consumed by** Plan 5 (ADP Assist test mode): test-failure events will plug into the `## Guidelines` credential-handling bullet established here.
- **Supersedes** §4 and the template-matching parts of §7 in `2026-04-18-adp-assist-flow-builder-design.md`.

## Open Items Flagged During Implementation

- **Node-id regeneration helper.** The `apply_template` tool needs to regenerate node (and edge source/target) ids when cloning template data, so the cloned flow's nodes don't collide with the template's in the component catalog. Check whether `reactflowUtils.ts`'s frontend `updateIds` has a backend equivalent; if not, write a minimal helper in the tool file.
- **Starter-folder id resolution on the frontend.** `useAddFlow` needs the starter-project folder id to decide when to set `based_on_template_flow_id`. Confirm it's accessible from the folders store; fall back to `null` if not.
- **Greet endpoint timing.** Measure the p95 latency of the greet round-trip post-deploy. If it feels sluggish (> 3 seconds), consider an optimistic pre-rendered local greeting with a background LLM refresh.
