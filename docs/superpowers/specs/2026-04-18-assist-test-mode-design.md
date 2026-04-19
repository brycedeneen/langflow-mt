# ADP Assist Test Mode

**Date:** 2026-04-18
**Status:** Draft

## Overview

Plan 5 of the ADP Assist roadmap. The fullscreen test shell (placeholder since Plan 3) becomes a working test experience: a `FlowPipelineView` on the left renders the current flow as a simplified DAG with per-component test status; the assistant chat on the right lets the user ask for help on failures. Clicks on a card build everything upstream-plus-that-node via the existing `/api/v1/build/{flow_id}/flow` endpoint with `stop_component_id` bounds. Test status and results flow through existing SSE events (`end_vertex`, `error`) and the existing `flowStore` state (`flowBuildStatus`, `flowPool`) — no new backend endpoints, SSE event types, or DB columns.

Realizes §5 and the test-execution portion of §7 from `2026-04-18-adp-assist-flow-builder-design.md`. Credential-walkthrough UX (§4 last paragraph) plugs in via a new system-prompt guideline bullet plus an "Ask assistant" button on failed cards.

This spec does NOT implement:
- Template management / versioning / field blanking — Plan 7 candidate.
- MCP ext-apps integration — Plan 6 candidate.
- "Request Professional Services" intake — Plan 8 candidate.
- Proactive narration on test failure — deliberately out of scope; user always clicks to ask.

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Single-node test semantics | **`stop_component_id = clickedNodeId` against existing `POST /api/v1/build/{flow_id}/flow` endpoint — builds everything upstream + the clicked node.** | Matches user mental model of "prove this node works." Fresh-flow friendly (no "needs upstream built first" failures). No new endpoint; the deprecated `/vertices/{vertex_id}` route is avoided. |
| Assistant narration of failures | **Click-to-ask: failed cards show an `[Ask assistant]` button; clicking POSTs a structured `[TEST_FAILURE]` user message into the conversation.** | Respects rapid-iteration workflows; doesn't drown the chat. The spec's "walks the user through it conversationally" language is about what the assistant *does* when prompted — the trigger mechanism is a design choice. |
| Pipeline view scope | **Full spec per §5: topological DAG layout, tool grouping, parallel branches, per-card chrome.** | Test mode's value hinges on being visually scannable; the view isn't optional polish. |
| Plan scope | **Single plan, ~18 tasks.** | Plumbing and view are useless without each other; splitting creates a "half-working test mode" intermediate state. |
| New backend work | **None.** | Existing build API + SSE events + `flowPool` / `flowBuildStatus` already cover the data path. |

## Architecture

```
┌──────────────────── Fullscreen Test Mode ─────────────────────┐
│ [ADP Assist — Test]    Back to chat    View Canvas    Close   │
├───────────────────────────────────┬───────────────────────────┤
│ FlowPipelineView                  │ Assistant chat            │
│  (reads flowBuildStatus/flowPool) │                           │
│                                   │                           │
│  ┌─────────────┐                  │                           │
│  │ Webhook     │ ✅               │                           │
│  └──────┬──────┘                  │                           │
│         │                         │                           │
│  ┌──────▼──────┐                  │  User clicks Ask assist   │
│  │ Agent       │ ❌ failed        │  ────────────────────▶    │
│  │  └─ Tool X  │ [Ask assistant]  │  [TEST_FAILURE] Slack…   │
│  │  └─ Tool Y  │                  │                           │
│  └──────┬──────┘                  │  (Asst replies            │
│         │                         │   conversationally        │
│  ┌──────▼──────┐                  │   with fix guidance)      │
│  │ Slack       │ ⚪ not tested   │                           │
│  └─────────────┘                  │                           │
│                                   │                           │
│  [Test All]                       │                           │
└───────────────────────────────────┴───────────────────────────┘

Data flow:
  [click Test/Test All]
      │
      ▼
  runTestForComponent(nodeId)
   or runTestForAll()
      │
      ▼
  buildFlowVerticesWithFallback({ stopNodeId?, onBuild* callbacks })
   └─ POST /api/v1/build/{flow_id}/flow?stop_component_id=nodeId
       ?event_delivery=streaming
      │
      ▼
  Backend queues job; events stream back via the build endpoint's
  SSE response (or a GET /api/v1/build/{job_id}/events fallback):
    vertices_sorted → build_start → [end_vertex]* → end
      │
      ▼
  test-runs.ts's onBuildStart / onBuildUpdate / onBuildError callbacks
   call updateBuildStatus and addDataToFlowPool
   → flowStore.flowBuildStatus[nodeId]
   → flowStore.flowPool[nodeId]
      │
      ▼
  FlowPipelineView re-renders on store change:
   - status badge per card
   - grouped tool sub-items
   - error summary on failed cards
   - raw output (expand-on-click)

Failure path:
  user clicks [Ask assistant] on a failed card
      │
      ▼
  sendAssistantMessage(flowId,
    "[TEST_FAILURE] Component `Slack` (Slack) failed.
     Error: invalid_auth
     Walk me through how to fix this.")
      │
      ▼
  Existing POST /api/v1/assistant/flows/{id}/messages SSE path
      │
      ▼
  LLM sees [TEST_FAILURE] prefix; new prompt
  guideline tells it how to respond
  (credential walkthrough branch if relevant)
```

