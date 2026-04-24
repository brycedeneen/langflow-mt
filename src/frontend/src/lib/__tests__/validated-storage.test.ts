import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedStorage } from "../validated-storage";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const SliceSchema = z.object({ count: z.number() });

function makeBase() {
  const store = new Map<string, string>();
  return {
    get length() { return store.size; },
    key: jest.fn<(i: number) => string | null>((i) => [...store.keys()][i] ?? null),
    getItem: jest.fn<(k: string) => string | null>((k) => store.get(k) ?? null),
    setItem: jest.fn<(k: string, v: string) => void>((k, v) => { store.set(k, v); }),
    removeItem: jest.fn<(k: string) => void>((k) => { store.delete(k); }),
    clear: jest.fn<() => void>(() => { store.clear(); }),
  };
}

describe("validatedStorage", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("returns null when the key is missing", () => {
    const base = makeBase();
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
  });

  it("returns null on malformed JSON", () => {
    const base = makeBase();
    base.setItem("k", "not json");
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
  });

  it("passes through bad shape in permissive mode + reports", () => {
    const base = makeBase();
    base.setItem("k", JSON.stringify({ count: "nope" }));
    const reporter = jest.fn();
    configureReporter(reporter);
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBe(JSON.stringify({ count: "nope" }));
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("clears the key and returns null on bad shape in strict mode", () => {
    registerSchema("storage.slice", "strict");
    const base = makeBase();
    base.setItem("k", JSON.stringify({ count: "nope" }));
    const reporter = jest.fn();
    configureReporter(reporter);
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
    expect(base.removeItem).toHaveBeenCalledWith("k");
    expect(reporter).toHaveBeenCalledTimes(1);
  });
});
