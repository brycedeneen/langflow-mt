import { describe, it, expect, beforeEach } from "@jest/globals";
import { z } from "zod";
import useValidationErrorStore from "../validationErrorStore";

describe("validationErrorStore", () => {
  beforeEach(() => {
    useValidationErrorStore.setState({ errors: [], mutedIds: new Set() });
    sessionStorage.clear();
  });

  it("push adds an error to the front", () => {
    const z1 = new z.ZodError([]);
    useValidationErrorStore.getState().push({ id: "a", boundary: "http", mode: "permissive", error: z1, raw: null, at: Date.now() });
    expect(useValidationErrorStore.getState().errors).toHaveLength(1);
  });

  it("mute persists via sessionStorage", () => {
    useValidationErrorStore.getState().mute("a");
    expect(sessionStorage.getItem("dto.mutedSchemaIds")).toContain("a");
  });

  it("filters out muted ids on push", () => {
    useValidationErrorStore.getState().mute("a");
    const z1 = new z.ZodError([]);
    useValidationErrorStore.getState().push({ id: "a", boundary: "http", mode: "permissive", error: z1, raw: null, at: Date.now() });
    expect(useValidationErrorStore.getState().errors).toHaveLength(0);
  });
});
