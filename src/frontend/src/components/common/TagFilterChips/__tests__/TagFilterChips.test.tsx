import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TagRead } from "@/types/tag";
import TagFilterChips from "../index";

const mkTag = (id: string, name: string, color = "slate" as const): TagRead => ({
  id,
  name,
  color,
  description: null,
  created_by: null,
  created_at: "2026-04-23T00:00:00Z",
  updated_at: "2026-04-23T00:00:00Z",
});

describe("TagFilterChips", () => {
  const tags: TagRead[] = [mkTag("t1", "Alpha"), mkTag("t2", "Beta")];

  it("adds the tag id to the selection when an unselected chip is clicked", async () => {
    const onChange = jest.fn();
    render(
      <TagFilterChips
        availableTags={tags}
        selected={[]}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add filter alpha/i }),
    );
    expect(onChange).toHaveBeenCalledWith(["t1"]);
  });

  it("removes the tag id when an already-selected chip is clicked", async () => {
    const onChange = jest.fn();
    render(
      <TagFilterChips
        availableTags={tags}
        selected={["t1", "t2"]}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /remove filter alpha/i }),
    );
    expect(onChange).toHaveBeenCalledWith(["t2"]);
  });

  it("renders nothing when availableTags is empty", () => {
    const { container } = render(
      <TagFilterChips
        availableTags={[]}
        selected={[]}
        onChange={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("tag-filter-chips")).not.toBeInTheDocument();
  });

  it("toggles a chip via keyboard (Enter)", async () => {
    const onChange = jest.fn();
    const user = userEvent.setup();
    render(
      <TagFilterChips
        availableTags={tags}
        selected={[]}
        onChange={onChange}
      />,
    );
    await user.tab(); // focuses the first chip button
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith(["t1"]);
  });
});
