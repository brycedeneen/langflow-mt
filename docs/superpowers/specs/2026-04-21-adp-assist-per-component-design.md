# ADP Assist · Per-Component Ephemeral Assistant

**Date:** 2026-04-21
**Status:** Draft

## Overview

An AI icon in every component node's toolbar opens a small, ephemeral chat popover scoped to configuring that single component. Distinct from the existing flow-level ADP Assist in three ways:

1. **Scope** — reads the target node plus its directly connected upstream/downstream neighbors; writes only to the target node's template.
2. **Lifetime** — conversation is in-memory only. Closing the popover discards the thread. No DB persistence, no session cache in v1.
3. **Tool surface** — one tool: `propose_config_update`. Proposals render inline in the chat as interactive blocks with Apply/Dismiss buttons. Apply is a purely client-side mutation using the existing flow-store update path.

The typical use case is natural-language configuration: a user describes intent in plain English, the assistant inspects the component schema (plus direct-neighbor schemas), and proposes field edits the user reviews and applies. The design is generic enough to support any component that opts in.

**Scope exclusion:** `DataMapperComponent` ships with its own dedicated agent and is explicitly excluded from ADP Assist. Components can opt out via a class attribute `assist_enabled: ClassVar[bool] = False` (default `True`). The Assist toolbar icon is suppressed on opted-out components and the backend rejects direct requests for them.

As part of shipping this feature, we populate starting `assist_guide` content for **every eligible user-facing component** (~400 classes across `src/backend/base/langflow/components/**` and `src/lfx/src/lfx/components/**`, minus opted-out classes like `DataMapperComponent`), auto-generated from each component's existing metadata (`display_name`, `description`, `documentation`, per-input `info` fields) and lightly reviewed. See Section 7.

## Section 1: Architecture

### High-level shape

```
Frontend                                Backend
─────────                               ───────
NodeToolbar "Assist" icon               POST /api/v1/assistant/components/messages
      │ click                                 │
      ▼                                       ▼
ComponentAssistPopover                  ComponentAssistService
  ├ componentAssistStore (zustand)           • Resolves component class + guide
  ├ useComponentAssistStream (SSE)           • Builds system prompt
  ├ Chat view (messages, bubbles)            • Calls LLM (inherits flow-assistant model)
  └ ProposalBlock (Apply / Dismiss)          • Streams deltas + propose_config_update
                                                tool calls via SSE
Apply: flowStore.updateNodeTemplate           • No DB writes, no session cache
```

### Key properties

- **Stateless backend.** Each turn the frontend sends the full thread plus the current node and neighbor snapshots. The backend holds nothing between requests. No `AssistantConversation`-style table. A server-side cache may be added later if input shows value; start without one.
- **SSE streaming.** Same transport as the flow-level assistant. Event types: `text-delta`, `tool-call`, `done`, `error`.
- **Single tool surface.** `propose_config_update(node_id, patch)` is the only tool. It does not apply the patch server-side — it streams the proposal to the client as a tool-call event; the client renders it as an interactive `ProposalBlock`. Apply happens via the existing client-side flow-store mutation (same code path as manual edits).
- **Component guide registry.** Guides are resolved in this order: (1) `assist_guide: ClassVar[str]` on the component class (co-located, highest priority — component authors editing a single component use this); (2) a curated bundle at `src/backend/base/langflow/services/component_assist/guides/*.yaml` keyed by component type (used for the bulk-populated starting guides); (3) fallback to a generic prompt. The backend injects the resolved guide into the system prompt when building the request for a node.
- **Opt-out contract.** A component may set `assist_enabled: ClassVar[bool] = False` to disable ADP Assist for itself (used by `DataMapperComponent`, which has its own bespoke agent). The frontend suppresses the Assist icon on the node toolbar when the component's `assist_enabled` is `False`, and the backend endpoint returns 400 if a request targets an opted-out component.
- **Multi-tenant inheritance.** Requests require `flow_id` for auth and pick up the same org/workspace scoping the flow-level assistant enforces. No new auth surface.
- **Model inheritance.** Uses whatever model the user has configured for the flow-level assistant. No separate setting in v1.
- **ADP red branding.** A new CSS variable `--color-adp-red: #ED1C2E` is introduced. Popover border, header gradient, Apply button, and brand-mark dot all reference it. This is distinct from `--destructive`, which is reserved for error states.

