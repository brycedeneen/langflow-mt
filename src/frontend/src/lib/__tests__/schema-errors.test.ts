import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import {
  ValidationError,
  reportParseFailure,
  configureReporter,
  _resetReporterForTest,
} from "../schema-errors";

describe("ValidationError", () => {
  it("carries id, boundary, and a readable toString()", () => {
    const zErr = new z.ZodError([{
      code: "invalid_type",
      expected: "string",
      input: undefined,
      path: ["data", "nodes", 2, "id"],
      message: "Required",
    }]);
    const err = new ValidationError("api.flows.getFlow", zErr, "http");
    expect(err.id).toBe("api.flows.getFlow");
    expect(err.boundary).toBe("http");
    expect(err.message).toContain("api.flows.getFlow");
    expect(err.message).toContain("data.nodes[2].id");
  });
});

describe("reportParseFailure", () => {
  beforeEach(() => _resetReporterForTest());

  it("invokes the configured reporter once per call", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr = new z.ZodError([]);
    reportParseFailure({ id: "a.b.c", mode: "permissive", error: zErr, raw: {}, boundary: "http" });
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("dedupes identical (id, top-level-path) pairs within 60s", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr = new z.ZodError([{
      code: "invalid_type", expected: "string", input: 0,
      path: ["data", "x"], message: "bad",
    }]);
    const payload = { id: "a.b.c", mode: "permissive" as const, error: zErr, raw: {}, boundary: "http" as const };
    reportParseFailure(payload);
    reportParseFailure(payload);
    reportParseFailure(payload);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("does not dedupe different (id, path) pairs", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr1 = new z.ZodError([{ code: "invalid_type", expected: "string", input: 0, path: ["a"], message: "" }]);
    const zErr2 = new z.ZodError([{ code: "invalid_type", expected: "string", input: 0, path: ["b"], message: "" }]);
    reportParseFailure({ id: "x.y.z", mode: "permissive", error: zErr1, raw: {}, boundary: "http" });
    reportParseFailure({ id: "x.y.z", mode: "permissive", error: zErr2, raw: {}, boundary: "http" });
    expect(reporter).toHaveBeenCalledTimes(2);
  });
});
