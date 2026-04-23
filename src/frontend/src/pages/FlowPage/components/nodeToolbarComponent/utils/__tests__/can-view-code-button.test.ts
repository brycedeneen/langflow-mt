import { canViewCodeButton } from "../can-view-code-button";

describe("canViewCodeButton", () => {
  it("returns false when the component has no code field", () => {
    expect(canViewCodeButton({ hasCode: false, isSuperuser: true })).toBe(false);
  });

  it("returns false for a non-superuser even if the component has code", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: false })).toBe(false);
  });

  it("returns true for a superuser on a component with code", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: true })).toBe(true);
  });

  it("ignores an undefined superuser flag (treated as non-super)", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: undefined })).toBe(false);
  });
});
