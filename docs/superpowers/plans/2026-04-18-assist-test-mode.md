# ADP Assist Test Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Plan 3's test-shell placeholder with a working `FlowPipelineView` (DAG of per-component test cards) that triggers upstream-bounded flow builds via the existing `/api/v1/build/{flow_id}/flow` endpoint, plus a click-to-ask "Ask assistant" path that walks users through test failures via a new system-prompt guideline.

**Architecture:** Frontend-only except for one backend prompt bullet + its test. Test mode calls `buildFlowVerticesWithFallback` directly (not `flowStore.buildFlow`, which resets `flowBuildStatus`). A pure `dag-layout.ts` function transforms `(nodes, edges)` into a leveled layout with tool grouping. PipelineCard derives its status from `flowStore.flowBuildStatus[nodeId]` and reads latest results from `flowStore.flowPool[nodeId]`. `[Ask assistant]` on a failed card calls the same `onSend` prop already plumbed through `TestShell` for the composer.

**Tech Stack:** React + TypeScript + Zustand (frontend); Python + pytest (backend). Jest for frontend tests. `ForwardedIconComponent` from `@/components/common/genericIconComponent` for icons.

---

## File Structure

**Created (frontend):**
- `src/frontend/src/utils/test-runs.ts` — `runTestForComponent(nodeId)` / `runTestForAll()` helpers.
- `src/frontend/src/utils/__tests__/test-runs.test.ts` — smoke test for the above.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/index.tsx` — container; reads stores + renders layout.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/dag-layout.ts` — pure layout function.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx` — single card.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/status-badge.tsx` — colored status.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/raw-output.tsx` — expandable output.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/test-all-button.tsx` — top-level button.
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx`

**Created (backend):**
- `src/backend/tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py`

**Modified:**
- `src/backend/base/langflow/services/assistant/service.py` — append one bullet to `SYSTEM_PROMPT_TEMPLATE`'s `## Guidelines` section.
- `src/frontend/src/modals/AssistantPanel/test-shell.tsx` — swap placeholder div for `<FlowPipelineView>`; pass `onSend` prop.
- `src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx` — update assertion (placeholder text → FlowPipelineView element).

**Untouched:** `flowStore.ts`, `assistantStore.ts`, `use-webhook-events.ts`, `buildUtils.ts`, `use-assistant-stream.ts`, `fullscreen-shell.tsx`, `AssistantPanel/index.tsx` — Plan 5 reuses their existing APIs, never modifies them.

---

## Task 1: Backend — `[TEST_FAILURE]` system-prompt guideline

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/service.py` (`SYSTEM_PROMPT_TEMPLATE` in `## Guidelines` section, around lines 50-86)
- Create: `src/backend/tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py`

- [ ] **Step 1: Write the failing test file**

Create `src/backend/tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py`:

```python
"""Pin the [TEST_FAILURE] guideline in SYSTEM_PROMPT_TEMPLATE."""

from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_test_failure_sentinel_bullet():
    assert "[TEST_FAILURE]" in SYSTEM_PROMPT_TEMPLATE
    assert "clicked \"Ask assistant\"" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_credential_walkthrough_keywords():
    # The guideline instructs the LLM to branch on these keywords.
    for keyword in ["credential", "auth", "api_key", "token", "invalid_auth", "401", "403"]:
        assert keyword in SYSTEM_PROMPT_TEMPLATE, f"missing keyword: {keyword}"


def test_prompt_tells_llm_to_stay_focused_on_fixing_one_failure():
    assert "do not propose redesigning the flow" in SYSTEM_PROMPT_TEMPLATE
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py -v`
Expected: 3 FAIL — "[TEST_FAILURE]" not in SYSTEM_PROMPT_TEMPLATE.

- [ ] **Step 3: Append the guideline bullet**

Open `src/backend/base/langflow/services/assistant/service.py`. Find the last bullet in the `## Guidelines` section of `SYSTEM_PROMPT_TEMPLATE` (the one that starts `"- Before starting a complex multi-component build…"` ending with `"…come back in a few minutes."`). Append this new bullet immediately after it, preserving the existing backslash-continuation style:

```
- When the user's most recent message starts with `[TEST_FAILURE]`, they \
clicked "Ask assistant" on a failed component test. Parse the component \
name, type, and error from the message. Respond conversationally with: \
(1) what likely went wrong in plain language, (2) concrete steps to fix \
it. If the error mentions `credential`, `auth`, `api_key`, `token`, \
`invalid_auth`, `401`, or `403`, prioritize a credentials walkthrough — \
explain where the user obtains the missing credential (e.g., "You'll \
need a Slack API token. Here's how to get one: go to api.slack.com/apps, \
create a new app…"), then where to put it in Langflow. Keep the \
response focused on fixing this one failure; do not propose redesigning \
the flow unless asked.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Stage (do not commit)**

```bash
git add src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py
```

The user batches commits at end of plan — do not run `git commit`.

---

## Task 2: Frontend — `test-runs.ts` helper

**Files:**
- Create: `src/frontend/src/utils/test-runs.ts`
- Create: `src/frontend/src/utils/__tests__/test-runs.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/utils/__tests__/test-runs.test.ts`:

```typescript
import { BuildStatus, EventDeliveryType } from "@/constants/enums";

jest.mock("@/utils/buildUtils", () => ({
  __esModule: true,
  buildFlowVerticesWithFallback: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ currentFlow: { id: "flow-abc" } }),
  },
}));

jest.mock("@/stores/assistantStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setSelectedTestComponent: jest.fn(),
    }),
  },
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      updateBuildStatus: jest.fn(),
      addDataToFlowPool: jest.fn(),
    }),
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ addNotificationToHistory: jest.fn() }),
  },
}));