## Section 1: Data Model — Reuse Only

No new DB columns, no migrations, no Pydantic additions, no new SSE event types.

### Frontend state (reused from existing stores)

- `flowStore.flowBuildStatus: Record<nodeId, { status: BuildStatus; timestamp?: string }>` — `BuildStatus` values `TO_BUILD | BUILDING | BUILT | ERROR | INACTIVE`. Updated by the existing `flowStore.buildFlow` action's `onBuildStart` / `onBuildUpdate` / `onBuildError` callbacks as the build's event stream arrives.
- `flowStore.flowPool: Record<nodeId, VertexBuildTypeAPI[]>` — per-vertex build history. The latest entry for each node carries output data, error message, and timing. Written by the same `buildFlow` callbacks.
- `assistantStore.selectedTestComponent: string | null` — added in Plan 3, unused until now. Plan 5 writes the clicked node's id here on each single-component test trigger (Test All leaves it null).

### New derived accessors on `flowStore`

Two small selectors — keep as derived accessors to avoid duplicated state:

```ts
getTestStatusForNode: (nodeId: string) => "not_tested" | "testing" | "passed" | "failed";
getLatestTestResultForNode: (nodeId: string) => VertexBuildTypeAPI | null;
```

Mapping:
- `TO_BUILD` / `INACTIVE` / absent → `"not_tested"`
- `BUILDING` → `"testing"`
- `BUILT` → `"passed"`
- `ERROR` → `"failed"`

That's the entire data model change.

## Section 2: Backend Integration — Zero New Code

Plan 5 calls the existing backend; it writes no new endpoint, SSE type, or handler. It also writes no new SSE handling on the frontend — the existing `flowStore.buildFlow` action already consumes the build event stream and updates `flowBuildStatus` / `flowPool`.

### New frontend utility: `test-runs.ts`

`src/frontend/src/utils/test-runs.ts` calls `buildFlowVerticesWithFallback` directly rather than `flowStore.buildFlow`. Reason: `buildFlow` resets `flowBuildStatus = {}` at start, which would erase prior per-card status on every single-node test. The wrapper wires minimal callbacks that call `updateBuildStatus` / `addDataToFlowPool` for only the nodes the event stream touches.

