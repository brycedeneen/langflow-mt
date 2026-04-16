# Flow Builder Assistant — Design

**Date:** 2026-04-15
**Status:** Draft (awaiting user review)
**Branch:** platform-multi-tenant

## Background

Users today build flows by manually dragging components from a sidebar onto the canvas, wiring edges by hand, and configuring fields. This is fine for experts but slow and discoverable-only-by-clicking for everyone else. We want an in-app AI assistant that understands every Langflow component and can build, modify, and explain flows on the user's behalf.

The full vision spans five sub-projects. This spec covers the first three, which together form a vertically complete slice; the rest will be specced separately as they build on the same primitives.

## Scope

### In scope (this spec)

1. **Chat shell + LLM-bring-your-own-key.** A dockable side-panel co-pilot in the flow editor, configured per-org with the org's own provider/model/API key.
2. **Component knowledge layer.** An MCP server exposing read-only catalog tools (`search_components`, `get_component_schema`, `list_compatible_outputs`, `list_categories`) over the existing Langflow component registry.
3. **Single-component "add this to my flow."** In-process mutation tools (`add_component`, `connect_edge`, `set_field_value`, `remove_component`, `add_sticky_note`) the assistant can call to modify the currently-open flow.

Backed by:

- Per-org Assistant Settings (provider + key + default model) stored in the existing variables table.
- Per-flow conversation persistence shared across all org members with access to the flow.
- SSE streaming for the chat turn.
- Provider support: OpenAI and Anthropic.

### Out of scope (deferred to follow-up specs)

- **D — full-flow generation from a single prompt** (e.g. "build me a RAG over my Notion docs").
- **E — auto-generated TODO sticky and flow-explanation sticky.** The `add_sticky_note` *primitive* is in scope; the LLM-driven *generation* of those specific stickies is not.
- Per-user keys or per-user provider override.
- Real-time collaborative sync of conversation or canvas (last-writer-wins with refresh banner only).
- Diff-style preview of mutations (designed for via `flow_patch` event contract, not built).
- Providers beyond OpenAI / Anthropic.
- Conversation summarization (added later if windowing meaningfully cuts off relevant context).

## Success criteria

A user opens an existing flow, opens the assistant side panel, types "add an OpenAI LLM after my prompt template and connect them," and sees the node appear on the canvas wired correctly with sensible field values pre-populated. Closing and reopening the flow (as the same user or any colleague in the same org) shows the prior conversation intact.

