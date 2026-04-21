import { useCallback, useState } from "react";

export const RECENT_ICONS_STORAGE_KEY = "langflow.template.recentIcons";
export const RECENT_ICONS_CAP = 8;

function readFromStorage(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_ICONS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is string => typeof v === "string").slice(0, RECENT_ICONS_CAP);
  } catch {
    return [];
  }
}

function writeToStorage(list: string[]): void {
  try {
    window.localStorage.setItem(RECENT_ICONS_STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage may be unavailable (Safari private mode) or quota-exceeded.
    // Swallow — the in-memory state is still correct for the current session.
  }
}

export function useRecentIcons(): {
  recents: string[];
  record: (name: string) => void;
} {
  const [recents, setRecents] = useState<string[]>(() => readFromStorage());

  const record = useCallback((name: string) => {
    setRecents((prev) => {
      const deduped = [name, ...prev.filter((n) => n !== name)].slice(
        0,
        RECENT_ICONS_CAP,
      );
      writeToStorage(deduped);
      return deduped;
    });
  }, []);

  return { recents, record };
}
