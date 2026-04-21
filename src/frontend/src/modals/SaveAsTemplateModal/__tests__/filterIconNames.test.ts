import { describe, expect, it } from "@jest/globals";
import { filterIconNames } from "../iconPicker/filterIconNames";

describe("filterIconNames", () => {
  const NAMES = ["Anchor", "Folder", "FolderOpen", "Database", "FileText", "Brain"];

  it("returns the input list unchanged when query is empty", () => {
    expect(filterIconNames(NAMES, "")).toEqual(NAMES);
    expect(filterIconNames(NAMES, "   ")).toEqual(NAMES);
  });

  it("filters by case-insensitive substring", () => {
    expect(filterIconNames(NAMES, "fold")).toEqual(["Folder", "FolderOpen"]);
    expect(filterIconNames(NAMES, "FOLD")).toEqual(["Folder", "FolderOpen"]);
  });

  it("ranks starts-with matches above mid-string matches", () => {
    const result = filterIconNames(["BookOpen", "Notebook", "Book"], "book");
    // Starts-with: "BookOpen", "Book"; mid-string: "Notebook"
    expect(result.indexOf("BookOpen")).toBeLessThan(result.indexOf("Notebook"));
    expect(result.indexOf("Book")).toBeLessThan(result.indexOf("Notebook"));
  });

  it("preserves alphabetical order within the same rank tier", () => {
    const result = filterIconNames(["Folder", "FolderOpen", "FolderClosed"], "folder");
    // All start with "folder"; sorted: Folder, FolderClosed, FolderOpen
    expect(result).toEqual(["Folder", "FolderClosed", "FolderOpen"]);
  });

  it("returns an empty list when no name matches", () => {
    expect(filterIconNames(NAMES, "zzzzz-no-match")).toEqual([]);
  });
});
