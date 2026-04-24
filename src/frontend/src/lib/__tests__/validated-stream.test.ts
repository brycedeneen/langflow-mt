import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedEventStream } from "../validated-stream";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const EventSchema = z.object({ type: z.literal("ping"), seq: z.number() });

type FakeEventSource = {
  onmessage: ((e: { data: string }) => void) | null;
  dispatch: (data: string) => void;
};

function makeSource(): FakeEventSource {
  return {
    onmessage: null,
    dispatch(data) { this.onmessage?.({ data }); },
  };
}

describe("validatedEventStream", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("invokes onMessage with parsed data on valid event", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage);
    src.dispatch(JSON.stringify({ type: "ping", seq: 1 }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: 1 });
  });

  it("invokes onInvalid + reports on malformed JSON", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage, onInvalid);
    src.dispatch("not json");
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });

  it("passes raw through onMessage in permissive mode on bad shape", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage);
    src.dispatch(JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: "oops" });
  });

  it("invokes onInvalid in strict mode on bad shape", () => {
    registerSchema("stream.ping", "strict");
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage, onInvalid);
    src.dispatch(JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });
});
