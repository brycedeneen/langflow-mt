import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PSRequestButton } from "../index";

// Mock the preview/submit hooks so the test runs without a real query client.
const previewMutateMock = jest.fn();
jest.mock("@/controllers/API/queries/pro-service-quotes/use-preview-quote", () => ({
  usePreviewQuote: () => ({
    mutate: previewMutateMock,
    isPending: false,
  }),
}));
jest.mock("@/controllers/API/queries/pro-service-quotes/use-submit-quote", () => ({
  useSubmitQuote: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
}));

function renderWithTooltipProvider(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("PSRequestButton", () => {
  beforeEach(() => {
    previewMutateMock.mockReset();
  });

  it("renders nothing when canRequest is false", () => {
    const { container } = renderWithTooltipProvider(
      <PSRequestButton flowId="f1" canRequest={false} psRequestActive={false} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("disables the button when psRequestActive is true", () => {
    renderWithTooltipProvider(
      <PSRequestButton flowId="f1" canRequest psRequestActive />,
    );
    expect(screen.getByTestId("ps-request-button")).toBeDisabled();
  });

  it("renders an enabled button when canRequest=true and psRequestActive=false", () => {
    renderWithTooltipProvider(
      <PSRequestButton flowId="f1" canRequest psRequestActive={false} />,
    );
    expect(screen.getByTestId("ps-request-button")).toBeEnabled();
  });
});
