import { render, screen, fireEvent } from "@testing-library/react";
import { AdpAssistButton } from "../adp-assist-button";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockOpenFullscreen = jest.fn();
jest.mock("@/utils/assist-entry", () => ({
  openFlowInFullscreenAssist: (flowId: string, navigate: unknown) =>
    mockOpenFullscreen(flowId, navigate),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

// ShadTooltip wraps its children in a Radix Tooltip which needs a provider.
// Mock it to just render children directly so the button stays testable.
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe("AdpAssistButton", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockOpenFullscreen.mockReset();
  });

  it("opens the flow in fullscreen assist mode on click", () => {
    render(<AdpAssistButton flowId="abc-123" builtWithAssist={false} />);
    fireEvent.click(
      screen.getByRole("button", { name: /open in adp assist/i }),
    );
    expect(mockOpenFullscreen).toHaveBeenCalledTimes(1);
    expect(mockOpenFullscreen).toHaveBeenCalledWith("abc-123", mockNavigate);
  });

  it("applies the highlighted class when builtWithAssist is true", () => {
    const { container } = render(
      <AdpAssistButton flowId="abc-123" builtWithAssist={true} />,
    );
    const button = container.querySelector("button");
    expect(button?.className).toMatch(/text-primary/);
  });
});
