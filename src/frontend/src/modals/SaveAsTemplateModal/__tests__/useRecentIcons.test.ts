import { describe, expect, it, beforeEach, jest } from "@jest/globals";
import { act, renderHook } from "@testing-library/react";
import { useRecentIcons, RECENT_ICONS_STORAGE_KEY, RECENT_ICONS_CAP } from "../iconPicker/useRecentIcons";

describe("useRecentIcons", () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.restoreAllMocks();
  });

  it("returns an empty list when storage is empty", () => {
    const { result } = renderHook(() => useRecentIcons());
    expect(result.current.recents).toEqual([]);
  });

  it("record adds the name to the head of the list", () => {
    const { result } = renderHook(() => useRecentIcons());
    act(() => result.current.record("FileText"));
    expect(result.current.recents).toEqual(["FileText"]);
  });

  it("recording the same name twice deduplicates and moves it to the head", () => {
    const { result } = renderHook(() => useRecentIcons());
    act(() => result.current.record("Folder"));
    act(() => result.current.record("FileText"));
    act(() => result.current.record("Folder"));
    expect(result.current.recents).toEqual(["Folder", "FileText"]);
  });

  it(`caps stored recents at ${RECENT_ICONS_CAP}`, () => {
    const { result } = renderHook(() => useRecentIcons());
    for (let i = 0; i < RECENT_ICONS_CAP + 3; i++) {
      act(() => result.current.record(`Icon${i}`));
    }
    expect(result.current.recents.length).toBe(RECENT_ICONS_CAP);
    // Most recent at head, oldest evicted
    expect(result.current.recents[0]).toBe(`Icon${RECENT_ICONS_CAP + 2}`);
    expect(result.current.recents).not.toContain("Icon0");
  });

  it("persists across hook re-mounts via localStorage", () => {
    const first = renderHook(() => useRecentIcons());
    act(() => first.result.current.record("Database"));
    first.unmount();

    const second = renderHook(() => useRecentIcons());
    expect(second.result.current.recents).toEqual(["Database"]);
  });

  it("returns [] when stored value is malformed JSON, then overwrites cleanly on next record", () => {
    window.localStorage.setItem(RECENT_ICONS_STORAGE_KEY, "{not valid json");
    const { result } = renderHook(() => useRecentIcons());
    expect(result.current.recents).toEqual([]);

    act(() => result.current.record("Folder"));
    expect(result.current.recents).toEqual(["Folder"]);
    expect(window.localStorage.getItem(RECENT_ICONS_STORAGE_KEY)).toBe(
      JSON.stringify(["Folder"]),
    );
  });

  it("does not throw when localStorage.setItem fails (quota exceeded)", () => {
    const setItem = jest
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceededError");
      });
    const { result } = renderHook(() => useRecentIcons());
    act(() => result.current.record("Database"));
    expect(result.current.recents).toEqual(["Database"]);
    setItem.mockRestore();
  });
});
