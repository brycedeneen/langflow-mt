import { act, fireEvent, render, screen } from "@testing-library/react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import useFlowStore from "@/stores/flowStore";
import ComponentAssistPopover from "../index";

describe("ComponentAssistPopover", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: null,
      anchorRect: null,
      position: { x: 100, y: 100 },
      size: { w: 420, h: 500 },
      thread: [],
      isStreaming: false,
      abortController: null,
    });
    useFlowStore.setState({
      currentFlow: { id: "flow-a" } as any,
      nodes: [],
      edges: [],
    });
  });

  it("does not render when closed", () => {
    render(<ComponentAssistPopover />);
    expect(screen.queryByTestId("component-assist-popover")).not.toBeInTheDocument();
  });

  it("renders with title derived from active node and an ephemeral footer", () => {
    useComponentAssistStore.setState({ activeNodeId: "n-abc" });
    render(<ComponentAssistPopover />);
    expect(screen.getByTestId("component-assist-popover")).toBeInTheDocument();
    expect(screen.getByText(/won't be saved/i)).toBeInTheDocument();
  });

  it("closes and wipes the thread when the close button is clicked", () => {
    useComponentAssistStore.setState({
      activeNodeId: "n-1",
      thread: [{ role: "user", content: "hi" }],
    });
    render(<ComponentAssistPopover />);
    fireEvent.click(screen.getByLabelText(/close/i));
    expect(useComponentAssistStore.getState().activeNodeId).toBeNull();
    expect(useComponentAssistStore.getState().thread).toEqual([]);
  });

  it("closes and wipes the thread when the current flow changes while open", () => {
    useComponentAssistStore.setState({
      activeNodeId: "n-1",
      flowId: "flow-a",
      thread: [{ role: "user", content: "hi from flow a" }],
    });
    render(<ComponentAssistPopover />);
    expect(screen.getByTestId("component-assist-popover")).toBeInTheDocument();

    act(() => {
      useFlowStore.setState({ currentFlow: { id: "flow-b" } as any });
    });

    expect(useComponentAssistStore.getState().activeNodeId).toBeNull();
    expect(useComponentAssistStore.getState().thread).toEqual([]);
    expect(screen.queryByTestId("component-assist-popover")).not.toBeInTheDocument();
  });

  it("closes after the user navigates to another flow via /all (popover unmounts and remounts)", () => {
    // Popover is open on flow A.
    useComponentAssistStore.setState({
      activeNodeId: "n-1",
      flowId: "flow-a",
      thread: [{ role: "user", content: "hi from flow a" }],
    });
    const { unmount } = render(<ComponentAssistPopover />);
    expect(screen.getByTestId("component-assist-popover")).toBeInTheDocument();

    // User clicks the ADP logo → FlowPage (and the popover) unmount.
    unmount();

    // User navigates into flow B → FlowPage remounts, currentFlow is now B.
    // The app-scoped store still holds the stale activeNodeId/thread/flowId.
    useFlowStore.setState({ currentFlow: { id: "flow-b" } as any });
    render(<ComponentAssistPopover />);

    // Popover must detect the stale flowId and close itself on mount.
    expect(useComponentAssistStore.getState().activeNodeId).toBeNull();
    expect(useComponentAssistStore.getState().thread).toEqual([]);
    expect(screen.queryByTestId("component-assist-popover")).not.toBeInTheDocument();
  });
});
