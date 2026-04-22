import { act, renderHook, waitFor } from "@testing-library/react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import { useComponentAssistStream } from "../hooks/use-component-assist-stream";

const SSE_OK = (chunks: string[]) => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return { ok: true, body: stream, status: 200 } as unknown as Response;
};

describe("useComponentAssistStream", () => {
  beforeEach(() => {
    useComponentAssistStore.setState({
      activeNodeId: "n1",
      anchorRect: null,
      position: { x: 0, y: 0 },
      size: { w: 0, h: 0 },
      thread: [],
      isStreaming: false,
      abortController: null,
    });
    global.fetch = jest.fn();
  });

  it("parses token events into assistant deltas", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      SSE_OK([
        'data: {"type":"token","text":"Hel"}\n',
        'data: {"type":"token","text":"lo"}\n',
        'data: {"type":"done"}\n',
      ]),
    );
    const { result } = renderHook(() => useComponentAssistStream("flow-1"));
    await act(async () => {
      await result.current.sendMessage({
        nodeSnapshot: { node_id: "n1", type: "X", display_name: "X", template: {}, outputs: [] } as any,
        neighborSnapshots: [],
        userMessage: "hi",
      });
    });
    await waitFor(() => {
      const thread = useComponentAssistStore.getState().thread;
      expect(thread[thread.length - 1]).toMatchObject({ role: "assistant", content: "Hello" });
    });
  });

  it("materializes tool_call events as proposals", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      SSE_OK([
        'data: {"type":"tool_call","name":"propose_config_update","args":{"node_id":"n1","patch":{"x":5},"rationale":"test"}}\n',
        'data: {"type":"done"}\n',
      ]),
    );
    const { result } = renderHook(() => useComponentAssistStream("flow-1"));
    await act(async () => {
      await result.current.sendMessage({
        nodeSnapshot: { node_id: "n1", type: "X", display_name: "X", template: { x: { value: 0 } }, outputs: [] } as any,
        neighborSnapshots: [],
        userMessage: "set x",
      });
    });
    const thread = useComponentAssistStore.getState().thread;
    const last = thread[thread.length - 1];
    expect(last.role).toBe("assistant");
    if (last.role !== "assistant") throw new Error("unreachable");
    expect(last.proposals?.[0].patch).toEqual({ x: 5 });
  });
});
