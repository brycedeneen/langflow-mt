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
