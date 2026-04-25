import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedSocket } from "../validated-socket";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const MsgSchema = z.object({ type: z.string(), payload: z.number() });

type FakeWebSocket = {
  onmessage: ((event: { data: unknown }) => void) | null;
  dispatch: (data: unknown) => void;
};

function makeSocket(): FakeWebSocket {
  return {
    onmessage: null,
    dispatch(data) {
      this.onmessage?.({ data });
    },
  };
}

describe("validatedSocket", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("invokes onMessage with parsed data on valid message", () => {
    const ws = makeSocket();
    const onMessage = jest.fn();
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage);
    ws.dispatch(JSON.stringify({ type: "hello", payload: 42 }));
    expect(onMessage).toHaveBeenCalledWith({ type: "hello", payload: 42 });
  });

  it("invokes onInvalid + reporter on malformed JSON", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const ws = makeSocket();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage, onInvalid);
    ws.dispatch("not valid json {{{");
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("passes raw through onMessage in permissive mode on bad shape", () => {
    const ws = makeSocket();
    const onMessage = jest.fn();
    // default mode is permissive
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage);
    ws.dispatch(JSON.stringify({ type: "hello", payload: "oops" }));
    expect(onMessage).toHaveBeenCalledWith({ type: "hello", payload: "oops" });
  });

  it("invokes onInvalid in strict mode on bad shape", () => {
    registerSchema("stream.ws", "strict");
    const ws = makeSocket();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage, onInvalid);
    ws.dispatch(JSON.stringify({ type: "hello", payload: "oops" }));
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });

  it("routes binary (non-string) data to onInvalid via empty-string coercion", () => {
    const ws = makeSocket();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage, onInvalid);
    // simulate binary Blob/ArrayBuffer — typeof !== "string", coerced to ""
    ws.dispatch(new ArrayBuffer(4));
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });

  it("sets socket.onmessage (replaces it)", () => {
    const ws = makeSocket();
    const originalOnMessage = jest.fn();
    ws.onmessage = originalOnMessage;
    const onMessage = jest.fn();
    validatedSocket("stream.ws", MsgSchema, ws as unknown as WebSocket, onMessage);
    expect(ws.onmessage).not.toBe(originalOnMessage);
    expect(ws.onmessage).toBeInstanceOf(Function);
  });
});