import { buildFlowVerticesWithFallback } from "@/utils/buildUtils";
import useAssistantStore from "@/stores/assistantStore";
import { runTestForAll, runTestForComponent } from "../test-runs";

describe("test-runs", () => {
  beforeEach(() => {
    (buildFlowVerticesWithFallback as jest.Mock).mockClear();
  });

  it("runTestForComponent sets selectedTestComponent and calls build with stopNodeId", async () => {
    const setSelected = jest.fn();
    (useAssistantStore.getState as jest.Mock).mockReturnValueOnce({
      setSelectedTestComponent: setSelected,
    });

    await runTestForComponent("node-42");

    expect(setSelected).toHaveBeenCalledWith("node-42");
    expect(buildFlowVerticesWithFallback).toHaveBeenCalledTimes(1);
    const args = (buildFlowVerticesWithFallback as jest.Mock).mock.calls[0][0];
    expect(args.flowId).toBe("flow-abc");
    expect(args.stopNodeId).toBe("node-42");
    expect(args.eventDelivery).toBe(EventDeliveryType.STREAMING);
  });

  it("runTestForAll clears selectedTestComponent and calls build with no stopNodeId", async () => {
    const setSelected = jest.fn();
    (useAssistantStore.getState as jest.Mock).mockReturnValueOnce({
      setSelectedTestComponent: setSelected,
    });

    await runTestForAll();

    expect(setSelected).toHaveBeenCalledWith(null);
    const args = (buildFlowVerticesWithFallback as jest.Mock).mock.calls[0][0];
    expect(args.stopNodeId).toBeNull();
  });

  it("is a no-op when currentFlow is missing", async () => {
    // Override flowsManagerStore mock for this test only.
    const flowsManagerStore = require("@/stores/flowsManagerStore").default;
    flowsManagerStore.getState = () => ({ currentFlow: null });

    await runTestForComponent("node-42");

    expect(buildFlowVerticesWithFallback).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/utils/__tests__/test-runs.test.ts --no-coverage`
Expected: FAIL — `../test-runs` module not found.

- [ ] **Step 3: Implement `test-runs.ts`**

Create `src/frontend/src/utils/test-runs.ts`:

```typescript
import { BuildStatus, EventDeliveryType } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { buildFlowVerticesWithFallback } from "@/utils/buildUtils";

async function runBuild(stopNodeId: string | null): Promise<void> {
  const flowId = useFlowsManagerStore.getState().currentFlow?.id;
  if (!flowId) {
    return;
  }
  await buildFlowVerticesWithFallback({
    flowId,
    stopNodeId,
    eventDelivery: EventDeliveryType.STREAMING,
    onBuildStart: (elementList) => {
      const ids = elementList.map((e) => e.id);
      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.BUILDING);
    },
    onBuildUpdate: (vertexBuildData, status, runId) => {
      useFlowStore.getState().addDataToFlowPool(
        { ...vertexBuildData, run_id: runId ?? "" },
        vertexBuildData.id,
      );
      useFlowStore.getState().updateBuildStatus([vertexBuildData.id], status);
    },
    onBuildComplete: () => {},
    onBuildError: (title, list, elementList) => {
      const ids =
        (elementList?.map((e) => e.id).filter(Boolean) as string[]) ?? [];
      if (ids.length > 0) {
        useFlowStore.getState().updateBuildStatus(ids, BuildStatus.ERROR);
      }
      useAlertStore
        .getState()
        .addNotificationToHistory({ title, type: "error", list });
    },
  });
}

/**
 * Build every vertex up to and including `nodeId`.
 * Wires minimal callbacks that update flowBuildStatus + flowPool without
 * resetting prior per-node state (unlike flowStore.buildFlow).
 */
export async function runTestForComponent(nodeId: string): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(nodeId);
  await runBuild(nodeId);
}

/** Build the whole flow. */
export async function runTestForAll(): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(null);
  await runBuild(null);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/utils/__tests__/test-runs.test.ts --no-coverage`
Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/utils/test-runs.ts \
        src/frontend/src/utils/__tests__/test-runs.test.ts
```

---

## Task 3: Frontend — `dag-layout.ts` pure function + full test suite

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/dag-layout.ts`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts`

- [ ] **Step 1: Write the full failing test file first**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts`:

```typescript
import { computeDagLayout, type LayoutNode, type LayoutEdge } from "../dag-layout";

function node(
  id: string,
  category: string = "tools",
  display_name: string = id,
): LayoutNode {
  return {
    id,
    data: { type: id, display_name, category },
  };
}

function edge(source: string, target: string): LayoutEdge {
  return { source, target };
}

describe("computeDagLayout", () => {
  it("returns empty levels for empty graph", () => {
    const result = computeDagLayout([], []);
    expect(result.levels).toEqual([]);
  });

  it("places a single node at level 0", () => {
    const result = computeDagLayout([node("A")], []);
    expect(result.levels).toHaveLength(1);
    expect(result.levels[0].level).toBe(0);
    expect(result.levels[0].cards).toHaveLength(1);
    expect(result.levels[0].cards[0].node.id).toBe("A");
  });

  it("places a linear chain at increasing levels", () => {
    const result = computeDagLayout(
      [node("A"), node("B"), node("C")],
      [edge("A", "B"), edge("B", "C")],
    );
    expect(result.levels.map((l) => l.cards.map((c) => c.node.id))).toEqual([
      ["A"],
      ["B"],
      ["C"],
    ]);
  });

  it("lays parallel branches side-by-side with a shared downstream target", () => {
    // A → B, A → C, B → D, C → D (diamond)
    const result = computeDagLayout(
      [node("A"), node("B"), node("C"), node("D")],
      [edge("A", "B"), edge("A", "C"), edge("B", "D"), edge("C", "D")],
    );
    expect(result.levels).toHaveLength(3);
    expect(result.levels[0].cards.map((c) => c.node.id)).toEqual(["A"]);
    const levelOne = result.levels[1].cards.map((c) => c.node.id).sort();
    expect(levelOne).toEqual(["B", "C"]);
    // Each should list the other as a parallel sibling.
    const bCard = result.levels[1].cards.find((c) => c.node.id === "B")!;
    expect(bCard.parallelSiblings).toEqual(["C"]);
    const cCard = result.levels[1].cards.find((c) => c.node.id === "C")!;
    expect(cCard.parallelSiblings).toEqual(["B"]);
    expect(result.levels[2].cards.map((c) => c.node.id)).toEqual(["D"]);
  });

  it("groups a tool node under its agent parent", () => {
    // Tool → Agent, where Agent's category is in TOOL_PARENT_CATEGORIES
    const result = computeDagLayout(
      [node("Tool1"), node("Agent1", "agent")],
      [edge("Tool1", "Agent1")],
    );
    // Tool1 should NOT be its own card — grouped into Agent1.
    expect(result.levels).toHaveLength(1);
    expect(result.levels[0].cards).toHaveLength(1);
    const agentCard = result.levels[0].cards[0];
    expect(agentCard.node.id).toBe("Agent1");
    expect(agentCard.groupedChildren.map((c) => c.id)).toEqual(["Tool1"]);
  });

  it("does not group a tool node with ambiguous parents", () => {
    // Tool1 → Agent1 AND Tool1 → Agent2 — ambiguous, keep ungrouped.
    const result = computeDagLayout(
      [node("Tool1"), node("Agent1", "agent"), node("Agent2", "agent")],
      [edge("Tool1", "Agent1"), edge("Tool1", "Agent2")],
    );
    const allIds = result.levels.flatMap((l) => l.cards.map((c) => c.node.id));
    expect(allIds).toContain("Tool1");
    expect(allIds).toContain("Agent1");
    expect(allIds).toContain("Agent2");
    // Agent1 / Agent2 should have no grouped children.
    const agent1 = result.levels
      .flatMap((l) => l.cards)
      .find((c) => c.node.id === "Agent1")!;
    expect(agent1.groupedChildren).toEqual([]);
  });

  it("does not group a tool node when parent's category is not in TOOL_PARENT_CATEGORIES", () => {
    // Tool1 → Generic1 where Generic1.category = "models" (not in set)
    const result = computeDagLayout(
      [node("Tool1"), node("Generic1", "models")],
      [edge("Tool1", "Generic1")],
    );
    const allIds = result.levels.flatMap((l) => l.cards.map((c) => c.node.id));
    expect(allIds).toEqual(expect.arrayContaining(["Tool1", "Generic1"]));
  });

  it("falls back to a linear order when the graph contains a cycle", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    // A → B → C → A (cycle)
    const result = computeDagLayout(
      [node("A"), node("B"), node("C")],
      [edge("A", "B"), edge("B", "C"), edge("C", "A")],
    );
    // All three nodes show up somewhere.
    const allIds = result.levels.flatMap((l) => l.cards.map((c) => c.node.id));
    expect(allIds.sort()).toEqual(["A", "B", "C"]);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("stacks disconnected subgraphs into separate levels", () => {
    // Two disconnected chains: A → B and X → Y
    const result = computeDagLayout(
      [node("A"), node("B"), node("X"), node("Y")],
      [edge("A", "B"), edge("X", "Y")],
    );
    // Roots (A, X) at level 0; (B, Y) at level 1.
    expect(
      result.levels[0].cards.map((c) => c.node.id).sort(),
    ).toEqual(["A", "X"]);
    expect(
      result.levels[1].cards.map((c) => c.node.id).sort(),
    ).toEqual(["B", "Y"]);
  });
});
```

- [ ] **Step 2: Run the test to verify all fail**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts --no-coverage`
Expected: Module not found (`../dag-layout`) — all fail.

- [ ] **Step 3: Implement `dag-layout.ts`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/dag-layout.ts`:

```typescript
/** Curated parent-category set for tool grouping. */
export const TOOL_PARENT_CATEGORIES = new Set<string>([
  "agent",
  "llm",
  "orchestrator",
]);

export type LayoutNode = {
  id: string;
  data: { type: string; display_name?: string; category?: string };
};

export type LayoutEdge = {
  source: string;
  target: string;
};

export type LayoutCard = {
  node: LayoutNode;
  groupedChildren: LayoutNode[];
  parallelSiblings: string[];
};

export type LayoutLevel = {
  level: number;
  cards: LayoutCard[];
};

export type LayoutModel = {
  levels: LayoutLevel[];
  edgesBetweenLevels: Array<{ sourceLevel: number; targetLevel: number }>;
};

export function computeDagLayout(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
): LayoutModel {
  if (nodes.length === 0) {
    return { levels: [], edgesBetweenLevels: [] };
  }

  const byId = new Map<string, LayoutNode>(nodes.map((n) => [n.id, n]));
  const outEdges = new Map<string, string[]>();
  const inEdges = new Map<string, string[]>();
  for (const n of nodes) {
    outEdges.set(n.id, []);
    inEdges.set(n.id, []);
  }
  for (const e of edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) continue;
    outEdges.get(e.source)!.push(e.target);
    inEdges.get(e.target)!.push(e.source);
  }

  // Pass 1: topo sort + level assignment via Kahn's.
  const inDegree = new Map<string, number>(
    nodes.map((n) => [n.id, inEdges.get(n.id)!.length]),
  );
  const level = new Map<string, number>();
  const queue: string[] = [];
  for (const n of nodes) {
    if (inDegree.get(n.id) === 0) {
      queue.push(n.id);
      level.set(n.id, 0);
    }
  }
  let processed = 0;
  while (queue.length > 0) {
    const id = queue.shift()!;
    processed++;
    const curLevel = level.get(id)!;
    for (const next of outEdges.get(id)!) {
      level.set(next, Math.max(level.get(next) ?? 0, curLevel + 1));
      const nd = inDegree.get(next)! - 1;
      inDegree.set(next, nd);
      if (nd === 0) queue.push(next);
    }
  }

  // Cycle fallback: if some nodes were never reached, assign them level 0
  // and render them linearly. Log a warning.
  if (processed < nodes.length) {
    console.warn(
      "[FlowPipelineView] cycle detected in flow graph; falling back to linear layout",
    );
    for (const n of nodes) {
      if (!level.has(n.id)) level.set(n.id, 0);
    }
  }

  // Pass 2: tool grouping.
  const groupedInto = new Map<string, string>(); // child -> parent
  for (const n of nodes) {
    const outs = outEdges.get(n.id)!;
    const ins = inEdges.get(n.id)!;
    if (outs.length !== 1) continue;
    if (ins.length !== 0) continue;
    // Ambiguity check: is `n` a potential tool child for multiple parents?
    const candidates = outs.filter((pid) => {
      const parentCat = byId.get(pid)?.data.category;
      return parentCat && TOOL_PARENT_CATEGORIES.has(parentCat);
    });
    if (candidates.length !== 1) continue;
    groupedInto.set(n.id, candidates[0]);
  }

  // Pass 3: build cards per level (skip grouped children as own cards).
  const cardsByLevel = new Map<number, LayoutCard[]>();
  for (const n of nodes) {
    if (groupedInto.has(n.id)) continue;
    const l = level.get(n.id)!;
    if (!cardsByLevel.has(l)) cardsByLevel.set(l, []);
    const children = nodes.filter((c) => groupedInto.get(c.id) === n.id);
    cardsByLevel.get(l)!.push({
      node: n,
      groupedChildren: children,
      parallelSiblings: [],
    });
  }

  // Compute parallel siblings within each level.
  for (const [, cards] of cardsByLevel) {
    for (const card of cards) {
      const myTargets = new Set(outEdges.get(card.node.id) ?? []);
      card.parallelSiblings = cards
        .filter((other) => other.node.id !== card.node.id)
        .filter((other) => {
          const otherTargets = new Set(outEdges.get(other.node.id) ?? []);
          for (const t of myTargets) if (otherTargets.has(t)) return true;
          return false;
        })
        .map((other) => other.node.id);
    }
  }

  const sortedLevels = [...cardsByLevel.entries()]
    .sort(([a], [b]) => a - b)
    .map(([l, cards]) => ({ level: l, cards }));

  // Collect level-to-level edges for layout rendering.
  const edgesBetweenLevels: Array<{ sourceLevel: number; targetLevel: number }> = [];
  for (const e of edges) {
    const s = level.get(e.source);
    const t = level.get(e.target);
    if (s !== undefined && t !== undefined && s !== t) {
      edgesBetweenLevels.push({ sourceLevel: s, targetLevel: t });
    }
  }

  return { levels: sortedLevels, edgesBetweenLevels };
}
```

- [ ] **Step 4: Run the test to verify all pass**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts --no-coverage`
Expected: 9 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/dag-layout.ts \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/dag-layout.test.ts
```

---

## Task 4: Frontend — `status-badge.tsx`

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/status-badge.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../status-badge";

describe("StatusBadge", () => {
  it("renders 'Not tested' for not_tested status", () => {
    render(<StatusBadge status="not_tested" />);
    expect(screen.getByText("Not tested")).toBeInTheDocument();
  });

  it("renders 'Testing…' for testing status", () => {
    render(<StatusBadge status="testing" />);
    expect(screen.getByText(/Testing/)).toBeInTheDocument();
  });

  it("renders 'Passed' for passed status", () => {
    render(<StatusBadge status="passed" />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("renders error message for failed status", () => {
    render(<StatusBadge status="failed" errorMessage="invalid_auth" />);
    expect(screen.getByText(/invalid_auth/)).toBeInTheDocument();
  });

  it("renders 'Failed' when failed status has no error message", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx --no-coverage`
Expected: FAIL — `../status-badge` module not found.

- [ ] **Step 3: Implement `status-badge.tsx`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/status-badge.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";

export type TestStatus = "not_tested" | "testing" | "passed" | "failed";

type Props = {
  status: TestStatus;
  errorMessage?: string;
};

export function StatusBadge({ status, errorMessage }: Props) {
  if (status === "not_tested") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
        Not tested
      </span>
    );
  }
  if (status === "testing") {
    return (
      <span className="flex items-center gap-1 text-xs text-amber-600">
        <ForwardedIconComponent name="Loader2" className="h-3 w-3 animate-spin" />
        Testing…
      </span>
    );
  }
  if (status === "passed") {
    return (
      <span className="flex items-center gap-1 text-xs text-emerald-600">
        <ForwardedIconComponent name="Check" className="h-3 w-3" />
        Passed
      </span>
    );
  }
  // failed
  const label = errorMessage ? errorMessage.split("\n")[0] : "Failed";
  return (
    <span
      className="flex items-center gap-1 truncate text-xs text-red-600"
      title={errorMessage}
    >
      <ForwardedIconComponent name="X" className="h-3 w-3 shrink-0" />
      <span className="truncate">{label}</span>
    </span>
  );
}
```

Note: `ForwardedIconComponent` is the default export of `@/components/common/genericIconComponent`. Follow the existing import style in `test-shell.tsx` (which imports it as `ForwardedIconComponent` from the same module).

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx --no-coverage`
Expected: 5 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/status-badge.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/status-badge.test.tsx
```

---

## Task 5: Frontend — `raw-output.tsx`

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/raw-output.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RawOutput } from "../raw-output";

describe("RawOutput", () => {
  it("is collapsed by default", () => {
    render(<RawOutput value={{ hello: "world" }} />);
    expect(screen.queryByText(/"hello": "world"/)).not.toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveTextContent(/View full output/i);
  });

  it("expands and shows JSON when clicked", async () => {
    const user = userEvent.setup();
    render(<RawOutput value={{ hello: "world" }} />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText(/"hello": "world"/)).toBeInTheDocument();
  });

  it("renders a string value verbatim when expanded", async () => {
    const user = userEvent.setup();
    render(<RawOutput value="plain text" />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("plain text")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx --no-coverage`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `raw-output.tsx`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/raw-output.tsx`:

```tsx
import { useState } from "react";

