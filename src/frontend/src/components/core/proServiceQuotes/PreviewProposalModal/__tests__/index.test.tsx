import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { PreviewResponse } from "@/types/pro-service-quote";
import { PreviewProposalModal } from "../index";

// Mock the submit hook so we don't need a QueryClientProvider — same pattern
// the SaveAsTemplateModal tests use for the create-template mutation.
const submitMock = jest.fn();
jest.mock("@/controllers/API/queries/pro-service-quotes/use-submit-quote", () => ({
  useSubmitQuote: () => ({
    mutate: submitMock,
    isPending: false,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

function basePreview(): PreviewResponse {
  return {
    minutes_low: 180,
    minutes_high: 720,
    rate_low_per_hour: "200.00",
    rate_high_per_hour: "200.00",
    cost_low: "600.00",
    cost_high: "2400.00",
    headline_summary: "Wire up Slack notifications",
    narrative: "User wants to push events.",
    conversation_summary: "User struggled with OAuth.",
    component_breakdown: [
      { type: "Webhook", minutes_low: 30, minutes_high: 90 },
    ],
  };
}

describe("PreviewProposalModal", () => {
  beforeEach(() => {
    submitMock.mockReset();
  });

  it("renders hours range and dollar range when rates are provided", () => {
    renderWithProviders(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={basePreview()}
        onClose={() => {}}
      />,
    );
    // 720 minutes >= 60 → flips to hours: 3.0 hr – 12.0 hr.
    expect(screen.getByTestId("ps-time-range")).toHaveTextContent(
      /3\.0 hr.*12\.0 hr/,
    );
    expect(screen.getByTestId("ps-cost-range")).toHaveTextContent(/\$600\.00/);
    expect(screen.getByTestId("ps-cost-range")).toHaveTextContent(/\$2400\.00/);
  });

  it("renders minutes range when upper bound is under 60 minutes", () => {
    renderWithProviders(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={{ ...basePreview(), minutes_low: 10, minutes_high: 45 }}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("ps-time-range")).toHaveTextContent(
      "10 min – 45 min",
    );
  });

  it("hides dollar range when both rates are null", () => {
    renderWithProviders(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={{
          ...basePreview(),
          rate_low_per_hour: null,
          rate_high_per_hour: null,
          cost_low: null,
          cost_high: null,
        }}
        onClose={() => {}}
      />,
    );
    expect(screen.queryByTestId("ps-cost-range")).not.toBeInTheDocument();
  });

  it("disables Submit when headline is blank", () => {
    renderWithProviders(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={{ ...basePreview(), headline_summary: "" }}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("ps-submit-button")).toBeDisabled();
  });

  it("submits with the user-edited headline + narrative", () => {
    renderWithProviders(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={basePreview()}
        onClose={() => {}}
      />,
    );
    const headline = screen.getByTestId(
      "ps-headline-input",
    ) as HTMLInputElement;
    fireEvent.change(headline, { target: { value: "Updated headline" } });

    fireEvent.click(screen.getByTestId("ps-submit-button"));
    expect(submitMock).toHaveBeenCalledTimes(1);
    const [payload] = submitMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload).toMatchObject({
      minutes_low: 180,
      minutes_high: 720,
      headline_summary: "Updated headline",
      narrative: "User wants to push events.",
    });
  });

  it("renders nothing when preview is null", () => {
    const { container } = render(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={null}
        onClose={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