### Scope rules

- **Read:** the target node's full template/outputs, plus the template/outputs of each directly connected upstream and downstream node. No chain traversal. If the agent needs deeper context, it asks the user to paste or describe it.
- **Write:** only the target node's template field values. The agent cannot add/remove nodes, rewire edges, or change anything on neighbors.

### Concurrency

Only one component assist popover is open at a time. Opening a second popover closes the first. If the first popover's thread is non-empty, a confirm dialog is shown: *"Discard unsaved conversation?"* (matches the ephemeral contract — the user is explicitly throwing away the chat).

## Section 2: Backend

### New files

| Path | Responsibility |
|---|---|
| `src/backend/base/langflow/api/v1/component_assist.py` | FastAPI router: `POST /api/v1/assistant/components/messages` (SSE). Request/response schemas. |
| `src/backend/base/langflow/services/component_assist/service.py` | `ComponentAssistService`: build system prompt, drive LLM, stream SSE events. |
| `src/backend/base/langflow/services/component_assist/prompt.py` | Generic base system prompt; guide-injection helper. |
| `src/backend/base/langflow/services/component_assist/tools.py` | `propose_config_update` tool schema. Pydantic model for the patch shape. |
| `src/backend/base/langflow/services/component_assist/guide_registry.py` | Resolves a component's guide (class attr → YAML bundle → `None`); also exposes `is_assist_enabled(cls)` (True unless the class sets `assist_enabled: ClassVar[bool] = False`). |
| `src/backend/base/langflow/services/component_assist/guides/*.yaml` | Bundled starting guides. One or more YAML files keyed by component type. Generated by `scripts/generate_component_assist_guides.py` (see Section 7) and hand-reviewed. |
| `scripts/generate_component_assist_guides.py` | One-shot generator script. Walks the `components/` directories, extracts metadata per class, calls an LLM to synthesize a 1–2 paragraph guide, emits YAML. Idempotent and re-runnable. |

### Request schema

```python
class ComponentAssistRequest(BaseModel):
    flow_id: UUID
    node_id: str
    node_snapshot: NodeSnapshot          # target node's current data (template, outputs, type)
    neighbor_snapshots: list[NodeSnapshot]  # directly connected upstream + downstream
    thread: list[ThreadMessage]          # prior turns in this ephemeral session
    user_message: str
```

`NodeSnapshot` is a trimmed view of the node JSON — enough to reason about inputs/outputs and current values, but not styling/layout. `ThreadMessage` carries role (`user`/`assistant`), content text, and any prior tool calls (so the model sees proposals it has already made).

### Tool schema

```python
class ProposeConfigUpdate(BaseModel):
    """Propose a partial update to the target node's template field values."""
    node_id: str
    patch: dict[str, Any]  # field-name → new-value map
    rationale: str         # one or two sentences the user sees alongside the proposal
```

The service validates that `patch` keys exist on the target node's template before emitting the tool-call event. On validation failure, it retries once by sending the error back to the LLM. Second failure surfaces an `error` event to the client.

### Component-author contract

Any `Component` subclass can opt into specialized guidance:

```python
class TextOperationsComponent(Component):
    assist_guide: ClassVar[str] = """
    You help users configure text operations. Ask which operation they want
    (split, join, trim, replace), then which input fields feed it, then
    any operation-specific options. Prefer concrete suggestions over open-ended
    questions; the user can always reject and iterate.
    """
```

`guide_registry.py` reads the attribute via `getattr(cls, "assist_guide", None)`. No decorator, no registration call, no plugin discovery — if the class has the attribute, it's used. If absent, the registry falls back to the YAML bundle (Section 7); if that's also absent, the generic prompt is used.

## Section 3: Frontend

### New files

