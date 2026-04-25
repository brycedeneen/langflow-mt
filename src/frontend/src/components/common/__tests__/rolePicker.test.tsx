import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RolePicker from "../rolePicker";

// Radix Select relies on several DOM APIs that jsdom does not implement.
// Polyfill them here so the listbox can open under userEvent.click().
beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
});

describe("RolePicker", () => {
  it("disables admin/owner options when caller is admin", async () => {
    render(<RolePicker caller="admin" current="member" onSelect={() => {}} />);
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    expect(screen.getByTestId("role-option-admin")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByTestId("role-option-owner")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByTestId("role-option-member")).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("enables all options when caller is owner", async () => {
    render(<RolePicker caller="owner" current="member" onSelect={() => {}} />);
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    for (const role of ["owner", "admin", "member", "operator", "viewer"]) {
      expect(screen.getByTestId(`role-option-${role}`)).not.toHaveAttribute(
        "aria-disabled",
        "true",
      );
    }
  });

  it("calls onSelect when a role is chosen", async () => {
    const onSelect = jest.fn();
    render(
      <RolePicker
        caller="platform_admin"
        current="viewer"
        onSelect={onSelect}
      />,
    );
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    await userEvent.click(screen.getByTestId("role-option-member"));
    expect(onSelect).toHaveBeenCalledWith("member");
  });

  it("is read-only when caller cannot assign anything", () => {
    render(<RolePicker caller="viewer" current="viewer" onSelect={() => {}} />);
    expect(screen.getByTestId("role-picker-trigger")).toBeDisabled();
  });
});