```ts
import { BuildStatus } from "@/constants/enums";
import { EventDeliveryType } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { buildFlowVerticesWithFallback } from "@/utils/buildUtils";

async function runBuild(stopNodeId?: string): Promise<void> {
  const flowId = useFlowsManagerStore.getState().currentFlow?.id;
  if (!flowId) return;
  await buildFlowVerticesWithFallback({
    flowId,
    stopNodeId: stopNodeId ?? null,
    eventDelivery: EventDeliveryType.STREAMING,
    onBuildStart: (elementList) => {
      const ids = elementList.map((e) => e.id);
      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.BUILDING);
    },
    onBuildUpdate: (vertexBuildData, status, runId) => {
      useFlowStore.getState().addDataToFlowPool(
        { ...vertexBuildData, run_id: runId },
        vertexBuildData.id,
      );
      useFlowStore.getState().updateBuildStatus([vertexBuildData.id], status);
    },
    onBuildComplete: () => {},
    onBuildError: (title, list, elementList) => {
      const ids = (elementList?.map((e) => e.id).filter(Boolean) as string[]) ?? [];
      if (ids.length > 0) {
        useFlowStore.getState().updateBuildStatus(ids, BuildStatus.ERROR);
      }
      useAlertStore.getState().addNotificationToHistory({ title, type: "error", list });
    },
  });
}

export async function runTestForComponent(nodeId: string): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(nodeId);
  await runBuild(nodeId);
}

export async function runTestForAll(): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(null);
  await runBuild();
}
```

Neither helper subscribes to SSE directly; `buildFlowVerticesWithFallback` owns the event stream and invokes the callbacks.

### Existing build-event pipeline (unchanged)

- Transport: `buildFlowVerticesWithFallback` in `src/frontend/src/utils/buildUtils.ts` POSTs to `/api/v1/build/{flow_id}/flow` with `stop_component_id` as a **query parameter** (not a body field). Events arrive either as an inline SSE response (`event_delivery=DIRECT`) or via a follow-up GET to `/api/v1/build/{job_id}/events`.
- Event → store wiring: `flowStore.buildFlow` passes `onBuildStart`, `onBuildUpdate`, `onBuildComplete`, `onBuildError` callbacks that already call `updateBuildStatus`, `addDataToFlowPool`, `setBuildInfo`. Plan 5 adds zero new SSE handling.
- Note: `useWebhookEvents` is unrelated to this pipeline. It subscribes to `/api/v1/webhook-events/{flowId}` only when the flow contains a Webhook component, and listens for events emitted by *external* webhook invocations — not user-triggered builds.

### Concurrency

- **Single test click:** `buildFlowVerticesWithFallback` streams events; callbacks write to flowStore; awaited promise resolves on completion.
- **Rapid clicks or Test All while a single test is running:** both calls run in parallel. `updateBuildStatus` / `addDataToFlowPool` are idempotent per vertex, so out-of-order events settle to last-writer-wins — acceptable for v1. If rapid-clicking becomes a real workflow, add a client-side debounce and a Stop button.
- **Status-badge conflicts:** because this helper never resets `flowBuildStatus`, a node's last-known status persists across other-branch test runs until that node itself is retested.

### Error payload

The `end_vertex` event already emits `{ build_data: { id, valid, data: ResultDataResponse } }`. When `valid: false`, `data` carries the error details. `flowStore.addDataToFlowPool` stores each entry; the pipeline view reads the latest `flowPool[nodeId]` entry for the error message. The `[View full output →]` expander shows the full `ResultDataResponse` as a collapsible `<pre>` block.

## Section 3: Pipeline View — Layout Algorithm, Cards, Interactions

### File structure

New directory: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/`

```
FlowPipelineView/
├── index.tsx               — main view container; reads flowStore, renders layout
├── dag-layout.ts           — pure function: (nodes, edges) → LayoutModel
├── pipeline-card.tsx       — single node card (header + status + actions + grouped sub-items)
├── status-badge.tsx        — colored status icon
├── raw-output.tsx          — expandable <pre> block for full output
├── test-all-button.tsx     — top-level "Test All" button
└── __tests__/
    └── dag-layout.test.ts  — unit tests for the layout algorithm
