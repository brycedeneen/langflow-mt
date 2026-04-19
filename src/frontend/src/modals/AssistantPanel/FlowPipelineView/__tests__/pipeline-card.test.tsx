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
