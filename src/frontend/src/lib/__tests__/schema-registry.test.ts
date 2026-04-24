import { describe, it, expect, beforeEach } from "@jest/globals";
import { registerSchema, getMode, _resetForTest } from "../schema-registry";

describe("schema-registry", () => {
  beforeEach(() => _resetForTest());

  it("returns 'permissive' for an unregistered schema id", () => {
    expect(getMode("api.unknown.endpoint")).toBe("permissive");
  });

  it("returns the registered mode for a known schema id", () => {
    registerSchema("api.flows.getFlow", "strict");
    expect(getMode("api.flows.getFlow")).toBe("strict");
  });

  it("overwrites when the same id is registered twice", () => {
    registerSchema("api.flows.getFlow", "permissive");
    registerSchema("api.flows.getFlow", "strict");
    expect(getMode("api.flows.getFlow")).toBe("strict");
  });
});