```

### DAG layout algorithm — three passes

`dag-layout.ts` exports one pure function. Fully unit-testable; no React deps.

**Pass 1 — topological sort + level assignment.** Standard Kahn's algorithm over `(nodes, edges)`. Each node gets a `level` equal to the max distance from any root (a root is a node with no incoming edges).

**Pass 2 — detect groupable "tool" nodes.** A node `X` is grouped into a parent `P` when:
1. `X` has exactly one outgoing edge (to `P`).
2. `X` has no incoming edges (it's a leaf on the input side).
3. `P`'s category is in a curated `TOOL_PARENT_CATEGORIES` set — starts as `["agent", "llm", "orchestrator"]`. Conservative, expand as patterns emerge.

Grouped nodes don't render as their own cards. They appear as sub-items inside the parent card.

**Pass 3 — parallel siblings.** Nodes at the same `level` whose direct downstream targets overlap are considered parallel and laid out side-by-side (horizontal row) within that level's container. Non-parallel nodes at a given level just flow top-to-bottom.

Return shape:

```ts
type LayoutModel = {
  levels: Array<{
    level: number;
    cards: Array<{
      node: FlowNode;
      groupedChildren: FlowNode[];
      parallelSiblings: string[];  // ids of nodes in same level with same downstream target
    }>;
  }>;
  edgesBetweenLevels: Array<{ sourceLevel: number; targetLevel: number }>;
};
```

### Card visual — `pipeline-card.tsx`

```
┌──────────────────────────────────────────────┐
│ [icon] Agent Orchestrator        [● failed] │
│ ├─ Tool: Slack Lookup                       │
│ ├─ Tool: ADP Worker Lookup                  │
│ └─ Tool: Calendar                           │
│                                              │
│ Slack API returned invalid_auth (401)       │
│                                              │
│ [↻ Re-test]  [Ask assistant]  [View full…]  │
└──────────────────────────────────────────────┘
```

Header: icon + `data.display_name || node.data.type` on the left, `<StatusBadge>` on the right. Grouped children render as an indented bulleted list under the header. Error summary (one-line truncated) appears only when status is `failed`. Footer buttons depend on status:

- `not_tested`: `[▶ Test]` (primary, filled)
- `testing`: `[Spinner]` (disabled)
- `passed`: `[↻ Re-test]` (outline) + `[View full output →]` (ghost)
- `failed`: `[↻ Re-test]` (outline) + `[Ask assistant]` (primary, destructive accent) + `[View full output →]` (ghost)

Click `[Test]` / `[Re-test]`: calls `runTestForComponent(node.id)` (which writes `assistantStore.selectedTestComponent` internally). Badge flips to `testing` as soon as the `build_start` event arrives and `updateBuildStatus([id], BuildStatus.BUILDING)` fires.

`[View full output →]` toggles `<RawOutput>`, which renders the latest `flowPool[nodeId]` result as a collapsible `<pre>` — JSON if the existing project has a JSON syntax highlighter helper, plain `<pre>` otherwise.

`[Ask assistant]` — see Section 4.

### Status badge — `status-badge.tsx`

Small component, one of four visual states:
- `not_tested` — gray dot, label `"Not tested"`
- `testing` — amber spinner, label `"Testing…"`
- `passed` — green check, label `"Passed"`
- `failed` — red X, label = first line of `flowPool[nodeId]`'s latest error

### Test All — `test-all-button.tsx`

Top-right of the `FlowPipelineView`. Primary button. Calls `runTestForAll(flowId)`. Disabled while any per-node test is in `testing` state (prevents confusion from overlapping SSE streams). When clicked, SSE events naturally populate every node's status as the full flow builds.

### Integration into `test-shell.tsx`

Plan 3's `test-shell.tsx` has a placeholder centered on the left pane:

```tsx
<div className="flex w-1/2 flex-col items-center justify-center border-r text-muted-foreground">
  <ForwardedIconComponent name="GitBranch" className="mb-2 h-8 w-8 opacity-50" />
  <div className="text-sm">Pipeline view will appear here (Plan 5).</div>
</div>
```

Plan 5 replaces that whole div with:

```tsx
<div className="flex w-1/2 flex-col border-r overflow-auto">
  <FlowPipelineView flowId={flowId} />
