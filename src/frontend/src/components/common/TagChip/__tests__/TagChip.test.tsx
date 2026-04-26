import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TagChip from "../index";

const baseTag = {
  id: "tag-1",
  name: "Production",
  color: "blue" as const,
};

describe("TagChip", () => {
  it("renders the tag name", () => {
    render(<TagChip tag={baseTag} />);
    expect(screen.getByText("Production")).toBeInTheDocument();
  });

  it("applies the correct bg-{color}-500 class for the given color", () => {
    const { container } = render(
      <TagChip tag={{ ...baseTag, color: "red" }} />,
    );
    const badge = container.querySelector("div");
    expect(badge).not.toBeNull();
    expect(badge!.className).toContain("bg-red-500");
  });

  it("renders a remove button that calls onRemove with the tag id when clicked", async () => {
    const onRemove = jest.fn();
    render(<TagChip tag={baseTag} onRemove={onRemove} />);
    const btn = screen.getByRole("button", { name: /remove production/i });
    await userEvent.click(btn);
    expect(onRemove).toHaveBeenCalledWith("tag-1");
  });

  it("does not render a remove button when onRemove is absent", () => {
    render(<TagChip tag={baseTag} />);
    expect(
      screen.queryByRole("button", { name: /remove/i }),
    ).not.toBeInTheDocument();
  });
});
