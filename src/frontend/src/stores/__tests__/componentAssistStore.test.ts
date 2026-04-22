import { act, renderHook } from "@testing-library/react";

import useComponentAssistStore from "../componentAssistStore";

describe("componentAssistStore", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: null,
      anchorRect: null,
      position: { x: 0, y: 0 },
      size: { w: 420, h: 500 },
      thread: [],
      isStreaming: false,
    });
  });

  it("opens with activeNodeId and position derived from anchor", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    const rect = { top: 100, left: 200, bottom: 140, right: 280, width: 80, height: 40, x: 200, y: 100, toJSON: () => ({}) } as DOMRect;
    act(() => {
      result.current.open("node-a", rect);
    });
    expect(result.current.activeNodeId).toBe("node-a");
    expect(result.current.anchorRect).toBe(rect);
    expect(result.current.thread).toEqual([]);
  });

  it("closes and wipes the thread", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    act(() => {
      result.current.open("node-a", null);
      result.current.appendUserMessage("hi");
    });
    expect(result.current.thread.length).toBe(1);
    act(() => {
      result.current.close();
    });
    expect(result.current.activeNodeId).toBeNull();
    expect(result.current.thread).toEqual([]);
  });

  it("appendAssistantDelta merges into the trailing assistant message", () => {
    const { result } = renderHook(() => useComponentAssistStore());
    act(() => {
      result.current.open("n", null);
      result.current.appendUserMessage("hi");
      result.current.appendAssistantDelta("Hel");
      result.current.appendAssistantDelta("lo!");
    });
    const last = result.current.thread[result.current.thread.length - 1];
    expect(last.role).toBe("assistant");
    expect(last.content).toBe("Hello!");
  });
});
