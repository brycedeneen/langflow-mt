import { areInputPropsEqual } from "../areInputPropsEqual";

describe("areInputPropsEqual", () => {
  it("returns true for the same object reference", () => {
    const props = { id: "a", value: 1 };
    expect(areInputPropsEqual(props, props)).toBe(true);
  });

  it("returns true when all compared props are Object.is-equal", () => {
    const a = { id: "a", value: 1, disabled: false };
    const b = { id: "a", value: 1, disabled: false };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("returns false when a non-skipped prop differs", () => {
    const a = { id: "a", value: 1 };
    const b = { id: "a", value: 2 };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("ignores handleOnNewValue identity (treats different refs as equal)", () => {
    const a = { id: "a", value: 1, handleOnNewValue: () => undefined };
    const b = { id: "a", value: 1, handleOnNewValue: () => undefined };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("ignores nodeClass identity (treats different refs as equal)", () => {
    const a = { id: "a", value: 1, nodeClass: { template: {} } as any };
    const b = { id: "a", value: 1, nodeClass: { template: {} } as any };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("returns false when prev has more keys than next", () => {
    const a = { id: "a", value: 1, extra: true };
    const b = { id: "a", value: 1 };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("returns false when next has more keys than prev", () => {
    const a = { id: "a", value: 1 };
    const b = { id: "a", value: 1, extra: true };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("uses Object.is semantics (NaN equals NaN, +0 ≠ -0)", () => {
    expect(areInputPropsEqual({ x: NaN }, { x: NaN })).toBe(true);
    expect(areInputPropsEqual({ x: +0 }, { x: -0 })).toBe(false);
  });
});
