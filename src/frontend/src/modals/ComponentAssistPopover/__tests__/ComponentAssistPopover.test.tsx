import { fireEvent, render, screen } from "@testing-library/react";

import useComponentAssistStore from "@/stores/componentAssistStore";
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
});
