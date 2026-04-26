import { describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { fireEvent, render, screen } from "@testing-library/react";
import { PSSuggestionCard } from "../index";

describe("PSSuggestionCard", () => {
  it("renders the reason text and the Need a hand? header", () => {
    render(
      <PSSuggestionCard
        reason="Stuck on OAuth for 15 min"
        onRequest={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/Need a hand\?/)).toBeInTheDocument();
    expect(
      screen.getByText(/Stuck on OAuth for 15 min/),
    ).toBeInTheDocument();
  });

  it("calls onRequest when the request CTA is clicked", () => {
    const onRequest = jest.fn();
    render(
      <PSSuggestionCard
        reason="Reason"
        onRequest={onRequest}
        onDismiss={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId("ps-suggestion-request"));
    expect(onRequest).toHaveBeenCalledTimes(1);
  });

  it("calls onDismiss when the dismiss button is clicked", () => {
    const onDismiss = jest.fn();
    render(
      <PSSuggestionCard
        reason="Reason"
        onRequest={() => {}}
        onDismiss={onDismiss}
      />,
    );
    fireEvent.click(screen.getByTestId("ps-suggestion-dismiss"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
