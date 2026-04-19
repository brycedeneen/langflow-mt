/** Field name on a target handle that marks this edge as wiring a tool into
 * a parent's `tools` input. Kept as a constant so it can be adjusted if
 * Langflow ever renames the pin. */
export const TOOL_INPUT_FIELD_NAME = "tools";

export type LayoutNode = {
  id: string;
  data: { type: string; display_name?: string; category?: string };
};

export type LayoutEdge = {
  source: string;
  target: string;
  /** Field name the edge targets on its destination node. When this is
   * `"tools"` and the source has no other incoming/outgoing edges, the
   * source is grouped under the target as a sub-item. */
  targetHandleFieldName?: string;
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

  // Build lookup maps using explicit iteration to avoid iterator spread issues.
  const byId: Record<string, LayoutNode> = Object.create(null);
  for (const n of nodes) byId[n.id] = n;

  const outEdges: Record<string, string[]> = Object.create(null);
  const inEdges: Record<string, string[]> = Object.create(null);
  for (const n of nodes) {
    outEdges[n.id] = [];
    inEdges[n.id] = [];
  }
  for (const e of edges) {
    if (!byId[e.source] || !byId[e.target]) continue;
    outEdges[e.source].push(e.target);
    inEdges[e.target].push(e.source);
  }

  // Pass 1: topo sort + level assignment via Kahn's.
  const inDegree: Record<string, number> = Object.create(null);
  for (const n of nodes) inDegree[n.id] = inEdges[n.id].length;

  const level: Record<string, number> = Object.create(null);
  const queue: string[] = [];
  for (const n of nodes) {
    if (inDegree[n.id] === 0) {
      queue.push(n.id);
      level[n.id] = 0;
    }
  }
  let processed = 0;
  while (queue.length > 0) {
    const id = queue.shift()!;
    processed++;
    const curLevel = level[id];
    for (const next of outEdges[id]) {
      level[next] = Math.max(level[next] ?? 0, curLevel + 1);
      inDegree[next]--;
      if (inDegree[next] === 0) queue.push(next);
    }
  }

  // Cycle fallback: if some nodes were never reached, assign them level 0
  // and render them linearly. Log a warning.
  if (processed < nodes.length) {
    console.warn(
      "[FlowPipelineView] cycle detected in flow graph; falling back to linear layout",
    );
    for (const n of nodes) {
      if (level[n.id] === undefined) level[n.id] = 0;
    }
  }

  // Pass 2: tool grouping.
  // A child is grouped under a parent when its single outgoing edge targets
  // the parent's `tools` input pin. This is the semantic signal Langflow emits
  // for any tool wired into an agent / crew / LLM's tools input, and is more
  // stable than hardcoded category lists.
  const toolEdgeByChild: Record<string, string> = Object.create(null); // child -> parent
  for (const e of edges) {
    if (e.targetHandleFieldName !== TOOL_INPUT_FIELD_NAME) continue;
    if (!byId[e.source] || !byId[e.target]) continue;
    toolEdgeByChild[e.source] = e.target;
  }
  const groupedInto: Record<string, string> = Object.create(null); // child -> parent
  for (const n of nodes) {
    const parent = toolEdgeByChild[n.id];
    if (!parent) continue;
    const outs = outEdges[n.id];
    const ins = inEdges[n.id];
    if (outs.length !== 1) continue;
    if (ins.length !== 0) continue;
    groupedInto[n.id] = parent;
  }

  // Pass 3: build cards per level (skip grouped children as own cards).
  const cardsByLevel: Record<number, LayoutCard[]> = Object.create(null);
  for (const n of nodes) {
    if (groupedInto[n.id] !== undefined) continue;
    const l = level[n.id];
    if (cardsByLevel[l] === undefined) cardsByLevel[l] = [];
    const children = nodes.filter((c) => groupedInto[c.id] === n.id);
    cardsByLevel[l].push({
      node: n,
      groupedChildren: children,
      parallelSiblings: [],
    });
  }

  // Compute parallel siblings within each level.
  const levelNums = Object.keys(cardsByLevel).map(Number);
  for (const l of levelNums) {
    const cards = cardsByLevel[l];
    for (const card of cards) {
      const myTargets = new Set(outEdges[card.node.id] ?? []);
      card.parallelSiblings = cards
        .filter((other) => other.node.id !== card.node.id)
        .filter((other) => {
          const otherTargets = outEdges[other.node.id] ?? [];
          for (const t of otherTargets) {
            if (myTargets.has(t)) return true;
          }
          return false;
        })
        .map((other) => other.node.id);
    }
  }

  const sortedLevels = levelNums
    .sort((a, b) => a - b)
    .map((l) => ({ level: l, cards: cardsByLevel[l] }));

  // Collect level-to-level edges for layout rendering.
  const edgesBetweenLevels: Array<{ sourceLevel: number; targetLevel: number }> = [];
  for (const e of edges) {
    const s = level[e.source];
    const t = level[e.target];
    if (s !== undefined && t !== undefined && s !== t) {
      edgesBetweenLevels.push({ sourceLevel: s, targetLevel: t });
    }
  }

  return { levels: sortedLevels, edgesBetweenLevels };
}
