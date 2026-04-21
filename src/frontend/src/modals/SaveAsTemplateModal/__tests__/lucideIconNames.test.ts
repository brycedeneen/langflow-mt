import { describe, expect, it } from "@jest/globals";
import { LUCIDE_ICON_NAMES } from "../iconPicker/lucideIconNames";

describe("LUCIDE_ICON_NAMES", () => {
  it("returns a non-empty array of strings", () => {
    expect(Array.isArray(LUCIDE_ICON_NAMES)).toBe(true);
    expect(LUCIDE_ICON_NAMES.length).toBeGreaterThan(0);
    LUCIDE_ICON_NAMES.forEach((n) => expect(typeof n).toBe("string"));
  });

  it("count is in the expected ballpark for current lucide-react", () => {
    expect(LUCIDE_ICON_NAMES.length).toBeGreaterThan(1000);
    expect(LUCIDE_ICON_NAMES.length).toBeLessThan(3000);
  });

  it("includes well-known icon names in PascalCase", () => {
    expect(LUCIDE_ICON_NAMES).toContain("FileText");
    expect(LUCIDE_ICON_NAMES).toContain("Folder");
    expect(LUCIDE_ICON_NAMES).toContain("Database");
  });

  it("excludes lucide non-component exports", () => {
    expect(LUCIDE_ICON_NAMES).not.toContain("createLucideIcon");
    expect(LUCIDE_ICON_NAMES).not.toContain("LucideProvider");
    expect(LUCIDE_ICON_NAMES).not.toContain("Icon");
  });

  it("returns names sorted alphabetically (case-insensitive)", () => {
    const sorted = [...LUCIDE_ICON_NAMES].sort((a, b) =>
      a.toLowerCase().localeCompare(b.toLowerCase()),
    );
    expect(LUCIDE_ICON_NAMES).toEqual(sorted);
  });

  it("contains no duplicates", () => {
    expect(new Set(LUCIDE_ICON_NAMES).size).toBe(LUCIDE_ICON_NAMES.length);
  });
});