</div>
```

Everything else in `test-shell.tsx` — header, chat on the right, mode-switch buttons — is untouched.

### Edge cases

- **Empty flow (zero nodes):** pipeline view renders `"No components yet. Go back to chat and add some."` + `[Back to chat]` button that sets `layoutMode: "fullscreen"`.
- **Disconnected subgraphs:** layout algorithm treats each as its own sub-DAG; renders them stacked vertically with a subtle divider.
- **Cycles in the flow** (shouldn't happen in Langflow but defensive): layout algorithm detects and falls back to a linear list in arbitrary order; logs a warning.
- **Tool grouping with ambiguous parents:** if `TOOL_PARENT_CATEGORIES` matches multiple parents a node could belong to, keep the node ungrouped (render as its own card). Explicit > ambiguous.

### Testing

- `dag-layout.test.ts`: empty graph, single node, linear chain, diamond (parallel branches), agent-with-tools grouping, cycle fallback, disconnected subgraphs.
- Jest component test for `pipeline-card.tsx`: status-dependent button rendering, Ask-assistant onClick, raw-output toggle.
- Integration Jest test for `FlowPipelineView`: mocked `flowStore` state with a small DAG, asserts cards render with correct badges, clicking `[Test]` calls the mocked `runTestForComponent`.

## Section 4: Assistant Narration — Click-to-Ask

### `[Ask assistant]` click handler

In `pipeline-card.tsx`:

```ts
const handleAskAssistant = useCallback(async () => {
  const result = flowPool[node.id]?.slice(-1)[0];
  const errorMsg = result?.data?.error ?? "Unknown error";
  const outputSummary = result?.data?.message ?? "";

  const message =
    `[TEST_FAILURE] Component \`${node.data.display_name || node.id}\` ` +
    `(${node.data.type}) failed.\n` +
    `Error: ${errorMsg}\n` +
    (outputSummary ? `Last output: ${outputSummary}\n` : "") +
    `Walk me through how to fix this.`;

  await sendAssistantMessage(flowId, message);
}, [node, flowPool, flowId]);
```

`sendAssistantMessage(flowId, content)` is a thin wrapper around the existing `useAssistantStream` sendMessage helper. No new endpoint, no new SSE event type, no new state. The response streams into the chat pane on the right.

The `[TEST_FAILURE]` prefix is a sentinel (parallel to `__greet__` from Plan 4). The LLM recognizes it via a new system-prompt guideline.

### New system-prompt guideline bullet

Appended to the existing `## Guidelines` in `SYSTEM_PROMPT_TEMPLATE`:

> - When the user's most recent message starts with `[TEST_FAILURE]`, they clicked "Ask assistant" on a failed component test. Parse the component name, type, and error from the message. Respond conversationally with: (1) what likely went wrong in plain language, (2) concrete steps to fix it. If the error mentions `credential`, `auth`, `api_key`, `token`, `invalid_auth`, `401`, or `403`, prioritize a credentials walkthrough — explain where the user obtains the missing credential (e.g., "You'll need a Slack API token. Here's how to get one: go to api.slack.com/apps, create a new app…"), then where to put it in Langflow. Keep the response focused on fixing this one failure; do not propose redesigning the flow unless asked.

Unit test (pattern from Plan 4): `test_test_failure_guideline_in_prompt.py` asserts the bullet and the keyword list are present in `SYSTEM_PROMPT_TEMPLATE`.

### What's explicitly NOT in scope

- **No proactive narration on failure.** User always clicks to ask.
- **No backend-side credential-error detection.** The LLM pattern-matches in its prompt logic.
- **No tagged error shape.** We stuff raw strings into the user message; LLM handles them.
- **No UI indicator for "assistant narrated this failure."** Chat history is the source of truth.

## Section 5: Testing Strategy

### Backend unit tests

- `tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py` — asserts the new prompt bullet and credential-keyword list are present.

### Frontend unit + integration tests

- `dag-layout.test.ts` — pure-function tests for the layout algorithm (7 cases minimum; see Section 3).
- `pipeline-card.test.tsx` — status-dependent button rendering, Ask-assistant onClick, raw-output toggle.
- `FlowPipelineView.test.tsx` — integration with mocked flowStore, asserts cards render, Test All button behavior.
- `test-shell.test.tsx` (existing from Plan 3) — update the snapshot to reference `FlowPipelineView` instead of the placeholder.

### Manual verification checklist (before merge)

