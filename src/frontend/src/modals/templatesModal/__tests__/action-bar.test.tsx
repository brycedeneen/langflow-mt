import { render, screen, fireEvent } from "@testing-library/react";
import { ActionBar } from "../components/actionBar";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("ActionBar", () => {
  it("disables Start Building and Build with ADP Assist when nothing selected", () => {
    render(
      <ActionBar
        selectedTemplate={null}
        onCancel={jest.fn()}
        onStartBuilding={jest.fn()}
        onBuildWithAssist={jest.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /start building/i })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /build with adp assist/i }),
    ).toBeDisabled();
  });

  it("enables both action buttons when a template is selected", () => {
    render(
      <ActionBar
        selectedTemplate="blank"
        onCancel={jest.fn()}
        onStartBuilding={jest.fn()}
        onBuildWithAssist={jest.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /start building/i })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: /build with adp assist/i }),
    ).toBeEnabled();
  });

  it("invokes the right handler on click", () => {
    const onCancel = jest.fn();
    const onStart = jest.fn();
    const onAssist = jest.fn();
    render(
      <ActionBar
        selectedTemplate="some-flow-id"
        onCancel={onCancel}
        onStartBuilding={onStart}
        onBuildWithAssist={onAssist}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    fireEvent.click(screen.getByRole("button", { name: /start building/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /build with adp assist/i }),
    );
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onAssist).toHaveBeenCalledTimes(1);
  });
});
