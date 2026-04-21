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
    // "Folder" should be in the filtered results, "Anchor" should not
    const titles = after.map((el) => el.getAttribute("title"));
    expect(titles).toContain("Folder");
    expect(titles).not.toContain("Anchor");
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
    // Pre-seed BEFORE the first render so the hook's useState initializer reads it.
    window.localStorage.setItem(
      RECENT_ICONS_STORAGE_KEY,
      JSON.stringify(["Database", "Folder"]),
    );
    render(<IconPickerField value="FileText" onChange={() => {}} />);
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
