import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedQueryFn, validatedMutationFn } from "../validated-fetch";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { ValidationError, configureReporter, _resetReporterForTest } from "../schema-errors";

const FlowSchema = z.object({ id: z.string(), name: z.string() });

describe("validatedQueryFn", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("returns parsed data on happy path (permissive)", async () => {
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema,
      async () => ({ id: "1", name: "x" }));
    const result = await fn();
    expect(result).toEqual({ id: "1", name: "x" });
  });

  it("passes through raw data + reports on permissive bad shape", async () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const bad = { id: 1, name: "x" }; // id should be string
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema, async () => bad);
    const result = await fn();
    expect(result).toEqual(bad);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("throws ValidationError on strict bad shape", async () => {
    registerSchema("api.flows.getFlow", "strict");
    const reporter = jest.fn();
    configureReporter(reporter);
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema,
      async () => ({ id: 1, name: "x" }));
    await expect(fn()).rejects.toBeInstanceOf(ValidationError);
    expect(reporter).toHaveBeenCalledTimes(1);
  });
});

describe("validatedMutationFn", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("validates request body before the call fires (strict)", async () => {
    registerSchema("api.flows.updateFlow", "strict");
    const ReqSchema = z.object({ name: z.string() });
    const ResSchema = z.object({ id: z.string() });
    const call = jest.fn<(b: unknown) => Promise<unknown>>(async () => ({ id: "1" }));
    const mut = validatedMutationFn("api.flows.updateFlow", ReqSchema, ResSchema, call);
    // @ts-expect-error intentional wrong type
    await expect(mut({ name: 42 })).rejects.toBeInstanceOf(ValidationError);
    expect(call).not.toHaveBeenCalled();
  });

  it("validates response on return (strict)", async () => {
    registerSchema("api.flows.updateFlow", "strict");
    const ReqSchema = z.object({ name: z.string() });
    const ResSchema = z.object({ id: z.string() });
    const mut = validatedMutationFn("api.flows.updateFlow", ReqSchema, ResSchema,
      async () => ({ id: 42 }));
    await expect(mut({ name: "x" })).rejects.toBeInstanceOf(ValidationError);
  });
});
