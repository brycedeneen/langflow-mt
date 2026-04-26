import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AdminNotificationsPage, { resolveNotificationLink } from "..";

const markReadMock = jest.fn();
const markAllReadMock = jest.fn();

jest.mock(
  "@/controllers/API/queries/admin/use-get-admin-notifications",
  () => ({
    useGetAdminNotifications: () => ({
      data: {
        items: [
          {
            id: "n-ps-1",
            org_id: null,
            category: "professional_services_request",
            severity: "info",
            title: "Quote submitted",
            body_md: "A new quote was submitted.",
            metadata: { quote_id: "quote-abc" },
            created_at: "2026-04-25T00:00:00Z",
            read_at: null,
          },
          {
            id: "n-system-1",
            org_id: null,
            category: "system",
            severity: "warning",
            title: "Heads up",
            body_md: "system note",
            metadata: {},
            created_at: "2026-04-25T00:00:00Z",
            read_at: null,
          },
        ],
        total: 2,
      },
      isPending: false,
    }),
  }),
);

jest.mock(
  "@/controllers/API/queries/admin/use-mark-notification-read",
  () => ({
    useMarkNotificationRead: () => ({ mutate: markReadMock, isPending: false }),
  }),
);

jest.mock(
  "@/controllers/API/queries/admin/use-mark-all-notifications-read",
  () => ({
    useMarkAllNotificationsRead: () => ({ mutate: markAllReadMock, isPending: false }),
  }),
);

function renderPage(initialEntry: string = "/settings/notifications") {
  const qc = new QueryClient();
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/settings/notifications" element={<AdminNotificationsPage />} />
          <Route
            path="/pro-service-quotes/:id"
            element={<div data-testid="ps-detail">PS Detail</div>}
          />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("AdminNotificationsPage", () => {
  beforeEach(() => {
    markReadMock.mockReset();
    markAllReadMock.mockReset();
  });

  it("renders notification rows", () => {
    renderPage();
    expect(screen.getByText("Quote submitted")).toBeInTheDocument();
    expect(screen.getByText("Heads up")).toBeInTheDocument();
  });

  it("deep-links a professional_services_request to the quote detail page", () => {
    renderPage();
    fireEvent.click(screen.getByTestId("notification-row-n-ps-1"));
    expect(screen.getByTestId("ps-detail")).toBeInTheDocument();
    // Clicking also marks unread rows read.
    expect(markReadMock).toHaveBeenCalledWith({ id: "n-ps-1" });
  });

  it("does not deep-link non-PS rows", () => {
    renderPage();
    fireEvent.click(screen.getByTestId("notification-row-n-system-1"));
    expect(screen.queryByTestId("ps-detail")).not.toBeInTheDocument();
  });
});

describe("resolveNotificationLink", () => {
  it("returns the PS quote detail URL when quote_id is present", () => {
    expect(
      resolveNotificationLink({
        id: "x",
        category: "professional_services_request",
        severity: "info",
        title: "t",
        body_md: "",
        metadata: { quote_id: "qid" },
        created_at: "",
        read_at: null,
      }),
    ).toBe("/pro-service-quotes/qid");
  });

  it("returns null for unknown categories", () => {
    expect(
      resolveNotificationLink({
        id: "x",
        category: "system",
        severity: "info",
        title: "t",
        body_md: "",
        metadata: {},
        created_at: "",
        read_at: null,
      }),
    ).toBeNull();
  });

  it("returns null when PS metadata.quote_id is missing", () => {
    expect(
      resolveNotificationLink({
        id: "x",
        category: "professional_services_request",
        severity: "info",
        title: "t",
        body_md: "",
        metadata: {},
        created_at: "",
        read_at: null,
      }),
    ).toBeNull();
  });
});
