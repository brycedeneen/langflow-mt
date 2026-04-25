import { applyTemplateChange } from "../applyTemplateChange";
import type { APIClassType } from "@/types/api";

const baseNode = (): APIClassType =>
  ({
    template: {
      query: { type: "str", value: "hello", show: true } as any,
      count: { type: "int", value: 1, show: true } as any,
      operations: { type: "str", value: [], show: true } as any,
      filter_key: { type: "str", value: "", show: true } as any,
      operator: { type: "str", value: "", show: true } as any,
    },
    display_name: "Test Node",
  }) as unknown as APIClassType;

describe("applyTemplateChange", () => {
  it("returns a new node reference (not the input)", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result).not.toBe(node);
  });

  it("returns a new template[name] reference with the merged change", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result.template.query).not.toBe(node.template.query);
    expect(result.template.query.value).toBe("world");
  });

  it("preserves reference identity for sibling template entries (structural sharing)", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result.template.count).toBe(node.template.count);
    expect(result.template.operations).toBe(node.template.operations);
  });

  it("strips undefined entries from changes", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", {
      value: "world",
      placeholder: undefined as any,
    });
    expect(result.template.query.value).toBe("world");
    expect("placeholder" in result.template.query).toBe(
      "placeholder" in node.template.query,
    );
  });

  it("hides Data Operations operation-fields when operations is cleared and display_name matches", () => {
    const node = { ...baseNode(), display_name: "Data Operations" };
    const result = applyTemplateChange(node, "operations", { value: [] });
    expect(result.template.filter_key.show).toBe(false);
    expect(result.template.operator.show).toBe(false);
  });

  it("does NOT hide operation-fields when display_name is not Data Operations", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "operations", { value: [] });
    expect(result.template.filter_key.show).toBe(true);
    expect(result.template.operator.show).toBe(true);
  });

  it("does NOT hide operation-fields when changes.value is non-empty", () => {
    const node = { ...baseNode(), display_name: "Data Operations" };
    const result = applyTemplateChange(node, "operations", { value: ["x"] });
    expect(result.template.filter_key.show).toBe(true);
  });

  it("freezes the returned node and template in dev mode (mutations throw)", () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = "development";
    try {
      const node = baseNode();
      const result = applyTemplateChange(node, "query", { value: "world" });
      expect(() => {
        (result as any).template = {};
      }).toThrow();
      expect(() => {
        (result.template as any).query = {};
      }).toThrow();
    } finally {
      process.env.NODE_ENV = prev;
    }
  });

  it("does NOT freeze in production mode", () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = "production";
    try {
      const node = baseNode();
      const result = applyTemplateChange(node, "query", { value: "world" });
      expect(Object.isFrozen(result)).toBe(false);
    } finally {
      process.env.NODE_ENV = prev;
    }
  });
});
