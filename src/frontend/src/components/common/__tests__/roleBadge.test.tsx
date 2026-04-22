import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoleBadge from "../roleBadge";

describe("RoleBadge", () => {
  it("renders the role label", () => {
    render(<RoleBadge role="admin" />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows the description in a tooltip on hover", async () => {
    render(<RoleBadge role="viewer" />);
    await userEvent.hover(screen.getByText("Viewer"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/views flows/i);
  });
});
