import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { QuoteRead } from "@/types/pro-service-quote";

const getQuoteMock = jest.fn();
const updateMock = jest.fn();

jest.mock("@/controllers/API/queries/pro-service-quotes", () => ({
  useGetQuote: (...args: unknown[]) => getQuoteMock(...args),
  useUpdateQuote: () => ({ mutate: updateMock, isPending: false }),
}));

let mockUserData: {
  id?: string;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
} = {};

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { userData: typeof mockUserData }) => unknown) =>
    selector({ userData: mockUserData }),
}));

import ProServiceQuoteDetailPage from "../index";

function quote(overrides: Partial<QuoteRead> = {}): QuoteRead {
  return {
    id: "quote-1",
    org_id: "org-1",
    org_name: "Acme",
    flow_id: "flow-1",
    flow_name: "Slack pipeline",
    requester_user_id: "user-1",
    requester_email: "user@acme.test",
    status: "open",
    assigned_admin_user_id: null,
    estimated_minutes_low: 180,
    estimated_minutes_high: 720,
    rate_low_per_hour: "200.00",
    rate_high_per_hour: "200.00",
    headline_summary: "Wire up Slack notifications",
    narrative: "User wants to push events.",
    conversation_summary: "User struggled with OAuth.",
    org_notes: "n1",
    admin_notes: "a1",
    created_at: "2026-04-25T00:00:00Z",
    submitted_at: "2026-04-25T00:00:00Z",
    in_progress_at: null,
    closed_at: null,
    closed_by_user_id: null,
    ...overrides,
  };
}

function renderAt(
  pathQuoteId = "quote-1",
  data?: Partial<{
    quote: QuoteRead;
    isLoading: boolean;
    isError: boolean;
  }>,
) {
  getQuoteMock.mockReturnValue({
    data: data?.quote ?? quote(),
    isLoading: data?.isLoading ?? false,
    isError: data?.isError ?? false,
  });
  return render(
    <MemoryRouter initialEntries={[`/pro-service-quotes/${pathQuoteId}`]}>
      <Routes>
        <Route
          path="/pro-service-quotes/:id"
          element={<ProServiceQuoteDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProServiceQuoteDetailPage", () => {
  beforeEach(() => {
    getQuoteMock.mockReset();
    updateMock.mockReset();
    mockUserData = {};
  });

  it("renders the headline, narrative, and dollar range", () => {
    renderAt();
    expect(screen.getByTestId("ps-detail-headline")).toHaveTextContent(
      "Wire up Slack notifications",
    );
    expect(screen.getByTestId("ps-detail-narrative")).toHaveTextContent(
      "User wants to push events.",
    );
    // 180→3.0, 720→12.0 hours
    expect(screen.getByTestId("ps-detail-hours")).toHaveTextContent(
      /3\.0 hr.*12\.0 hr/,
    );
    expect(screen.getByTestId("ps-detail-dollars")).toHaveTextContent(
      /\$600\.00.*\$2400\.00/,
    );
  });

  it("hides the dollar range when rates are null", () => {
    renderAt("quote-1", {
      quote: quote({ rate_low_per_hour: null, rate_high_per_hour: null }),
    });
    expect(screen.queryByTestId("ps-detail-dollars")).not.toBeInTheDocument();
  });

  it("hides the admin-notes panel for non-admin org members", () => {
    mockUserData = { id: "user-1" };
    renderAt();
    expect(screen.queryByTestId("ps-detail-admin-notes")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("ps-detail-mark-in-progress"),
    ).not.toBeInTheDocument();
  });

  it("shows the admin actions for admin users", () => {
    mockUserData = { id: "admin-1", is_superuser: true };
    renderAt();
    expect(screen.getByTestId("ps-detail-admin-notes")).toBeInTheDocument();
    expect(
      screen.getByTestId("ps-detail-mark-in-progress"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("ps-detail-close")).toBeInTheDocument();
  });

  it("shows Cancel-my-request only for the requester on an open quote", () => {
    mockUserData = { id: "user-1" };
    renderAt();
    expect(
      screen.getByTestId("ps-detail-cancel-request"),
    ).toBeInTheDocument();
  });

  it("does not show Cancel-my-request once the quote is closed", () => {
    mockUserData = { id: "user-1" };
    renderAt("quote-1", { quote: quote({ status: "closed" }) });
    expect(
      screen.queryByTestId("ps-detail-cancel-request"),
    ).not.toBeInTheDocument();
  });
});
