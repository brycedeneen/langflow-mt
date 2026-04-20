import { describe, it, expect, jest } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import GradientPickerField from "../GradientPickerField";

describe("GradientPickerField", () => {
  it("renders the selected gradient with a visible 'selected' indicator", () => {
    render(<GradientPickerField value="2" onChange={() => {}} />);
    const selected = screen.getByTestId("gradient-swatch-2");
    expect(selected.getAttribute("data-selected")).toBe("true");
  });

  it("clicking a swatch calls onChange with that index as a string", () => {
    const handleChange = jest.fn();
    render(<GradientPickerField value="0" onChange={handleChange} />);
    fireEvent.click(screen.getByTestId("gradient-swatch-3"));
    expect(handleChange).toHaveBeenCalledWith("3");
  });

  it("renders as many swatches as there are gradients", () => {
    render(<GradientPickerField value="0" onChange={() => {}} />);
    const swatches = screen.getAllByTestId(/^gradient-swatch-/);
    expect(swatches.length).toBeGreaterThanOrEqual(8);
  });
});