1. Open a flow in fullscreen ADP Assist, switch to Test mode, confirm `FlowPipelineView` renders with all nodes as cards and correct execution order.
2. Click Test on the root node — badge goes `testing → passed` within a few seconds; `View full output →` shows the node's output data.
3. Click Test on a middle node — upstream nodes also run (confirm via badges); middle node ends `passed`.
4. Set an invalid API key on a component that needs one, click Test on that component, confirm the card goes `failed` with a short error, and an `[Ask assistant]` button appears.
5. Click `[Ask assistant]`; confirm a `[TEST_FAILURE]` message appears in chat and the assistant responds with credentials-walkthrough guidance per the new system-prompt bullet.
6. Click Test All — confirm every card's badge updates as the full flow builds.
7. Verify tool-grouping: on a flow with an agent-with-tools shape, confirm tool nodes appear as indented sub-items under the agent card (not as separate cards).
8. Verify parallel layout: on a flow with a diamond shape, confirm the parallel pair render side-by-side within their level container.
9. Verify the expand-raw-output toggle works on both passed and failed cards.
10. Open an empty flow (zero nodes) in test mode; confirm the "no components yet" empty state.

### Rollback

- All changes are frontend-only. Removing the `FlowPipelineView` directory + reverting `test-shell.tsx`'s one-line JSX change + removing the system-prompt bullet reverts Plan 5 entirely.
- No DB migration; no schema changes.
- `test-runs.ts` helpers are additive; removing them doesn't affect anything else.

## Section 6: Out of Scope (Hard Boundaries)

- **Proactive assistant narration on failure** — user always clicks to ask.
- **Server-side credential-error classification** — LLM pattern-matches in its prompt.
- **Per-user / per-org test history** — `flowPool` stores in-memory build history; no persisted test log.
- **Offline / queued test runs** — tests require an active SSE connection.
- **Stop / cancel in-flight tests** — once the build job starts on the backend, there's no cancel path. User waits for it to finish.
- **New Mutation tools for the assistant** — no new tools; the assistant can only respond to `[TEST_FAILURE]` messages from the user.
- **Cross-flow test aggregation** — pipeline view is scoped to the current flow's DAG.
- **Time-series visualizations of past tests** — just latest status + latest output per node.
- **Template management / versioning / field blanking** — Plan 7 candidate.
- **MCP ext-apps rich UI widgets** — Plan 6 candidate.
- **"Request Professional Services" feature** — Plan 8 candidate.

## Relationship to Other Specs

- **Depends on** `2026-04-18-assist-layout-and-entry-points-design.md` (Plan 3): fullscreen + test shell, `layoutMode: "test"`, `selectedTestComponent` state.
- **Depends on** `2026-04-18-assist-fullscreen-experience-design.md` (Plan 4): the assistant conversation the test mode inserts `[TEST_FAILURE]` messages into, the system prompt template that gains the new guideline.
- **Depends on** pre-Plan-ADP infrastructure: `flowStore.buildFlow` action → `buildFlowVerticesWithFallback` → `POST /api/v1/build/{flow_id}/flow` + `vertices_sorted` / `end_vertex` / `error` build events, `flowStore.flowBuildStatus`, `flowStore.flowPool`.
- **Supersedes** §5 and the test-execution portion of §7 in `2026-04-18-adp-assist-flow-builder-design.md`.

## Open Items Flagged During Implementation

- **`TOOL_PARENT_CATEGORIES` ruleset.** Starts as `["agent", "llm", "orchestrator"]`. May prove too narrow or too broad once real flows are tested. Revisit if manual verification (Task 7 above) shows flows where grouping obviously should or shouldn't apply.
- **Parallel-branch layout beyond 3 cards at a level.** If a flow has 5+ parallel paths, horizontal side-by-side gets visually cramped. Acceptable fallback: wrap to a new row. Worst case: keep cards flowing vertically and skip the parallel-layout bit. Decide once we have real data.
- **Raw output rendering.** If Langflow has an existing JSON syntax-highlighter utility, use it; otherwise plain `<pre>`. Not a blocker.
- **`sendAssistantMessage` wrapper shape.** The existing `useAssistantStream` sendMessage function lives on the hook; `pipeline-card.tsx` needs access to it. Either pass it down via prop from the parent `FlowPipelineView`, or refactor to a shared hook. Pick the less invasive path during implementation.