| Path | Responsibility |
|---|---|
| `src/frontend/src/modals/ComponentAssistPopover/index.tsx` | Popover container: drag handle, resize handle, close button, chat body, input, footer notice. |
| `src/frontend/src/modals/ComponentAssistPopover/hooks/use-component-assist-stream.ts` | POST request with `AbortController`; consume SSE; merge deltas into the active thread; materialize tool calls as `ProposalBlock` entries. |
| `src/frontend/src/modals/ComponentAssistPopover/components/ProposalBlock.tsx` | Renders a `propose_config_update` tool call as a diff-style card with Apply/Dismiss buttons. |
| `src/frontend/src/stores/componentAssistStore.ts` | Zustand store: `activeNodeId`, `anchorRect`, `position {x,y}`, `size {w,h}`, `thread[]`, `isStreaming`, open/close/abort actions. |

### Modified files

| Path | Change |
|---|---|
| `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx` | Add the Assist icon button wired to `componentAssistStore.open(nodeId, anchorRect)`. Button tint uses `--color-adp-red`. |
| `src/frontend/src/style/index.css` | Define `--color-adp-red: #ED1C2E`. |

### UI spec

- **Popover size:** 420 × 500px default; draggable by the header; resizable from the bottom-right corner; minimum 320 × 360px; maximum clamped to the viewport.
- **Header:** ADP brand dot (`--color-adp-red`), title `Assist · <ComponentDisplayName>`, `ephemeral` chip (italic, muted amber), close button.
- **Message area:** standard chat bubble layout. User bubbles right-aligned; assistant bubbles left-aligned. Streaming assistant text shows a three-dot "thinking" indicator ahead of the first delta.
- **ProposalBlock:** inline card within the thread using `--color-adp-red` accent border. Shows the patch as a field-by-field diff against current values. Two buttons: **Apply** (primary, ADP red) and **Dismiss** (secondary). After Apply, the block becomes read-only with an "Applied ✓" marker.
- **Input:** single-line growing textarea at the bottom. Placeholder: `Ask anything about this component…`
- **Footer notice:** small italic text below the input: *"This conversation won't be saved when you close."*
- **Empty state:** when the popover first opens, the assistant shows a greeting derived from the component's `assist_guide` (or a generic "Hi! I'll help configure this component. Paste a spec, describe rules, or ask me anything." if none is defined).

### Store shape

```ts
type ComponentAssistStore = {
  activeNodeId: string | null;
  anchorRect: DOMRect | null;
  position: { x: number; y: number };
  size: { w: number; h: number };
  thread: ThreadMessage[];
  isStreaming: boolean;
  open: (nodeId: string, anchorRect: DOMRect) => void;
  close: () => void;
  abort: () => void;  // aborts active request
  appendUserMessage: (text: string) => void;
  appendAssistantDelta: (delta: string) => void;
  appendProposal: (proposal: ProposalPayload) => void;
  markProposalApplied: (proposalId: string, skippedKeys: string[]) => void;
};
```

Open-while-another-is-open triggers a confirm dialog if `thread.length > 0`. Close wipes `thread`, `activeNodeId`, and aborts any streaming request.

## Section 4: Data Flow — One Turn

1. **Click icon.** `NodeToolbar` calls `componentAssistStore.open(nodeId, anchorRect)`. Popover mounts with position derived from the anchor rect (clamped into the viewport).
2. **Greeting.** Empty-state greeting is rendered from `assist_guide` or the generic fallback. No network call.
3. **User sends message.** `use-component-assist-stream`:
   - Pulls node and its direct neighbors from the existing flow zustand store.
   - Builds payload: `{ flow_id, node_id, node_snapshot, neighbor_snapshots, thread, user_message }`.
   - POSTs to `/api/v1/assistant/components/messages` with `AbortController`.
4. **Backend processes turn.** `ComponentAssistService`:
   - Looks up component class from `node_snapshot.type`.
   - Loads `assist_guide` via `guide_registry`.
   - Builds system prompt: base + (guide if present) + scope rules + neighbor schemas summary.
   - Calls LLM with the `propose_config_update` tool.
   - Streams `text-delta` events and any `tool-call` events; emits `done` at completion.
5. **Frontend merges.** Delta events append to the streaming assistant bubble. Tool-call events validate against the local template shape and materialize as `ProposalBlock` entries in the thread.
6. **User applies a proposal.** `ProposalBlock.onApply()` calls `flowStore.updateNodeTemplate(nodeId, patch)`. The block becomes read-only with "Applied ✓". If any keys were skipped (because the user edited the node after the proposal was generated), the block shows "Applied with N fields skipped — the component changed since this proposal was made."
7. **User closes popover.** `componentAssistStore.close()` aborts any active request and wipes the thread. Applied proposals remain on the node — they're flow state now. Unapplied proposals are gone.

