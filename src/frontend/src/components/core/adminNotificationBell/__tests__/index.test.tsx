import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import AdminNotificationBell from "..";

jest.mock(
  "@/controllers/API/queries/admin/use-get-unread-notifications-count",
  () => ({
    useGetUnreadNotificationsCount: () => ({ data: { unread: 3 }, isPending: false }),
  }),
);

function renderBell() {
  const qc = new QueryClient();
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <AdminNotificationBell />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("AdminNotificationBell", () => {
  it("renders the unread badge count", () => {
    renderBell();
    expect(screen.getByTestId("admin-bell")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
