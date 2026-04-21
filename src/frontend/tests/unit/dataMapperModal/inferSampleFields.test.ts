import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";

test("flat object infers each field to its primitive type", () => {
  expect(inferSampleFields({ name: "Ada", age: 36, active: true })).toEqual([
    { name: "name", type: "str", required: false },
    { name: "age", type: "int", required: false },
    { name: "active", type: "bool", required: false },
  ]);
});

test("float vs int is inferred", () => {
  expect(inferSampleFields({ ratio: 0.5, count: 3 })).toEqual([
    { name: "ratio", type: "float", required: false },
    { name: "count", type: "int", required: false },
  ]);
});

test("array field becomes 'list'; nested object becomes 'dict'", () => {
  expect(inferSampleFields({ tags: ["x", "y"], meta: { a: 1 } })).toEqual([
    { name: "tags", type: "list", required: false },
    { name: "meta", type: "dict", required: false },
  ]);
});

test("null field falls back to 'str'", () => {
  expect(inferSampleFields({ nope: null })).toEqual([
    { name: "nope", type: "str", required: false },
  ]);
});

test("list of objects uses the first object to infer a shape", () => {
  expect(inferSampleFields([{ a: 1, b: "x" }])).toEqual([
    { name: "a", type: "int", required: false },
    { name: "b", type: "str", required: false },
  ]);
});

test("empty list returns empty fields", () => {
  expect(inferSampleFields([])).toEqual([]);
});

test("ISO datetime string infers datetime", () => {
  expect(inferSampleFields({ at: "2026-04-21T10:00:00Z" })).toEqual([
    { name: "at", type: "datetime", required: false },
  ]);
});
