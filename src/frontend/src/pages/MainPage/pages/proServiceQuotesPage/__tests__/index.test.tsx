import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { QuoteRead } from "@/types/pro-service-quote";

// The list page reads from useListQuotes (react-query) and useAuthStore
// (zustand). Both are mocked here so the smoke test renders without
// needing a QueryClientProvider or real auth state — same approach as the
// PreviewProposalModal test.
const listMock = jest.fn();
jest.mock("@/controllers/API/queries/pro-service-quotes", () => ({
  useListQuotes: (...args: unknown[]) => listMock(...args),
}));

let mockUserData: { is_superuser?: boolean; is_platform_admin?: boolean } = {};
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { userData: typeof mockUserData }) => unknown) =>
    selector({ userData: mockUserData }),
}));

import ProServiceQuotesPage from "../index";

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
    conversation_summary: null,
    org_notes: null,
    admin_notes: null,
    created_at: "2026-04-25T00:00:00Z",
    submitted_at: "2026-04-25T00:00:00Z",
    in_progress_at: null,
    closed_at: null,
    closed_by_user_id: null,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ProServiceQuotesPage />
    </MemoryRouter>,
  );
}

describe("ProServiceQuotesPage", () => {
  beforeEach(() => {
    listMock.mockReset();
    mockUserData = {};
  });

  it("renders the empty state when there are no quotes", () => {
    listMock.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, isError: false });
    renderPage();
    expect(screen.getByTestId("ps-quotes-empty")).toBeInTheDocument();
  });

  it("shows the org-name column for admin users", () => {
    mockUserData = { is_superuser: true };
    listMock.mockReturnValue({
      data: { items: [quote()], total: 1 },
      isLoading: false,
      isError: false,
    });
    renderPage();
    expect(screen.getByText("Org name")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Flow" })).not.toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
  });

  it("shows the flow column for non-admin org members", () => {
    mockUserData = { is_superuser: false, is_platform_admin: false };
    listMock.mockReturnValue({
      data: { items: [quote()], total: 1 },
      isLoading: false,
      isError: false,
    });
    renderPage();
    expect(screen.queryByText("Org name")).not.toBeInTheDocument();
    expect(screen.getByText("Flow")).toBeInTheDocument();
    // "Slack pipeline" appears in both the Flow cell and the Open-flow link;
    // assert presence via the row cell to disambiguate.
    const row = screen.getByTestId("ps-quote-row-quote-1");
    expect(row.querySelectorAll("td")[0].textContent).toBe("Slack pipeline");
  });

  it("renders an em-dash price range when rates are null", () => {
    listMock.mockReturnValue({
      data: {
        items: [
          quote({ rate_low_per_hour: null, rate_high_per_hour: null }),
        ],
        total: 1,
      },
      isLoading: false,
      isError: false,
    });
    renderPage();
    // Price-range cell is the second cell in the row.
    const row = screen.getByTestId("ps-quote-row-quote-1");
    const cells = row.querySelectorAll("td");
    expect(cells[1].textContent).toBe("—");
  });
});
