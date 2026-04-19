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

function edge(
  source: string,
  target: string,
  targetHandleFieldName?: string,
): LayoutEdge {
  return { source, target, targetHandleFieldName };
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
    expect(result.edgesBetweenLevels).toEqual([
      { sourceLevel: 0, targetLevel: 1 },
      { sourceLevel: 1, targetLevel: 2 },
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
    // Diamond has 4 edges: A→B (0→1), A→C (0→1), B→D (1→2), C→D (1→2)
    expect(result.edgesBetweenLevels).toHaveLength(4);
    const signature = result.edgesBetweenLevels
      .map((e) => `${e.sourceLevel}->${e.targetLevel}`)
      .sort();
    expect(signature).toEqual(["0->1", "0->1", "1->2", "1->2"]);
  });

  it("groups a tool node when its outgoing edge targets the parent's 'tools' input", () => {
    const result = computeDagLayout(
      [node("Tool1"), node("Agent1")],
      [edge("Tool1", "Agent1", "tools")],
    );
    // Tool1 should NOT be its own card — grouped into Agent1.
    expect(result.levels).toHaveLength(1);
    expect(result.levels[0].cards).toHaveLength(1);
    const agentCard = result.levels[0].cards[0];
    expect(agentCard.node.id).toBe("Agent1");
    expect(agentCard.groupedChildren.map((c) => c.id)).toEqual(["Tool1"]);
  });

  it("does not group a tool node when it has multiple outgoing edges", () => {
    // Even if both edges target 'tools', two outgoing edges disqualify grouping
    // because the node isn't a root-leaf tool with a single home.
    const result = computeDagLayout(
      [node("Tool1"), node("Agent1"), node("Agent2")],
      [edge("Tool1", "Agent1", "tools"), edge("Tool1", "Agent2", "tools")],
    );
    const allIds = result.levels.flatMap((l) => l.cards.map((c) => c.node.id));
    expect(allIds).toContain("Tool1");
    expect(allIds).toContain("Agent1");
    expect(allIds).toContain("Agent2");
    const agent1 = result.levels
      .flatMap((l) => l.cards)
      .find((c) => c.node.id === "Agent1")!;
    expect(agent1.groupedChildren).toEqual([]);
    const agent2 = result.levels
      .flatMap((l) => l.cards)
      .find((c) => c.node.id === "Agent2")!;
    expect(agent2.groupedChildren).toEqual([]);
  });

  it("does not group when the outgoing edge does not target a 'tools' input", () => {
    // Edge targets e.g. 'input_value' — the child is a normal upstream node.
    const result = computeDagLayout(
      [node("Input1"), node("Model1")],
      [edge("Input1", "Model1", "input_value")],
    );
    const allIds = result.levels.flatMap((l) => l.cards.map((c) => c.node.id));
    expect(allIds).toEqual(expect.arrayContaining(["Input1", "Model1"]));
    const model1 = result.levels
      .flatMap((l) => l.cards)
      .find((c) => c.node.id === "Model1")!;
    expect(model1.groupedChildren).toEqual([]);
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
