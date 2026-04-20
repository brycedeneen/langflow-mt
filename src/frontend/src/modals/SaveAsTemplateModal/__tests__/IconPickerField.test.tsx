import { describe, it, expect, jest } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import IconPickerField from "../IconPickerField";

describe("IconPickerField", () => {
  it("renders the selected icon name on the trigger", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /filetext/i })).toBeInTheDocument();
  });

  it("clicking the trigger opens a popover with icon options", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    expect(screen.getAllByRole("option").length).toBeGreaterThan(5);
  });

  it("selecting an option calls onChange with that icon name", () => {
    const handleChange = jest.fn();
    render(<IconPickerField value="FileText" onChange={handleChange} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    const options = screen.getAllByRole("option");
    fireEvent.click(options[0]);
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(typeof handleChange.mock.calls[0][0]).toBe("string");
  });

  it("typing in the search filters the list", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    const before = screen.getAllByRole("option").length;
    const search = screen.getByPlaceholderText(/search/i);
    fireEvent.change(search, { target: { value: "zzzzzz-unlikely-match" } });
    expect(screen.queryAllByRole("option").length).toBeLessThan(before);
  });
});