## Section 5: Error Handling

| Scenario | Handling |
|---|---|
| Network drop mid-stream | SSE `onerror` → append a system message: *"Connection lost — your previous message wasn't completed. Try again."* Thread intact; user can retry without retyping. |
| Popover closed mid-stream | `AbortController.abort()` cancels the fetch; backend honors cancellation via FastAPI/anyio. |
| LLM refusal or provider error | Backend emits `error` SSE event with a safe message. Frontend renders it inline as a muted-red "assistant error" bubble (not ADP red — avoids conflating brand with failure). |
| Invalid `propose_config_update` patch | Pydantic validates tool args server-side. On failure, service retries once with an error message back to the LLM. Second failure → `error` event to client. |
| Apply fails on stale patch | `updateNodeTemplate` performs a shallow diff against current state, applies valid keys, returns the list of skipped keys. `ProposalBlock` renders "Applied with N fields skipped…" |
| Component class not found | Registry returns `None`; service falls back to generic prompt. Works fine — just less specialized. |
| Auth / flow scoping failure | 403 (wrong org) or 404 (missing flow) from the endpoint. Frontend shows inline error; user dismisses and popover closes. |

## Section 6: Testing

### Backend — `src/backend/tests/unit/services/component_assist/`

- `test_guide_registry.py` — class attribute present/absent/inherited; unknown component returns `None`.
- `test_service_prompt_building.py` — prompt contains guide when present, falls back to generic when absent; node + neighbor snapshots are interpolated correctly.
- `test_service_streaming.py` — mocked LLM yields deltas + a tool call; assert SSE event order (`text-delta`*, `tool-call`, `done`). Invalid tool-call args trigger one retry; second failure emits `error`.
- `test_component_assist_endpoint.py` — auth: other-org flow 403s; missing flow 404s; happy-path streams expected events.

### Frontend — `src/frontend/src/modals/ComponentAssistPopover/__tests__/` + store tests

- `componentAssistStore.test.ts` — open/close/abort; one-at-a-time behavior; confirm dialog when replacing a non-empty thread.
- `use-component-assist-stream.test.ts` — SSE parsing (Jest + mock EventSource), delta merging, tool-call materialization, abort on close.
- `ProposalBlock.test.tsx` — renders patch diff; Apply calls `flowStore.updateNodeTemplate`; Dismiss removes block; "Applied with N fields skipped" branch when the node has drifted.
- `ComponentAssistPopover.test.tsx` — renders greeting from guide when present, falls back when absent; drag updates `position`; resize updates `size`; close wipes thread.

### Integration smoke test

Fixture flow with one upstream source node and one generic target component that has `assist_enabled=True` (e.g., `TextOperationsComponent`). Open Assist on the target, send a configuration request, assert a `ProposalBlock` appears, click Apply, assert the target's template now reflects the proposed patch. Uses the existing backend test harness with a stubbed LLM response. A separate assertion confirms that a component with `assist_enabled=False` does NOT render the Assist icon.

## Section 7: Initial Component Guide Population

Ship this feature with starter guides for every existing user-facing component so ADP Assist is useful from day one, not just on the one or two components whose authors have written guides.

### Inventory

Based on a scan of the repo on 2026-04-21:

- `src/lfx/src/lfx/components/**` — ~397 user-facing component classes across 111 category directories (Composio 64, processing 33, langchain_utilities 28, vectorstores 20+, provider integrations 40+, etc.).
- `src/backend/base/langflow/components/**` — 4 minimal files (processing/converter, knowledge_bases skeleton).
- **Excluded:** `deactivated/` (24 files), files prefixed with `_` (internal/mixins/helpers, ~121 files), empty `__init__.py` files.

**Net:** roughly 400 components need starter guides.

### Existing metadata per component

Most components already carry rich metadata the generator can lean on:

- `display_name` (always present)
- `description` (almost always present)
- `documentation` URL (present on most integrations)
- Per-input `info=` strings describing purpose, constraints, and defaults (consistently populated)
- Return type hints on build methods (inform output schema)
- Class docstrings (sometimes)

