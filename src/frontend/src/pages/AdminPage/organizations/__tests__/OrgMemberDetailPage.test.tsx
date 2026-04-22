import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import OrgMemberDetailPage from "../OrgMemberDetailPage";

jest.mock("@/controllers/API/queries/admin", () => ({
  ...jest.requireActual("@/controllers/API/queries/admin"),
  useGetOrganization: () => ({
    data: {
      id: "org-team",
      name: "Team",
      slug: "team",
      is_personal: false,
      created_at: "2025-01-01",
      updated_at: "2025-01-01",
      member_count: 1,
      members: [
        { user_id: "u1", username: "ava", role: "admin", is_active: true },
      ],
    },
    isPending: false,
  }),
  useRemoveMember: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock("@/controllers/API/queries/admin/use-update-member-role", () => ({
  useUpdateMemberRole: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      userData: { id: "admin-user", is_platform_admin: true },
    }),
}));

const qc = new QueryClient();
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={qc}>
    <TooltipProvider>{ui}</TooltipProvider>
  </QueryClientProvider>
);

it("renders scoped member view", () => {
  render(
    wrap(
      <MemoryRouter
        initialEntries={["/settings/organizations/org-team/members/u1"]}
      >
        <Routes>
          <Route
            path="/settings/organizations/:orgId/members/:userId"
            element={<OrgMemberDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    ),
  );
  expect(screen.getByText("ava")).toBeInTheDocument();
  expect(screen.getByTestId("status-pill")).toHaveTextContent(/active/i);
  // Should NOT render the "Platform Admin" pill or cross-org data.
  expect(screen.queryByText(/^Platform Admin$/)).toBeNull();
  // The back-link shows the org name.
  expect(screen.getByText(/back to team/i)).toBeInTheDocument();
});
