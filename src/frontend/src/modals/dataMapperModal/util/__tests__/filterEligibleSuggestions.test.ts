import { filterEligibleSuggestions } from "../filterEligibleSuggestions";
import type { MapperConfig, MappingEntry } from "../../types";

const baseConfig: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true, default: null },
    { name: "email",     type: "str", required: true, default: null },
    { name: "user_id",   type: "str", required: false, default: null },
  ],
  mappings: [],
};

const proposal = (destination: string, extras: Partial<MappingEntry> = {}): MappingEntry => ({
  destination,
  transform: "direct",
  sources: [{ input: "users", field: destination }],
  config: {},
  ...extras,
});

describe("filterEligibleSuggestions", () => {
  it("keeps proposals for destinations with no existing mapping entry", () => {
    const out = filterEligibleSuggestions(baseConfig, [proposal("full_name")]);
    expect(out).toHaveLength(1);
    expect(out[0].destination).toBe("full_name");
  });

  it("keeps proposals for destinations with the default empty entry", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: {} },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(1);
  });

  it("drops proposals for customized entries (non-direct transform)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "template" as const, sources: [], config: { template: "{x}" } },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals for customized entries (non-empty sources)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const,
        sources: [{ input: "users", field: "name" }], config: {} },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals for customized entries (non-empty config)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: { foo: 1 } },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals referencing unknown destinations", () => {
    expect(filterEligibleSuggestions(baseConfig, [proposal("does_not_exist")])).toHaveLength(0);
  });

  it("drops proposals with transform: 'expression'", () => {
    expect(filterEligibleSuggestions(baseConfig, [proposal("full_name", { transform: "expression" })])).toHaveLength(0);
  });

  it("handles mixed proposals correctly", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "email", transform: "template" as const, sources: [], config: { template: "{x}" } },
    ]};
    const out = filterEligibleSuggestions(config, [
      proposal("full_name"),   // eligible — no entry
      proposal("email"),       // skip — customized
      proposal("user_id"),     // eligible — no entry
      proposal("nonexistent"), // skip — unknown dest
    ]);
    expect(out.map((e) => e.destination).sort()).toEqual(["full_name", "user_id"]);
  });
});
