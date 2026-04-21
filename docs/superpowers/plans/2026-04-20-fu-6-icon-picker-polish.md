# FU-6 — Icon Picker Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project commit policy:** This repo follows a strict "no git commits without explicit user approval" rule. Every Step labeled **Commit** in this plan REQUIRES the executing agent to pause and ask the user before running `git commit`. Do NOT auto-commit even if the plan says "commit".

**Goal:** Replace the placeholder `IconPickerField` in `SaveAsTemplateModal` with a polished picker that renders real icons, virtualizes the full ~1900-icon lucide set, supports keyboard navigation, and remembers the user's 8 most-recent picks.

**Architecture:** All changes colocated under `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/`. The picker uses cmdk (already in the dep tree via `@/components/ui/command`) for the search input + accessible chrome with `shouldFilter={false}`, and a custom `react-window`-virtualized grid for the icon cells. A small `useRecentIcons` hook persists the LRU recent-icon list in `localStorage`. The picker's public API stays `{ value: string; onChange: (name: string) => void }` so the parent modal needs no changes.

**Tech Stack:** React + TypeScript + Jest + React Testing Library, lucide-react (existing), cmdk (existing via `@/components/ui/command`), `react-window` (NEW dep added in Task 1).

**Spec:** [`docs/superpowers/specs/2026-04-20-fu-6-icon-picker-polish-design.md`](../specs/2026-04-20-fu-6-icon-picker-polish-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/frontend/package.json` | modify | Add `react-window` and `@types/react-window` deps |
| `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/lucideIconNames.ts` | create | Build the canonical PascalCase icon-name list from lucide's `dynamicIconImports` |
| `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/useRecentIcons.ts` | create | Hook over `localStorage` for the most-recent 8 picked icons (LRU, deduped, quota-safe) |
| `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/filterIconNames.ts` | create | Pure helper: substring match + starts-with boost ranking |
| `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/IconGrid.tsx` | create | Virtualized 6-column icon grid with arrow-key navigation |
| `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx` | rewrite | Trigger button + Popover wrapper composing the units above |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts` | create | Source-list sanity tests |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts` | create | Hook unit tests |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts` | create | Filter helper unit tests |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx` | rewrite | Component tests; mocks `react-window` so grid renders all items in jsdom |

---

## Task 1: Add `react-window` and create the lucide icon-name list

**Files:**
- Modify: `src/frontend/package.json`
- Create: `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/lucideIconNames.ts`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts`

- [ ] **Step 1: Add dependencies**

In `src/frontend/package.json`, add `"react-window": "^1.8.10"` to `dependencies` and `"@types/react-window": "^1.8.8"` to `devDependencies` (alphabetical placement). Then install:

```bash
cd src/frontend && npm install
```

Expected: `node_modules/react-window/` and `node_modules/@types/react-window/` exist after install. No other lockfile changes besides the two new entries and their transitive deps.

- [ ] **Step 2: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts`:

```typescript
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
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts
```

Expected: FAIL with `Cannot find module '../iconPicker/lucideIconNames'`.

- [ ] **Step 4: Implement `lucideIconNames.ts`**

Create `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/lucideIconNames.ts`:

```typescript
import dynamicIconImports from "lucide-react/dynamicIconImports";

// lucide ships dynamicIconImports as the authoritative kebab-case map of
// every renderable icon component. Convert to PascalCase to match the
// names used by the existing IconComponent renderer.
function toPascalCase(kebab: string): string {
  return kebab
    .split("-")
    .map((part) => (part.length > 0 ? part[0].toUpperCase() + part.slice(1) : ""))
    .join("");
}

export const LUCIDE_ICON_NAMES: string[] = Object.keys(dynamicIconImports)
  .map(toPascalCase)
  .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts
```

Expected: 6 tests pass.

- [ ] **Step 6: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/package.json src/frontend/package-lock.json src/frontend/src/modals/SaveAsTemplateModal/iconPicker/lucideIconNames.ts src/frontend/src/modals/SaveAsTemplateModal/__tests__/lucideIconNames.test.ts
git commit -m "feat(icon-picker): add react-window dep + canonical lucide icon-name list"
```

---

## Task 2: `useRecentIcons` hook

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/useRecentIcons.ts`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts`:

```typescript
import { describe, expect, it, beforeEach, jest } from "@jest/globals";
import { act, renderHook } from "@testing-library/react";
import { useRecentIcons, RECENT_ICONS_STORAGE_KEY, RECENT_ICONS_CAP } from "../iconPicker/useRecentIcons";

describe("useRecentIcons", () => {
  beforeEach(() => {
    window.localStorage.clear();
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

  it("returns [] when stored value is malformed JSON", () => {
    window.localStorage.setItem(RECENT_ICONS_STORAGE_KEY, "{not valid json");
    const { result } = renderHook(() => useRecentIcons());
    expect(result.current.recents).toEqual([]);
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts
```

Expected: FAIL with `Cannot find module '../iconPicker/useRecentIcons'`.

- [ ] **Step 3: Implement `useRecentIcons.ts`**

Create `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/useRecentIcons.ts`:

```typescript
import { useCallback, useEffect, useState } from "react";

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

  // Re-read on mount in case storage was modified by another tab/component.
  useEffect(() => {
    setRecents(readFromStorage());
  }, []);

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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/iconPicker/useRecentIcons.ts src/frontend/src/modals/SaveAsTemplateModal/__tests__/useRecentIcons.test.ts
git commit -m "feat(icon-picker): add useRecentIcons localStorage-backed LRU hook"
```

---

## Task 3: `filterIconNames` helper

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/filterIconNames.ts`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts
```

Expected: FAIL with `Cannot find module '../iconPicker/filterIconNames'`.

- [ ] **Step 3: Implement `filterIconNames.ts`**

Create `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/filterIconNames.ts`:

```typescript
/**
 * Substring-match filter with a starts-with boost.
 * Names that start with the query rank above mid-string matches.
 * Within each rank tier, results are alphabetical (case-insensitive).
 */
export function filterIconNames(names: string[], query: string): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return names;

  const startsWith: string[] = [];
  const contains: string[] = [];

  for (const name of names) {
    const lower = name.toLowerCase();
    if (lower.startsWith(q)) {
      startsWith.push(name);
    } else if (lower.includes(q)) {
      contains.push(name);
    }
  }

  const cmp = (a: string, b: string) =>
    a.toLowerCase().localeCompare(b.toLowerCase());
  startsWith.sort(cmp);
  contains.sort(cmp);

  return [...startsWith, ...contains];
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/iconPicker/filterIconNames.ts src/frontend/src/modals/SaveAsTemplateModal/__tests__/filterIconNames.test.ts
git commit -m "feat(icon-picker): add filterIconNames helper with starts-with boost"
```

---

## Task 4: `IconGrid` virtualized grid

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/IconGrid.tsx`

> **Note:** `IconGrid` is exercised by Task 5's component tests through the `IconPickerField` integration. There is no standalone test file for it — `react-window`'s `FixedSizeGrid` measures DOM size, which jsdom returns as `0`, so a standalone test would render zero cells and have nothing meaningful to assert. The Task 5 test file mocks `react-window` so the grid behavior surfaces in the integrated tests.

- [ ] **Step 1: Implement `IconGrid.tsx`**

Create `src/frontend/src/modals/SaveAsTemplateModal/iconPicker/IconGrid.tsx`:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { FixedSizeGrid, type GridChildComponentProps } from "react-window";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

const COLUMN_COUNT = 6;
const CELL_SIZE = 40;
const GRID_HEIGHT = 240;
const GRID_WIDTH = 6 * CELL_SIZE;

type Props = {
  names: string[];
  selected: string;
  onSelect: (name: string) => void;
  /** Auto-focus the first cell when this becomes true (e.g. after Tab from search input). */
  autoFocus?: boolean;
};

export default function IconGrid({ names, selected, onSelect, autoFocus }: Props) {
  const [focusIndex, setFocusIndex] = useState<number>(() => {
    const i = names.indexOf(selected);
    return i >= 0 ? i : 0;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<FixedSizeGrid>(null);

  // Re-clamp focus when the names list changes (e.g. user types and filtered set shrinks).
  useEffect(() => {
    if (focusIndex >= names.length) {
      setFocusIndex(Math.max(0, names.length - 1));
    }
  }, [names.length, focusIndex]);

  // Scroll the focused cell into view as it changes.
  useEffect(() => {
    const rowIndex = Math.floor(focusIndex / COLUMN_COUNT);
    const columnIndex = focusIndex % COLUMN_COUNT;
    gridRef.current?.scrollToItem({ rowIndex, columnIndex, align: "smart" });
  }, [focusIndex]);

  useEffect(() => {
    if (autoFocus) containerRef.current?.focus();
  }, [autoFocus]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (names.length === 0) return;
      const lastIndex = names.length - 1;
      let next = focusIndex;
      switch (e.key) {
        case "ArrowRight":
          next = Math.min(lastIndex, focusIndex + 1);
          break;
        case "ArrowLeft":
          next = Math.max(0, focusIndex - 1);
          break;
        case "ArrowDown":
          next = Math.min(lastIndex, focusIndex + COLUMN_COUNT);
          break;
        case "ArrowUp":
          next = Math.max(0, focusIndex - COLUMN_COUNT);
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = lastIndex;
          break;
        case "Enter":
        case " ":
          e.preventDefault();
          onSelect(names[focusIndex]);
          return;
        default:
          return;
      }
      e.preventDefault();
      setFocusIndex(next);
    },
    [focusIndex, names, onSelect],
  );

  const Cell = useCallback(
    ({ columnIndex, rowIndex, style }: GridChildComponentProps) => {
      const index = rowIndex * COLUMN_COUNT + columnIndex;
      if (index >= names.length) return null;
      const name = names[index];
      const isSelected = name === selected;
      const isFocused = index === focusIndex;
      return (
        <button
          type="button"
          role="option"
          aria-selected={isSelected}
          tabIndex={-1}
          onClick={() => onSelect(name)}
          style={style}
          className={cn(
            "flex items-center justify-center rounded-sm",
            isSelected && "bg-accent text-accent-foreground",
            isFocused && "ring-2 ring-primary ring-inset",
          )}
          title={name}
        >
          <IconComponent name={name} className="h-5 w-5" />
        </button>
      );
    },
    [names, selected, focusIndex, onSelect],
  );

  if (names.length === 0) return null;

  const rowCount = Math.ceil(names.length / COLUMN_COUNT);

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      role="listbox"
      aria-label="Icons"
      onKeyDown={handleKeyDown}
      className="outline-hidden"
    >
      <FixedSizeGrid
        ref={gridRef}
        columnCount={COLUMN_COUNT}
        rowCount={rowCount}
        columnWidth={CELL_SIZE}
        rowHeight={CELL_SIZE}
        height={GRID_HEIGHT}
        width={GRID_WIDTH}
      >
        {Cell}
      </FixedSizeGrid>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd src/frontend && npx tsc --noEmit -p tsconfig.json
```

Expected: no new type errors. (Pre-existing repo errors unrelated to these files are acceptable; investigate any error mentioning `iconPicker/IconGrid` or `react-window`.)

- [ ] **Step 3: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/iconPicker/IconGrid.tsx
git commit -m "feat(icon-picker): add virtualized IconGrid with arrow-key nav"
```

---

## Task 5: Rewrite `IconPickerField` + component tests

**Files:**
- Rewrite: `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx`
- Rewrite: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx`

- [ ] **Step 1: Write the failing test file**

Replace the contents of `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx` with:

```tsx
/**
 * react-window's FixedSizeGrid measures DOM size; jsdom reports 0×0, so
 * the real grid would render zero cells. Mock it with a passthrough that
 * renders every cell so tests can interact with the icon options.
 */
jest.mock("react-window", () => {
  const React = require("react");
  const FixedSizeGrid = React.forwardRef(function MockGrid(
    {
      children: Cell,
      columnCount,
      rowCount,
    }: {
      children: React.ComponentType<any>;
      columnCount: number;
      rowCount: number;
    },
    _ref: React.Ref<unknown>,
  ) {
    const cells = [];
    for (let r = 0; r < rowCount; r++) {
      for (let c = 0; c < columnCount; c++) {
        cells.push(
          React.createElement(Cell, {
            key: `${r}-${c}`,
            columnIndex: c,
            rowIndex: r,
            style: {},
            data: undefined,
            isScrolling: false,
          }),
        );
      }
    }
    return React.createElement("div", { "data-testid": "mock-grid" }, cells);
  });
  return { __esModule: true, FixedSizeGrid };
});

import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, fireEvent, within } from "@testing-library/react";
import IconPickerField from "../IconPickerField";
import { RECENT_ICONS_STORAGE_KEY } from "../iconPicker/useRecentIcons";

beforeEach(() => {
  window.localStorage.clear();
});

function openPicker() {
  fireEvent.click(screen.getByRole("button", { name: /choose icon/i }));
}

describe("IconPickerField", () => {
  it("trigger renders the selected icon name as text", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    expect(screen.getByText("FileText")).toBeInTheDocument();
  });

  it("clicking the trigger opens the popover with a search input", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();
    expect(screen.getByPlaceholderText(/search icons/i)).toBeInTheDocument();
  });

  it("opens with a populated grid of icon options", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();
    const options = screen.getAllByRole("option");
    expect(options.length).toBeGreaterThan(50);
  });

  it("clicking an option calls onChange and closes the popover", () => {
    const handleChange = jest.fn();
    render(<IconPickerField value="FileText" onChange={handleChange} />);
    openPicker();
    const option = screen.getAllByRole("option")[0];
    fireEvent.click(option);
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(typeof handleChange.mock.calls[0][0]).toBe("string");
    expect(screen.queryByPlaceholderText(/search icons/i)).not.toBeInTheDocument();
  });

  it("typing in the search filters the grid", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();
    const before = screen.getAllByRole("option").length;
    fireEvent.change(screen.getByPlaceholderText(/search icons/i), {
      target: { value: "fold" },
    });
    const after = screen.getAllByRole("option");
    expect(after.length).toBeLessThan(before);
    // "Folder" should be in the filtered results
    const titles = after.map((el) => el.getAttribute("title"));
    expect(titles).toContain("Folder");
  });

  it("typing a no-match query renders the empty state", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();
    fireEvent.change(screen.getByPlaceholderText(/search icons/i), {
      target: { value: "zzzz-no-match-query" },
    });
    expect(screen.getByText(/no icons match/i)).toBeInTheDocument();
  });

  it("recents row appears after a selection and is hidden when query is non-empty", () => {
    const { rerender } = render(<IconPickerField value="FileText" onChange={() => {}} />);
    // Pre-seed a recent
    window.localStorage.setItem(
      RECENT_ICONS_STORAGE_KEY,
      JSON.stringify(["Database", "Folder"]),
    );
    rerender(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();

    const recents = screen.getByRole("region", { name: /recents/i });
    expect(recents).toBeInTheDocument();
    expect(within(recents).getByTitle("Database")).toBeInTheDocument();

    // Type → recents row hides
    fireEvent.change(screen.getByPlaceholderText(/search icons/i), {
      target: { value: "fold" },
    });
    expect(screen.queryByRole("region", { name: /recents/i })).not.toBeInTheDocument();
  });

  it("selecting an icon records it as a recent", () => {
    const handleChange = jest.fn();
    render(<IconPickerField value="FileText" onChange={handleChange} />);
    openPicker();
    fireEvent.click(screen.getAllByRole("option")[0]);

    const stored = window.localStorage.getItem(RECENT_ICONS_STORAGE_KEY);
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored!);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed.length).toBe(1);
  });

  it("Escape closes the popover", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    openPicker();
    expect(screen.getByPlaceholderText(/search icons/i)).toBeInTheDocument();
    fireEvent.keyDown(screen.getByPlaceholderText(/search icons/i), {
      key: "Escape",
    });
    expect(screen.queryByPlaceholderText(/search icons/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx
```

Expected: FAILs because the current `IconPickerField` does not match the new expectations (new aria-label "Choose icon", recents region, empty-state text, etc.).

- [ ] **Step 3: Rewrite `IconPickerField.tsx`**

Replace the contents of `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx` with:

```tsx
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Command, CommandInput } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { filterIconNames } from "./iconPicker/filterIconNames";
import IconGrid from "./iconPicker/IconGrid";
import { LUCIDE_ICON_NAMES } from "./iconPicker/lucideIconNames";
import { useRecentIcons } from "./iconPicker/useRecentIcons";

type Props = {
  value: string;
  onChange: (iconName: string) => void;
};

export default function IconPickerField({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { recents, record } = useRecentIcons();

  const filtered = useMemo(() => filterIconNames(LUCIDE_ICON_NAMES, query), [query]);

  // Drop recents that no longer exist in the current lucide set.
  const validRecents = useMemo(() => {
    const set = new Set(LUCIDE_ICON_NAMES);
    return recents.filter((n) => set.has(n));
  }, [recents]);

  const showRecents = query.trim() === "" && validRecents.length > 0;

  const handleSelect = (name: string) => {
    onChange(name);
    record(name);
    setOpen(false);
    setQuery("");
  };

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Choose icon"
          className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-accent"
        >
          <IconComponent name={value} className="h-4 w-4" />
          <span>{value}</span>
          <ChevronDown className="h-4 w-4 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[340px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search icons…"
            value={query}
            onValueChange={setQuery}
            autoFocus
          />
          <div className="p-2">
            {showRecents && (
              <div
                role="region"
                aria-label="Recents"
                className="mb-2 border-b pb-2"
              >
                <div className="mb-1 px-1 text-xs font-medium text-muted-foreground">
                  Recents
                </div>
                <div className="flex flex-wrap gap-1">
                  {validRecents.map((name) => {
                    const isSelected = name === value;
                    return (
                      <button
                        key={name}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelect(name)}
                        title={name}
                        className={cn(
                          "flex h-9 w-9 items-center justify-center rounded-sm hover:bg-accent",
                          isSelected && "bg-accent text-accent-foreground",
                        )}
                      >
                        <IconComponent name={name} className="h-5 w-5" />
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {filtered.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No icons match "{query}"
              </div>
            ) : (
              <IconGrid
                names={filtered}
                selected={value}
                onSelect={handleSelect}
              />
            )}
          </div>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx
```

Expected: 9 tests pass.

- [ ] **Step 5: Run the full SaveAsTemplateModal test directory to confirm no regression**

```bash
cd src/frontend && npx jest src/modals/SaveAsTemplateModal
```

Expected: All tests pass across `lucideIconNames`, `useRecentIcons`, `filterIconNames`, `IconPickerField`, `GradientPickerField`, `scanBlankableFields`, and `SaveAsTemplateModal`.

- [ ] **Step 6: Type-check the project**

```bash
cd src/frontend && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors involving the changed files. (Pre-existing repo-wide errors are out of scope.)

- [ ] **Step 7: Manual smoke test**

Start the frontend dev server and exercise the picker in a browser:

```bash
cd src/frontend && npm run dev
```

Then in the running app:
1. Sign in as a superuser.
2. Open any flow.
3. Click Share → Save as Template.
4. Verify the Icon trigger shows the actual `FileText` icon (not the text "FileText" alone).
5. Click the trigger; verify the popover opens with a search input and a virtualized grid of real icons.
6. Type "fold"; verify only folder-related icons remain and `Folder` appears at the top.
7. Pick an icon; verify the trigger updates and the popover closes.
8. Reopen the picker; verify your last pick appears under a "Recents" header.
9. Type a query; verify "Recents" disappears.
10. Type a no-match query; verify the empty state shows.
11. Press Escape; verify the popover closes.
12. Reopen and use Tab to move focus from the input to the grid; use arrow keys; press Enter; verify the icon is selected.

If any of these fail, file the issue and stop before committing.

- [ ] **Step 8: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx
git commit -m "feat(icon-picker): rewrite IconPickerField with cmdk + virtualized grid + recents"
```

---

## Self-Review Notes

- **Spec coverage:** G1 (real icons everywhere) → Tasks 4 + 5. G2 (fuzzy ranking) → Task 3. G3 (virtualized) → Task 4. G4 (recents) → Task 2. G5 (keyboard) → Task 4. G6 (public API unchanged) → Task 5 keeps the same `Props`.
- **Risks coverage:** R1 (cmdk + virtualization) handled by `shouldFilter={false}` in Task 5. R2 (`dynamicIconImports` is private-ish) caught immediately by Task 1's "non-empty array" + ballpark tests. R3 (first react-window use) confined to `IconGrid.tsx` per Task 4.
- **Type consistency:** `LUCIDE_ICON_NAMES`, `useRecentIcons` shape `{ recents, record }`, `filterIconNames(names, query)`, `IconGrid` props `{ names, selected, onSelect, autoFocus? }`, `IconPickerField` props `{ value, onChange }` — all consistent across tasks.
- **Test scope:** Tasks 1–3 are pure TDD with focused unit tests. Task 4's grid is exercised through Task 5 because of jsdom's 0×0 measurement. Task 5 mocks `react-window` so the integrated picker behavior surfaces.
