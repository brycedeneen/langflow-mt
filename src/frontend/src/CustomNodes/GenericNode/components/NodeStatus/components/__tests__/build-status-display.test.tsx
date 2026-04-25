import { render, screen } from "@testing-library/react";
import BuildStatusDisplay from "../build-status-display";
import { BuildStatus } from "@/constants/enums";
import type { UsageType } from "@/types/chat";

const baseValidationStatus = (token_usage: UsageType | null | undefined) => ({
  data: {
    duration: "1.2s",
    token_usage,
  },
});

const renderTooltip = (token_usage: UsageType | null | undefined) =>
  render(
    <BuildStatusDisplay
      buildStatus={BuildStatus.BUILT}
      validationStatus={baseValidationStatus(token_usage)}
      validationString=""
      lastRunTime="4/25/2026, 7:44:00 AM"
    />,
  );

describe("BuildStatusDisplay cost row", () => {
  it("renders the Estimated cost row with $X.XX when cost_micros is multi-cent", () => {
    renderTooltip({
      input_tokens: 100,
      output_tokens: 50,
      total_tokens: 150,
      cost_micros: 1_234_567,
    });
    expect(screen.getByText(/Estimated cost/i)).toBeInTheDocument();
    expect(screen.getByText("$1.23")).toBeInTheDocument();
  });

  it("renders <$0.01 for sub-cent positive cost", () => {
    renderTooltip({
      input_tokens: 1,
      output_tokens: 0,
      total_tokens: 1,
      cost_micros: 500,
    });
    expect(screen.getByText("<$0.01")).toBeInTheDocument();
  });

  it("renders $0.00 for genuine zero cost", () => {
    renderTooltip({
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_micros: 0,
    });
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  it("hides the cost row when cost_micros is null", () => {
    renderTooltip({
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
      cost_micros: null,
    });
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });

  it("hides the cost row when cost_micros is undefined", () => {
    renderTooltip({
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
    });
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });

  it("does not render any usage rows when token_usage itself is undefined", () => {
    renderTooltip(undefined);
    expect(screen.queryByText(/Input tokens/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Estimated cost/i)).not.toBeInTheDocument();
  });
});
