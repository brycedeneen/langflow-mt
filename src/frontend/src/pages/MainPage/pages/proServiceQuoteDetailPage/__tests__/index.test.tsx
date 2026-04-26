import { describe, expect, it } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import ProServiceQuoteDetailPage from "../index";

describe("ProServiceQuoteDetailPage (stub)", () => {
  it("renders without crashing", () => {
    render(<ProServiceQuoteDetailPage />);
    expect(
      screen.getByTestId("pro-service-quote-detail-page"),
    ).toBeInTheDocument();
  });
});
