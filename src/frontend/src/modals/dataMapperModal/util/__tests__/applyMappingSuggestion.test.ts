import { applyMappingSuggestion } from "../applyMappingSuggestion";
import type { MapperConfig, MappingEntry } from "../../types";

const baseConfig: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true, default: null },
    { name: "email",     type: "str", required: true, default: null },
  ],
  mappings: [],
};

const entry: MappingEntry = {
  destination: "full_name",
  transform: "template",
  sources: [
    { input: "users", field: "first_name" },
    { input: "users", field: "last_name" },
  ],
  config: { template: "{first_name} {last_name}" },
};

describe("applyMappingSuggestion", () => {
  it("appends when the destination has no existing entry", () => {
    const out = applyMappingSuggestion(baseConfig, entry);
    expect(out.mappings).toHaveLength(1);
    expect(out.mappings[0]).toEqual(entry);
  });

  it("replaces when the destination has a default empty entry", () => {
    const input = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: {} },
    ]};
    const out = applyMappingSuggestion(input, entry);
    expect(out.mappings).toHaveLength(1);
    expect(out.mappings[0]).toEqual(entry);
  });

  it("does not mutate the input config", () => {
    const input: MapperConfig = JSON.parse(JSON.stringify(baseConfig));
    applyMappingSuggestion(input, entry);
    expect(input.mappings).toHaveLength(0);
  });

  it("leaves other mappings alone", () => {
    const otherEntry: MappingEntry = {
      destination: "email", transform: "direct",
      sources: [{ input: "users", field: "email_address" }], config: {},
    };
    const input = { ...baseConfig, mappings: [otherEntry] };
    const out = applyMappingSuggestion(input, entry);
    expect(out.mappings).toHaveLength(2);
    expect(out.mappings).toContainEqual(otherEntry);
    expect(out.mappings).toContainEqual(entry);
  });
});