This is enough to synthesize a usable 1–2 paragraph guide for 70–80% of components without human authoring.

### Generator approach

A one-shot script, `scripts/generate_component_assist_guides.py`, walks the two component roots and for each eligible class:

1. Imports the class and collects: `display_name`, `description`, `documentation`, class docstring, input list (name + type + `info`), output list (name + type).
2. Skips classes marked `legacy` or under `deactivated/`, and any class that already has `assist_guide` defined inline.
3. Builds a structured prompt and calls the LLM (same model as the flow assistant) asking for a 1–2 paragraph guide that covers: what the component does, its key inputs and when to adjust them, any notable constraints, and (where inferable) the typical upstream/downstream pairing.
4. Writes results to YAML files bundled under `src/backend/base/langflow/services/component_assist/guides/`, one file per top-level category directory (e.g., `openai.yaml`, `processing.yaml`, `vectorstores.yaml`).
5. Emits a review report listing components where existing metadata was thin (missing description, no input `info`, etc.) so humans can prioritize reinforcement.

The script is idempotent: re-runs pick up newly added components, skip those with an existing guide, and leave edited guides untouched unless a `--overwrite` flag is passed.

### YAML format

```yaml
# guides/processing.yaml
- type: TextOperationsComponent
  guide: |
    You help users configure text operations. Confirm which operation they want
    (split / join / trim / replace), which input field feeds it, and any
    operation-specific options. Propose concrete configurations rather than
    asking open-ended questions — the user can reject and iterate cheaply.

- type: SplitTextComponent
  guide: |
    ...
```

The registry loads all YAML files at startup, merges into a single `type → guide` dict, and caches for the process lifetime.

### Review workflow

1. Generator runs; emits ~30 YAML files (one per top-level category) and one `review-report.md`.
2. A first reviewer (likely the feature author) skims each YAML for obvious issues — hallucinated capabilities, generic non-guidance ("this component does what its description says"), outdated references.
3. Per-directory PRs sized by reviewability (one PR per 3–5 YAML files, ~30–50 guides each). Skip or rework any flagged by the review-report as thin-metadata risks.
4. Component owners can promote a guide onto the class (`assist_guide: ClassVar[str]`) at any time — the registry's class-attribute-first rule lets them own it without coordinating with the YAML bundle.

### Acceptance bar for v1

- Every non-excluded component has *some* entry in the bundle (generic fallback acceptable where metadata is too thin).
- At least one high-traffic component (e.g., `TextOperationsComponent` or an LLM/agent component) has a hand-authored `assist_guide` on its class to validate the class-attribute priority path. Choice of which component is left to the executor based on metadata completeness.
- `DataMapperComponent` is **excluded** from the bundle (it has its own bespoke agent).
- The review-report surfaces at most ~20% of components flagged for manual enrichment; those are tracked as a follow-up task, not a v1 blocker.

## Section 8: Out of Scope for v1

Deferred explicitly:

- **Server-side session cache** for truly-ephemeral conversations — start stateless; add only if input or metrics justify it.
- **Starter-prompt placeholders** driven by `assist_guide` (component-author-authored input-placeholder text).
- **"Edited by Assist" badge** on applied fields — decided against; no visual distinction between agent-applied and user-applied changes.
- **Multiple concurrent popovers** — one at a time in v1.
- **Component-registered custom tools** (beyond `propose_config_update`) — generic guide is enough to unlock the motivating use cases.
- **Chain traversal of node neighbors** — only direct neighbors; agent asks the user for deeper context if needed.
- **Moving the popover between monitors or persisting its position across sessions** — ephemeral position is fine; it re-anchors to the node each time.

## Section 9: Dependencies

- `DataMapperComponent` is **out of scope** and must not be affected by this work — it has its own bespoke agent (see project memory `project_data_mapper_dedicated_agent.md`). ADP Assist is opted out on DataMapper via `assist_enabled: ClassVar[bool] = False`.
- Inherits the existing flow-level assistant's LLM client, SSE streaming primitives, and auth guards.
- Inherits the existing flow zustand store's `setNode` mutation — no new store write path is introduced.
