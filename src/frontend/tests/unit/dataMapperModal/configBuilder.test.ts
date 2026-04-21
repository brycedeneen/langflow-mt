import {
  addDestinationField,
  removeDestinationField,
  setTransformForDestination,
  setSourcesForDestination,
  addInput,
  setDriverIndex,
  setJoinKey,
  addJoinKey,
  removeJoinKey,
} from "@/modals/dataMapperModal/util/configBuilder";
import { EMPTY_MAPPER_CONFIG, MapperConfig } from "@/modals/dataMapperModal/types";

test("addDestinationField appends and defaults to direct transform", () => {
  const next = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "External_ID", type: "str", required: true, default: null });
  expect(next.destination_schema).toHaveLength(1);
  expect(next.mappings).toHaveLength(1);
  expect(next.mappings[0]).toMatchObject({ destination: "External_ID", transform: "direct" });
});

test("removeDestinationField removes both the schema entry and the mapping", () => {
  const withOne = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "External_ID", type: "str", required: true, default: null });
  const cleaned = removeDestinationField(withOne, "External_ID");
  expect(cleaned.destination_schema).toHaveLength(0);
  expect(cleaned.mappings).toHaveLength(0);
});

test("setTransformForDestination resets config and sources appropriately", () => {
  const start = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "Region", type: "str", required: false, default: "" });
  const asStatic = setTransformForDestination(start, "Region", "static");
  expect(asStatic.mappings[0].transform).toBe("static");
  expect(asStatic.mappings[0].sources).toEqual([]);
  expect(asStatic.mappings[0].config).toEqual({ value: "" });
});

test("setSourcesForDestination replaces the sources array", () => {
  const start = addDestinationField(EMPTY_MAPPER_CONFIG, { name: "Name", type: "str", required: false, default: "" });
  const withSources = setSourcesForDestination(start, "Name", [
    { input: "workers", field: "first_name" },
    { input: "workers", field: "last_name" },
  ]);
  expect(withSources.mappings[0].sources).toHaveLength(2);
});

test("addInput preserves driver_index when adding a lookup", () => {
  const withDriver = addInput(EMPTY_MAPPER_CONFIG, { alias: "workers", schema_source: "autodetect", schema: { fields: [] } });
  const withLookup = addInput(withDriver, { alias: "jobs", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "job_id", lookup_field: "id" }] } });
  expect(withLookup.driver_index).toBe(0);
  expect(withLookup.inputs).toHaveLength(2);
});

test("setDriverIndex in range is accepted; out of range is rejected", () => {
  const withTwo = addInput(addInput(EMPTY_MAPPER_CONFIG, { alias: "a", schema_source: "autodetect", schema: { fields: [] } }), { alias: "b", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "x", lookup_field: "y" }] } });
  expect(setDriverIndex(withTwo, 1).driver_index).toBe(1);
  expect(() => setDriverIndex(withTwo, 5)).toThrow(/out of range/);
});

test("addJoinKey / setJoinKey / removeJoinKey operate on the target input", () => {
  const cfg = addInput(addInput(EMPTY_MAPPER_CONFIG, { alias: "workers", schema_source: "autodetect", schema: { fields: [] } }), { alias: "jobs", schema_source: "autodetect", schema: { fields: [] }, join: { on: [{ driver_field: "x", lookup_field: "y" }] } });
  const added = addJoinKey(cfg, "jobs", { driver_field: "", lookup_field: "" });
  expect(added.inputs[1].join!.on).toHaveLength(2);
  const setted = setJoinKey(added, "jobs", 1, { driver_field: "org_id", lookup_field: "org_id" });
  expect(setted.inputs[1].join!.on[1]).toEqual({ driver_field: "org_id", lookup_field: "org_id" });
  const removed = removeJoinKey(setted, "jobs", 0);
  expect(removed.inputs[1].join!.on).toHaveLength(1);
});