## Architectural decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Where the LLM call happens | Backend proxy | Keys never touch the browser; multi-tenant–safe; reuses existing credential store; tool execution lives next to the graph. |
| Component knowledge transport | Split: MCP server for read-only catalog, in-process for mutations | Catalog is reusable by Claude Desktop / Cursor / external clients; mutations are inherently session-bound and need user/org/flow auth context. |
| UI placement | Dockable right-side panel ("co-pilot" pattern, like VS Code Copilot) | More natural than a floating bubble for long iterative work; shows canvas updates live as the assistant works. |
| Mutation UX | Just-do-it + undo, with structured `flow_patch` events | Ships fastest; designed so a future diff-review UX can be layered on by intercepting `flow_patch` instead of auto-applying. |
| Key scoping | Per-org only | Fits enterprise multi-tenant model; per-user complicates auth and billing without enterprise demand. |
| Provider list v1 | OpenAI + Anthropic | Both have first-class native tool-use APIs; avoids premature abstraction. |
| Conversation persistence | Per-flow, shared across org | The assistant is fundamentally scoped to "the flow you're editing"; sharing matches how org members collaborate on a flow asynchronously. |
| Concurrency on shared conversation | Last-writer-wins with stale banner; no real-time sync | Multi-user concurrent canvas editing isn't supported today; building real-time conversation sync ahead of canvas sync is wrong order. |
| Streaming transport | Server-Sent Events (SSE) | Simpler than a new WebSocket; fits the request/response shape; not conflated with the existing flow-execution chat WebSocket. |
| Context window strategy | Window the slice sent to LLM by token budget; storage unbounded | Don't truncate user-visible scrollback; preserve audit trail; only the LLM input is budgeted. |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (flow editor page)                                  │
│                                                              │
│   ┌────────────────────┐         ┌─────────────────────┐    │
│   │  ReactFlow canvas  │ ◄────── │  Assistant panel    │    │
│   │  (existing)        │  patch  │  (new, dockable)    │    │
│   └────────────────────┘  events └──────────┬──────────┘    │
│           ▲                                  │ SSE           │
│           │ store.applyAssistantPatch()      ▼               │
└───────────┼──────────────────────────────────┼──────────────┘
            │                                  │
            │ (existing flow PATCH endpoints)  │ /api/v1/assistant/* (NEW)
            │                                  │
┌───────────┼──────────────────────────────────┼──────────────┐
│  Langflow backend                            │              │
│                                              ▼              │
│   ┌────────────────────────────────────────────────────┐   │
│   │  AssistantService (NEW)                            │   │
│   │  - loads org Assistant Settings (provider+key)     │   │
│   │  - loads flow + conversation history               │   │
│   │  - runs tool-calling loop (OpenAI/Anthropic SDK)   │   │
│   │  - streams tokens + tool-events back over SSE      │   │
│   └─────────┬──────────────────────────────┬───────────┘   │
│             │                              │               │
│             │ MCP client (in-process)      │ direct calls  │
│             ▼                              ▼               │
│   ┌──────────────────────┐    ┌───────────────────────┐   │
│   │ Langflow Components  │    │ FlowMutationTools     │   │
│   │ MCP Server (NEW,     │    │ (NEW, in-process)     │   │
│   │ reuses mcp.py infra) │    │ - add_component       │   │
│   │ - search_components  │    │ - connect_edge        │   │
│   │ - get_component_     │    │ - set_field_value     │   │
│   │   schema             │    │ - remove_component    │   │
│   │ - list_compatible_   │    │ - add_sticky_note     │   │
│   │   outputs            │    │ scoped to (user, org, │   │
│   │ - list_categories    │    │  flow_id) per request │   │
│   └──────────────────────┘    └──────────┬────────────┘   │
│             │                              │               │
│             ▼                              ▼               │
│   ┌──────────────────────┐    ┌───────────────────────┐   │
│   │ Component registry   │    │ Flow service          │   │
│   │ (existing)           │    │ (existing, write API) │   │
│   └──────────────────────┘    └───────────────────────┘   │
│                                                            │
│   ┌────────────────────────────────────────────────────┐  │
│   │  Persistence (NEW tables):                         │  │
│   │  - assistant_conversation (flow_id, org_id)        │  │
│   │  - assistant_message (conversation_id, role,       │  │
│   │      content, tool_calls, tool_results, ts)        │  │
│   │  Org settings live in existing variables table.    │  │
│   └────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### Boundaries

- **MCP server** is a separate, pure, read-only surface. Reuses the existing `api/v1/mcp.py` / `mcp_projects.py` infrastructure. Reusable by external MCP clients (Claude Desktop, Cursor, third-party assistants).
- **Mutation tools** are in-process Python functions, called directly by `AssistantService` with the authenticated user/org/flow context already bound to the request. Returns structured "applied change" objects that the SSE stream forwards.
- **The assistant never writes to the DB-shaped flow representation directly.** All mutations go through the existing flow service so dirty-state, undo, and validation behave the same as manual user edits.

## Data model

### New tables (alembic migration)

```
assistant_conversation
  id              UUID PK
  flow_id         UUID FK → flow.id (UNIQUE — one conversation per flow)
  org_id          UUID FK → organization.id
  created_at      timestamp
  updated_at      timestamp

assistant_message
  id              UUID PK
  conversation_id UUID FK → assistant_conversation.id
  user_id         UUID FK → user.id  (NULL for assistant/tool messages)
  role            enum('user','assistant','tool')
  content         text          (assistant/user message text)
  tool_calls      jsonb NULL    (assistant turn's tool invocations, provider-native shape)
  tool_call_id    text NULL     (for role=tool, links to the call)
  tool_result     jsonb NULL    (for role=tool)
  created_at      timestamp
  index (conversation_id, created_at)
```

### Org Assistant Settings

Three rows in the existing `variable` table, scoped to the org:

- `assistant.provider` ∈ {`openai`, `anthropic`}
- `assistant.api_key` (encrypted, like other credential variables)
- `assistant.model` (e.g. `gpt-4o`, `claude-sonnet-4-6`)

No new settings table.

## API

All endpoints under `/api/v1/assistant`. All require the user be a member of the flow's org.

```
GET  /flows/{flow_id}/conversation
   → { conversation_id, messages: [...], settings_configured: bool }

POST /flows/{flow_id}/messages       (SSE stream)
     body: { content: string }
   → server-sent events:
       { type: "token", text: "..." }
       { type: "tool_call", id, name, args }
       { type: "tool_result", id, result }
       { type: "flow_patch", patch: { added_nodes, added_edges, updated_nodes, removed_ids } }
       { type: "message_complete", message_id }
       { type: "error", message }

DELETE /flows/{flow_id}/conversation
   → clears history. Allowed for any org member with access to the flow. Confirm dialog in UI.

GET  /settings        → { provider, model, has_key: bool }
PUT  /settings        → set provider/model/key (org-admin only)
```

### Auth & defense-in-depth

Mutation tool calls inside a turn re-verify the flow belongs to the user's org on every call. The LLM cannot smuggle a different `flow_id`; tools always use the request-bound `flow_id` from the endpoint, never one the LLM provides.

## Tool-calling loop

`AssistantService.send_message(flow_id, user_message)`:

1. Load org Assistant Settings → instantiate provider client (OpenAI or Anthropic SDK).
2. Build the message thread to send to the LLM:
   - **System prompt** (~1-2k tokens): role description + a *category index* (one line per component category, e.g. "LLMs: 18 components for chat models — search to discover specific ones") + a compact `current_canvas_summary` JSON of the flow's nodes (id, type, key fields) and edges. Canvas summary capped at ~3-5k tokens; summarized further for very large flows.
   - **Tool definitions** in the provider's native format. Catalog tools (from MCP) and mutation tools are presented as one flat tool list to the LLM.
   - **Conversation history**, windowed by token budget (see below).
   - The new user message.
3. Run the tool loop: send → receive (tokens stream as `token` events; tool calls as `tool_call` events) → execute tool calls (catalog → MCP client; mutation → in-process function) → emit `tool_result` and (if mutation) `flow_patch` events → feed results back to LLM → repeat until the model returns a final assistant message → emit `message_complete`.
4. Persist the assistant turn + tool calls + tool results to `assistant_message`.

### Context windowing strategy

- Per-model token budget = model's context window − reserved overhead (system prompt + tool defs + canvas summary + max output, roughly 12-20k reserved). Remainder is the conversation budget.
- Pack messages newest-first into the budget. Stop when the next message wouldn't fit.
- If the oldest in-budget message is `role=tool`, walk back to include its triggering `assistant` message. Don't break tool-call/result pairs.
- Storage is unbounded — the panel UI scrolls back through full history. Only the LLM input is windowed.
- No summarization in v1.

### Tool error handling

- **Catalog tool error** (MCP unreachable, bad component name) → return error JSON to the LLM, let it recover.
- **Mutation tool error** (invalid flow_id, edge incompatible types, component not found) → return structured error to the LLM AND emit a user-visible system message in the panel. The LLM can retry or apologize.
- **Provider error** (rate limit, auth) → emit `error` event, abort the turn, do not persist a partial assistant message.

### Mutation tool contract (example)

```python
add_component(component_type: str, position: {x,y} | "auto", initial_fields: dict | None) -> {
    node_id: str,
    applied_patch: { added_nodes: [...], added_edges: [] }
}

connect_edge(source_node_id: str, source_output: str, target_node_id: str, target_input: str) -> {
    edge_id: str,
    applied_patch: { added_edges: [...] }
}
```

Each tool returns the patch it applied. `AssistantService` forwards it as a `flow_patch` SSE event. This contract is what enables a future diff-review UX without changing the tool layer.

## Frontend integration

### New files (`src/frontend/src/`)

```
modals/AssistantPanel/
  index.tsx                    # dockable panel shell
  components/
    panel-header.tsx           # title + collapse + clear-conversation
    message-list.tsx           # scrollback (uses persisted history)
    message.tsx                # role-based rendering (user/assistant/tool)
    tool-call-card.tsx         # collapsed view of a tool invocation
    composer.tsx               # text input + send
    settings-required.tsx      # empty state when org has no key configured
  hooks/
    use-assistant-stream.ts    # opens SSE, dispatches events
    use-assistant-conversation.ts  # GET history on mount

pages/SettingsPage/AssistantSettings/
  index.tsx                    # provider/model dropdowns + key input (org-admin gated)

stores/
  assistantStore.ts            # panel open/closed, current conversation, streaming state
```

### Panel docking

A new collapsible right-side rail in the flow editor layout (sibling of the existing canvas). Default closed; opens to ~400px wide; drag-resizable; pin/unpin state persisted per-user in localStorage. Toggle button lives in the existing flow-editor toolbar.

### Stream → canvas wiring

- `use-assistant-stream` parses each SSE event.
- `flow_patch` events dispatch into the existing flow store via a new `applyAssistantPatch(patch)` action that internally calls the same node-add/edge-add mutations the user's manual interactions use. Undo stack works for free, dirty-state flags fire correctly, validation runs.
- After each `flow_patch`, the canvas auto-pans/zooms to fit the newly added nodes (existing `fitView` helper).
- `tool_call` and `tool_result` render inline in the message list as a collapsible card ("Used add_component → added OpenAI LLM"). Keeps the conversation legible while still showing what the assistant did.
- `error` events render as a system message bubble, not a toast — keeps history honest.

### Empty state

Panel opens, no settings configured → `settings-required.tsx` shows a "Configure the assistant" button. For org admins, links to the Assistant Settings page. For non-admins, shows "Ask an org admin to configure the assistant."

### Stale-history banner

- On panel open, GET conversation. Set `last_seen_message_id`.
- Every 30s while panel is open, poll `HEAD /conversation?since=last_seen_message_id`. If new messages exist, show a non-blocking banner: "New messages from <user> — refresh." Click → reload history. No real-time push.

### Scope discipline

No new global state crossing pages. Panel state lives in `assistantStore`, scoped to the editor. Closes when navigating away.

## Testing strategy

### Backend (`src/backend/tests/`)

- **MCP server tools** — pure unit tests against the component registry. Fast, no LLM, no DB.
- **FlowMutationTools** — integration tests against a real test DB and a real flow. Round-trip through the flow service; re-fetch and assert. Edge cases include invalid component type, incompatible edge types, non-existent node id, flow not in user's org (auth bypass attempt).
- **AssistantService tool loop** — record-replay tests with a fake provider client returning scripted tool-call sequences. Verifies tool dispatch routing, error recovery, message persistence, SSE event ordering. No network, no real LLM bills.
- **Context windowing** — unit tests on the packing function: given N synthetic messages and a budget, returns the right slice; never breaks tool-call/result pairs; reserves room for system+tools+output.
- **API endpoints** — FastAPI test client. Auth (non-org-member gets 403), settings CRUD (admin-only PUT), conversation GET/DELETE, SSE streaming smoke test.

### Frontend (`src/frontend/tests/`)

- **Stream parsing** — unit tests on `use-assistant-stream` consuming a recorded SSE byte stream and emitting expected store dispatches. Covers partial chunks, out-of-order tool events, error events.
- **Canvas patching** — component test: dispatch a `flow_patch` with `added_nodes` + `added_edges`, assert the flow store updates and undo restores prior state.
- **Panel rendering** — Storybook + RTL: empty state, settings-required state, mid-stream state (cursor + partial tokens), tool-call card, error message, stale banner.

### End-to-end (Playwright)

- **Golden path:** fixture flow with a prompt template, mocked assistant backend that scripts a fixed tool-call sequence, assert the new node appears on the canvas wired correctly, conversation persists across reload.
- **Failure path:** backend returns provider auth error → panel shows error message, no partial assistant message persisted.

### Deliberately not tested in v1

- Real LLM responses (flaky, expensive, non-deterministic). The fake provider client is the testing seam.
- Real multi-tenant key isolation under load — covered by org-scoping unit tests on the data layer; load testing is a separate concern.
- Token-budget calibration accuracy — we use the provider tokenizers and treat them as ground truth.

## Risks & open questions

- **Tool-call quality on small flows vs huge flows.** The canvas summary cap is a heuristic. We may need to evolve it (e.g. always include nodes adjacent to the user's selection, summarize the rest) once we see real behavior.
- **MCP latency overhead.** In-process MCP client calls should be sub-millisecond, but if we ever move the MCP server out-of-process for reuse, latency budget needs review.
- **Provider tool-call format drift.** OpenAI and Anthropic tool-call formats differ in subtle ways (parallel tool calls, content blocks, etc.). The `AssistantService` adapter layer needs careful per-provider tests.
- **Org admin gating.** This spec assumes the multi-tenant work in flight defines an "org admin" role. If that's not landed when implementation begins, we either block on it or temporarily gate Assistant Settings on a simpler check.

## Follow-up specs (not this spec)

- **D.** Full-flow generation from a single prompt.
- **E.** LLM-driven generation of TODO sticky and flow-explanation sticky notes.
- Per-user keys / per-user provider override.
- Real-time collaborative sync of conversation and canvas.
- Diff-review UX layered on `flow_patch` events.
- Additional providers (Google, Groq, Ollama, etc.).
- Conversation summarization for very long histories.
