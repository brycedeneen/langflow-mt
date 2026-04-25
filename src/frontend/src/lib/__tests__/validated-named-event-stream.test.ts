import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedNamedEventStream } from "../validated-named-event-stream";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const PingSchema = z.object({ type: z.literal("ping"), seq: z.number() });

type Listener = (event: Event) => void;

type FakeEventSource = {
  listeners: Map<string, Listener[]>;
  addEventListener: jest.Mock<(name: string, handler: Listener) => void>;
  removeEventListener: jest.Mock<(name: string, handler: Listener) => void>;
  dispatch: (eventName: string, data: string) => void;
};

function makeSource(): FakeEventSource {
  const listeners = new Map<string, Listener[]>();
  const src: FakeEventSource = {
    listeners,
    addEventListener: jest.fn((name: string, handler: Listener) => {
      const existing = listeners.get(name) ?? [];
      listeners.set(name, [...existing, handler]);
    }),
    removeEventListener: jest.fn((name: string, handler: Listener) => {
      const existing = listeners.get(name) ?? [];
      listeners.set(name, existing.filter((h) => h !== handler));
    }),
    dispatch(eventName: string, data: string) {
      const handlers = listeners.get(eventName) ?? [];
      const event = Object.assign(new Event(eventName), { data });
      for (const h of handlers) h(event);
    },
  };
  return src;
}

describe("validatedNamedEventStream", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("invokes onMessage with parsed data on valid named event", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage);
    src.dispatch("ping", JSON.stringify({ type: "ping", seq: 1 }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: 1 });
  });

  it("invokes onInvalid + reporter on malformed JSON", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage, onInvalid);
    src.dispatch("ping", "not valid json {{{");
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("passes raw through onMessage in permissive mode on bad shape", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    // default mode is permissive
    validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage);
    src.dispatch("ping", JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: "oops" });
  });

  it("invokes onInvalid in strict mode on bad shape", () => {
    registerSchema("stream.ping", "strict");
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage, onInvalid);
    src.dispatch("ping", JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });

  it("returned cleanup function removes the event listener", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    const cleanup = validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage);
    expect(src.addEventListener).toHaveBeenCalledTimes(1);
    cleanup();
    expect(src.removeEventListener).toHaveBeenCalledTimes(1);
    // after cleanup, dispatching should not call onMessage
    src.dispatch("ping", JSON.stringify({ type: "ping", seq: 2 }));
    expect(onMessage).not.toHaveBeenCalled();
  });

  it("does not call handler for different event names", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedNamedEventStream("stream.ping", PingSchema, src as unknown as EventSource, "ping", onMessage);
    src.dispatch("other", JSON.stringify({ type: "ping", seq: 1 }));
    expect(onMessage).not.toHaveBeenCalled();
  });
});
