import { describe, expect, it } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import ProServiceQuotesPage from "../index";

describe("ProServiceQuotesPage (stub)", () => {
  it("renders without crashing", () => {
    render(<ProServiceQuotesPage />);
    expect(screen.getByTestId("pro-service-quotes-page")).toBeInTheDocument();
  });
});