type Props = {
  value: unknown;
};

export function RawOutput({ value }: Props) {
  const [open, setOpen] = useState(false);
  const rendered =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div>
      <button
        type="button"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "Hide full output" : "View full output →"}
      </button>
      {open && (
        <pre className="mt-2 max-h-60 overflow-auto rounded bg-muted p-2 text-xs">
          {rendered}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx --no-coverage`
Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/raw-output.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/raw-output.test.tsx
```

---

## Task 6: Frontend — `test-all-button.tsx`

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/test-all-button.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const runTestForAll = jest.fn().mockResolvedValue(undefined);
jest.mock("@/utils/test-runs", () => ({
  __esModule: true,
  runTestForAll: (...args: unknown[]) => runTestForAll(...args),
  runTestForComponent: jest.fn(),
}));

import { TestAllButton } from "../test-all-button";

describe("TestAllButton", () => {
  beforeEach(() => {
    runTestForAll.mockClear();
  });

  it("renders the 'Test All' label", () => {
    render(<TestAllButton anyTesting={false} />);
    expect(screen.getByRole("button", { name: /test all/i })).toBeInTheDocument();
  });

  it("calls runTestForAll when clicked", async () => {
    const user = userEvent.setup();
    render(<TestAllButton anyTesting={false} />);
    await user.click(screen.getByRole("button", { name: /test all/i }));
    expect(runTestForAll).toHaveBeenCalledTimes(1);
  });

  it("is disabled while any single test is in progress", async () => {
    const user = userEvent.setup();
    render(<TestAllButton anyTesting={true} />);
    const btn = screen.getByRole("button", { name: /test all/i });
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(runTestForAll).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx --no-coverage`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `test-all-button.tsx`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/test-all-button.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { runTestForAll } from "@/utils/test-runs";

type Props = {
  anyTesting: boolean;
};

export function TestAllButton({ anyTesting }: Props) {
  return (
    <Button
      size="sm"
      disabled={anyTesting}
      onClick={() => {
        void runTestForAll();
      }}
    >
      Test All
    </Button>
  );
}
```

Note: `Button` comes from `@/components/ui/button` (shadcn style — this path is used elsewhere in the AssistantPanel codebase). If the exact import path differs, grep `test-shell.tsx` and `fullscreen-shell.tsx` for the pattern they use.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx --no-coverage`
Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/test-all-button.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/test-all-button.test.tsx
```

---

## Task 7: Frontend — `pipeline-card.tsx`

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const runTestForComponent = jest.fn().mockResolvedValue(undefined);
jest.mock("@/utils/test-runs", () => ({
  __esModule: true,
  runTestForComponent: (...args: unknown[]) => runTestForComponent(...args),
  runTestForAll: jest.fn(),
}));

import { PipelineCard } from "../pipeline-card";

function makeNode(id: string, overrides: Partial<any> = {}): any {
  return {
    id,
    data: { type: id, display_name: id, category: "tools" },
    ...overrides,
  };
}

describe("PipelineCard", () => {
  beforeEach(() => {
    runTestForComponent.mockClear();
  });

  it("renders a 'Test' button when status is not_tested", () => {
    render(
      <PipelineCard
        node={makeNode("A")}
        groupedChildren={[]}
        status="not_tested"
        latestResult={null}
        onSend={jest.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /^test$/i }),
    ).toBeInTheDocument();
  });

  it("renders a spinner when status is testing (no buttons)", () => {
    render(
      <PipelineCard
        node={makeNode("A")}
        groupedChildren={[]}
        status="testing"
        latestResult={null}
        onSend={jest.fn()}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /^test$/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Testing/)).toBeInTheDocument();
  });

  it("renders Re-test + View full output when status is passed", () => {
    render(
      <PipelineCard
        node={makeNode("A")}
        groupedChildren={[]}
        status="passed"
        latestResult={{
          id: "A",
          valid: true,
          data: { results: { foo: "bar" } },
          timestamp: "",
          params: {},
          messages: [],
          artifacts: {},
          inactivated_vertices: null,
          next_vertices_ids: [],
          top_level_vertices: [],
        } as any}
        onSend={jest.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /re-test/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view full output/i })).toBeInTheDocument();
  });

  it("renders Ask assistant when status is failed and sends a [TEST_FAILURE] message on click", async () => {
    const user = userEvent.setup();
    const onSend = jest.fn();
    render(
      <PipelineCard
        node={makeNode("A", { data: { type: "Slack", display_name: "Slack", category: "tools" } })}
        groupedChildren={[]}
        status="failed"
        latestResult={{
          id: "A",
          valid: false,
          data: { error: "invalid_auth" },
          timestamp: "",
          params: {},
          messages: [],
          artifacts: {},
          inactivated_vertices: null,
          next_vertices_ids: [],
          top_level_vertices: [],
        } as any}
        onSend={onSend}
      />,
    );
    const btn = screen.getByRole("button", { name: /ask assistant/i });
    await user.click(btn);
    expect(onSend).toHaveBeenCalledTimes(1);
    const msg = onSend.mock.calls[0][0];
    expect(msg).toMatch(/^\[TEST_FAILURE\]/);
    expect(msg).toContain("Slack");
    expect(msg).toContain("invalid_auth");
  });

  it("calls runTestForComponent when Test button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <PipelineCard
        node={makeNode("node-42")}
        groupedChildren={[]}
        status="not_tested"
        latestResult={null}
        onSend={jest.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    expect(runTestForComponent).toHaveBeenCalledWith("node-42");
  });

  it("renders grouped children as indented sub-items", () => {
    render(
      <PipelineCard
        node={makeNode("Agent1")}
        groupedChildren={[makeNode("Tool1"), makeNode("Tool2")]}
        status="not_tested"
        latestResult={null}
        onSend={jest.fn()}
      />,
    );
    expect(screen.getByText(/Tool: Tool1/)).toBeInTheDocument();
    expect(screen.getByText(/Tool: Tool2/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx --no-coverage`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `pipeline-card.tsx`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx`:

```tsx
import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import type { VertexBuildTypeAPI } from "@/types/api";
import { runTestForComponent } from "@/utils/test-runs";
import { RawOutput } from "./raw-output";
import { StatusBadge, type TestStatus } from "./status-badge";
import type { LayoutNode } from "./dag-layout";

type Props = {
  node: LayoutNode;
  groupedChildren: LayoutNode[];
  status: TestStatus;
  latestResult: VertexBuildTypeAPI | null;
  onSend: (text: string) => void;
};

function extractErrorMessage(result: VertexBuildTypeAPI | null): string {
  if (!result) return "";
  const data = result.data as Record<string, unknown> | undefined;
  if (!data) return "";
  const err = (data as { error?: unknown }).error;
  if (typeof err === "string") return err;
  const msg = (data as { message?: unknown }).message;
  if (typeof msg === "string") return msg;
  return "";
}

function extractOutputSummary(result: VertexBuildTypeAPI | null): string {
  if (!result) return "";
  const data = result.data as Record<string, unknown> | undefined;
  const msg = data?.["message"];
  return typeof msg === "string" ? msg : "";
}

export function PipelineCard({
  node,
  groupedChildren,
  status,
  latestResult,
  onSend,
}: Props) {
  const displayName = node.data.display_name || node.id;
  const typeName = node.data.type;
  const errorMessage = extractErrorMessage(latestResult);

  const handleTest = useCallback(() => {
    void runTestForComponent(node.id);
  }, [node.id]);

  const handleAskAssistant = useCallback(() => {
    const outputSummary = extractOutputSummary(latestResult);
    const message =
      `[TEST_FAILURE] Component \`${displayName}\` (${typeName}) failed.\n` +
      `Error: ${errorMessage || "Unknown error"}\n` +
      (outputSummary ? `Last output: ${outputSummary}\n` : "") +
      `Walk me through how to fix this.`;
    onSend(message);
  }, [displayName, typeName, errorMessage, latestResult, onSend]);

  return (
    <div className="rounded-md border bg-background p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{displayName}</div>
          {groupedChildren.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
              {groupedChildren.map((child) => (
                <li key={child.id}>
                  Tool: {child.data.display_name || child.id}
                </li>
              ))}
            </ul>
          )}
        </div>
        <StatusBadge status={status} errorMessage={errorMessage} />
      </div>

      {status === "failed" && errorMessage && (
        <div className="mt-2 truncate text-xs text-red-600" title={errorMessage}>
          {errorMessage}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {status === "not_tested" && (
          <Button size="sm" onClick={handleTest}>
            Test
          </Button>
        )}
        {status === "testing" && (
          <span className="text-xs text-muted-foreground">Testing…</span>
        )}
        {status === "passed" && (
          <>
            <Button size="sm" variant="outline" onClick={handleTest}>
              Re-test
            </Button>
          </>
        )}
        {status === "failed" && (
          <>
            <Button size="sm" variant="outline" onClick={handleTest}>
              Re-test
            </Button>
            <Button size="sm" variant="destructive" onClick={handleAskAssistant}>
              Ask assistant
            </Button>
          </>
        )}
        {(status === "passed" || status === "failed") && latestResult && (
          <RawOutput value={latestResult.data} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx --no-coverage`
Expected: 6 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx
```

---

## Task 8: Frontend — `FlowPipelineView/index.tsx` container

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/index.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import useAssistantStore from "@/stores/assistantStore";
import { FlowPipelineView } from "../index";

jest.mock("@/utils/test-runs", () => ({
  __esModule: true,
  runTestForAll: jest.fn(),
  runTestForComponent: jest.fn(),
}));

function setFlowStore(partial: Partial<any>) {
  useFlowStore.setState({ ...(useFlowStore.getState() as any), ...partial });
}

describe("FlowPipelineView", () => {
  beforeEach(() => {
    useFlowStore.setState({
      nodes: [],
      edges: [],
      flowBuildStatus: {},
      flowPool: {},
    } as any);
    useAssistantStore.setState({
      layoutMode: "test",
      selectedTestComponent: null,
    } as any);
  });

  it("renders the empty state when there are zero nodes", () => {
    render(<FlowPipelineView onSend={jest.fn()} />);
    expect(screen.getByText(/No components yet/i)).toBeInTheDocument();
  });

  it("renders one card per ungrouped node with derived status", () => {
    setFlowStore({
      nodes: [
        {
          id: "A",
          data: { type: "ChatInput", node: { display_name: "A", category: "inputs" } },
        },
        {
          id: "B",
          data: { type: "ChatOutput", node: { display_name: "B", category: "outputs" } },
        },
      ],
      edges: [{ source: "A", target: "B", data: {} }],
      flowBuildStatus: {
        A: { status: BuildStatus.BUILT },
        B: { status: BuildStatus.ERROR },
      },
      flowPool: { B: [{ id: "B", valid: false, data: { error: "oops" } }] },
    });
    render(<FlowPipelineView onSend={jest.fn()} />);
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText("Passed")).toBeInTheDocument();
    // The failed-status badge renders the error message, not "Failed".
    expect(screen.getAllByText(/oops/).length).toBeGreaterThan(0);
  });

  it("renders the Test All button", () => {
    setFlowStore({
      nodes: [
        {
          id: "A",
          data: { type: "ChatInput", node: { display_name: "A", category: "inputs" } },
        },
      ],
      edges: [],
      flowBuildStatus: {},
      flowPool: {},
    });
    render(<FlowPipelineView onSend={jest.fn()} />);
    expect(screen.getByRole("button", { name: /test all/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx --no-coverage`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `FlowPipelineView/index.tsx`**

Create `src/frontend/src/modals/AssistantPanel/FlowPipelineView/index.tsx`:

```tsx
import { useMemo } from "react";
import { BuildStatus } from "@/constants/enums";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";
import { PipelineCard } from "./pipeline-card";
import { TestAllButton } from "./test-all-button";
import { computeDagLayout, type LayoutEdge, type LayoutNode } from "./dag-layout";
import type { TestStatus } from "./status-badge";

function deriveStatus(
  entry: { status: BuildStatus } | undefined,
): TestStatus {
  if (!entry) return "not_tested";
  switch (entry.status) {
    case BuildStatus.BUILDING:
      return "testing";
    case BuildStatus.BUILT:
      return "passed";
    case BuildStatus.ERROR:
      return "failed";
    case BuildStatus.TO_BUILD:
    case BuildStatus.INACTIVE:
    default:
      return "not_tested";
  }
}

type Props = {
  onSend: (text: string) => void;
};

export function FlowPipelineView({ onSend }: Props) {
  const nodes = useFlowStore((s) => s.nodes);
  const edges = useFlowStore((s) => s.edges);
  const flowBuildStatus = useFlowStore((s) => s.flowBuildStatus);
  const flowPool = useFlowStore((s) => s.flowPool);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);

  const layoutNodes: LayoutNode[] = useMemo(
    () =>
      nodes.map((n: any) => ({
        id: n.id,
        data: {
          type: n.data?.type ?? n.id,
          display_name:
            n.data?.node?.display_name ?? n.data?.display_name ?? n.id,
          category: n.data?.node?.category ?? n.data?.category,
        },
      })),
    [nodes],
  );

  const layoutEdges: LayoutEdge[] = useMemo(
    () => edges.map((e: any) => ({ source: e.source, target: e.target })),
    [edges],
  );

  const layout = useMemo(
    () => computeDagLayout(layoutNodes, layoutEdges),
    [layoutNodes, layoutEdges],
  );

  const anyTesting = useMemo(
    () =>
      Object.values(flowBuildStatus ?? {}).some(
        (v: any) => v?.status === BuildStatus.BUILDING,
      ),
    [flowBuildStatus],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center text-muted-foreground">
        <div className="text-sm">No components yet. Go back to chat and add some.</div>
        <button
          type="button"
          className="text-sm underline"
          onClick={() => setLayoutMode("fullscreen")}
        >
          Back to chat
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">Pipeline</div>
        <TestAllButton anyTesting={anyTesting} />
      </div>
      <div className="flex flex-col gap-6">
        {layout.levels.map((level) => (
          <div key={level.level} className="flex flex-wrap gap-3">
            {level.cards.map((card) => {
              const latest = flowPool?.[card.node.id]?.slice(-1)[0] ?? null;
              const status = deriveStatus(flowBuildStatus?.[card.node.id]);
              return (
                <div
                  key={card.node.id}
                  className={
                    card.parallelSiblings.length > 0
                      ? "min-w-[240px] flex-1"
                      : "w-full"
                  }
                >
                  <PipelineCard
                    node={card.node}
                    groupedChildren={card.groupedChildren}
                    status={status}
                    latestResult={latest}
                    onSend={onSend}
                  />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx --no-coverage`
Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/index.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/FlowPipelineView.test.tsx
```

---

## Task 9: Frontend — Wire `FlowPipelineView` into `test-shell.tsx`

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/test-shell.tsx` (replace the placeholder div)
- Modify: `src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx` (update assertion if it checks placeholder text)

- [ ] **Step 1: Extend the existing test to assert the pipeline view renders (failing)**

The current file (`shell-switch.test.tsx`, 70 lines) tests each layout mode but does not assert content inside the test-shell left pane. Once `test-shell.tsx` swaps its placeholder for `FlowPipelineView`, which reads `useFlowStore`, the existing test will fail because no flowStore state is set up.

Edit `shell-switch.test.tsx`:

**1a. Add a `useFlowStore` import at the top, after the `useAssistantStore` import:**

```typescript
import useFlowStore from "@/stores/flowStore";
```

**1b. Extend the `beforeEach` block at line 34-41 to also reset `useFlowStore`:**

```typescript
beforeEach(() => {
  useAssistantStore.setState({
    panelOpen: true,
    layoutMode: "panel",
    settingsConfigured: true,
    messages: [],
  });
  useFlowStore.setState({
    nodes: [],
    edges: [],
    flowBuildStatus: {},
    flowPool: {},
  } as any);
});
```

**1c. Extend the `it("renders the test shell when layoutMode is 'test'", ...)` test (line 58-62) with an assertion that FlowPipelineView's empty state renders:**

```typescript
it("renders the test shell when layoutMode is 'test'", () => {
  useAssistantStore.setState({ layoutMode: "test" });
  render(<AssistantPanel flowId="flow-1" />);
  expect(screen.getByTestId("adp-assist-back-to-chat-btn")).toBeInTheDocument();
  expect(screen.getByText(/No components yet/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/__tests__/shell-switch.test.tsx --no-coverage`
Expected: the `"renders the test shell when layoutMode is 'test'"` test FAILs — "No components yet" not found (placeholder still reads "Pipeline view will appear here"). Other tests in the file still pass.

- [ ] **Step 3: Replace the placeholder in `test-shell.tsx`**

Open `src/frontend/src/modals/AssistantPanel/test-shell.tsx`. Find the left-pane placeholder div (currently lines 64-72 per the prior exploration). Replace:

```tsx
<div className="flex w-1/2 flex-col items-center justify-center border-r text-muted-foreground">
  <ForwardedIconComponent
    name="GitBranch"
    className="mb-2 h-8 w-8 opacity-50"
  />
  <div className="text-sm">
    Pipeline view will appear here (Plan 5).
  </div>
</div>
```

with:

```tsx
<div className="flex w-1/2 flex-col border-r overflow-auto">
  <FlowPipelineView onSend={onSend} />
</div>
```

Add the import at the top of the file:

```typescript
import { FlowPipelineView } from "./FlowPipelineView";
```

If `ForwardedIconComponent` becomes unused after this change, remove its import. Otherwise leave it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/__tests__/shell-switch.test.tsx --no-coverage`
Expected: PASS.

- [ ] **Step 5: Run the full AssistantPanel test subtree as a smoke check**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel --no-coverage`
Expected: all tests PASS.

- [ ] **Step 6: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/test-shell.tsx \
        src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx
```

---

## Task 10: Cross-suite verification + manual checklist

**Files:** none modified. This task validates the plan end-to-end.

- [ ] **Step 1: Run the full frontend AssistantPanel test suite**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel src/utils/__tests__/test-runs.test.ts --no-coverage`
Expected: ALL PASS.

- [ ] **Step 2: Run the backend guideline test**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant/test_test_failure_guideline_in_prompt.py tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py -v`
Expected: ALL PASS (includes Plan 4's greeting tests — regression check).

- [ ] **Step 3: Manual verification — pipeline renders**

Start the stack (`make run` or project's usual dev-server command), open a flow in the browser, open the ADP Assist panel, switch to fullscreen (per Plan 4), then click the Test button to enter Test mode. Confirm `FlowPipelineView` renders with a card per component, arranged in topological order.

- [ ] **Step 4: Manual verification — single-node test happy path**

In the browser, on a flow with a simple root component (ChatInput or similar), click the `Test` button on that card. Expected:
1. Badge goes `Not tested → Testing… → Passed`
2. `View full output →` button appears
3. Clicking it expands a `<pre>` with the node's output data

- [ ] **Step 5: Manual verification — upstream-plus-self semantics**

Click the `Test` button on a middle node of a chain (A → B → C, click on B). Expected: A's badge also flips to `Passed` as part of the same run (because B's build requires A).

- [ ] **Step 6: Manual verification — failure path + Ask assistant**

Configure a component with an invalid API key (e.g., Slack with `xoxb-invalid`). Click Test on that card. Expected:
1. Badge goes `Testing… → Failed` with the error message inline (e.g., `invalid_auth`)
2. `Ask assistant` button appears
3. Clicking Ask assistant appends a `[TEST_FAILURE]` message to the right-pane chat
4. The assistant responds conversationally with a credentials walkthrough (not generic troubleshooting)

- [ ] **Step 7: Manual verification — Test All**

Click `Test All`. Expected: badges update on every card as the full flow builds. During the run, the `Test All` button is disabled.

- [ ] **Step 8: Manual verification — tool grouping**

On a flow with an agent-with-tools shape (e.g., `Agent` node with `category=agent` and multiple tool nodes feeding in), confirm tools appear as indented sub-items under the agent card, not as separate cards.

- [ ] **Step 9: Manual verification — parallel branches**

On a diamond flow (A → B, A → C, B → D, C → D), confirm B and C render side-by-side within the same level row.

- [ ] **Step 10: Manual verification — empty flow**

Open a brand-new empty flow in test mode. Confirm the empty state renders with `No components yet. Go back to chat and add some.` and a `Back to chat` button that returns to fullscreen chat (Plan 4 layout mode).

- [ ] **Step 11: Report readiness for commit**

If all above steps pass, report to the human: "Plan 5 implementation complete, ready for batched commit". Do NOT run `git commit`. The human will review and author the commit.

---

## Open Items for Implementation (flag to user if hit)

- **`TOOL_PARENT_CATEGORIES` value.** Starts as `["agent", "llm", "orchestrator"]`. During Step 8 of Task 10, if a real agent-with-tools flow obviously should group but doesn't (because the parent's category string differs), grep the codebase for the actual category values used by agent-style components (`src/backend/base/langflow/components/agents/` and `src/lfx/src/lfx/components/agents/` likely hold the source of truth) and extend the set.
- **JSON syntax highlighting for RawOutput.** The plan uses plain `<pre>`. If the reviewer requests prettier output, swap `<pre>{rendered}</pre>` for `<SimplifiedCodeTabComponent language="json" code={rendered} />` from `@/components/core/codeTabsComponent`.
- **`onBuildUpdate` callback signature.** Confirmed as `(data: any, status: BuildStatus, buildId: string) => void` at `src/frontend/src/utils/buildUtils.ts:182`. If the signature has changed by the time this plan is executed, adjust `test-runs.ts`'s callback accordingly.
