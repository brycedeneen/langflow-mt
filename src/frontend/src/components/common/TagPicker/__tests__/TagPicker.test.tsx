import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TagPicker from "../index";

jest.mock("@/controllers/API/queries/tags", () => ({
  useListTags: jest.fn(),
}));

// Re-import after mock to get the mocked handle.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { useListTags } = require("@/controllers/API/queries/tags") as {
  useListTags: jest.Mock;
};

const mkTag = (id: string, name: string, color = "slate" as const) => ({
  id,
  name,
  color,
  description: null,
  created_by: null,
  created_at: "2026-04-23T00:00:00Z",
  updated_at: "2026-04-23T00:00:00Z",
});

describe("TagPicker", () => {
  beforeEach(() => {
    useListTags.mockReturnValue({
      data: [
        mkTag("t1", "Alpha"),
        mkTag("t2", "Beta"),
        mkTag("t3", "Gamma"),
      ],
      isPending: false,
    });
  });

  it("renders all tags as unselected chips when selectedIds is empty", () => {
    render(<TagPicker selectedIds={[]} onChange={() => {}} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    // All three should be add-buttons (unselected).
    expect(screen.getByRole("button", { name: /add alpha/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add beta/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add gamma/i })).toBeInTheDocument();
  });

  it("calls onChange with the added id when an unselected chip is clicked", async () => {
    const onChange = jest.fn();
    render(<TagPicker selectedIds={[]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /add beta/i }));
    expect(onChange).toHaveBeenCalledWith(["t2"]);
  });

  it("calls onChange with the id removed when the ✕ on a selected chip is clicked", async () => {
    const onChange = jest.fn();
    render(<TagPicker selectedIds={["t1", "t2"]} onChange={onChange} />);
    const removeBtn = screen.getByRole("button", { name: /remove alpha/i });
    await userEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith(["t2"]);
  });

  it("shows the empty state when there are zero tags", () => {
    useListTags.mockReturnValueOnce({ data: [], isPending: false });
    render(<TagPicker selectedIds={[]} onChange={() => {}} />);
    expect(screen.getByTestId("tag-picker-empty")).toHaveTextContent(
      /no tags yet/i,
    );
  });
});
