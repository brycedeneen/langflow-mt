import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import MembershipsTab from "../MembershipsTab";

const mockUpdateRole = jest.fn();
const mockRemoveMember = jest.fn();

jest.mock("@/controllers/API/queries/admin/use-update-member-role", () => ({
  useUpdateMemberRole: () => ({ mutate: mockUpdateRole, isPending: false }),
}));
jest.mock("@/controllers/API/queries/admin", () => ({
  ...jest.requireActual("@/controllers/API/queries/admin"),
  useRemoveMember: () => ({ mutate: mockRemoveMember, isPending: false }),
}));

const qc = new QueryClient();
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={qc}>
    <TooltipProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

const user = {
  id: "u1",
  username: "ava",
  is_active: true,
  is_platform_admin: true,
  is_superuser: false,
  create_at: null,
  updated_at: null,
  last_login_at: null,
  memberships: [
    {
      organization_id: "org-personal",
      organization_name: "ava's org",
      is_personal: true,
      role: "owner" as const,
      joined_at: "2024-01-01",
    },
    {
      organization_id: "org-team",
      organization_name: "Team",
      is_personal: false,
      role: "admin" as const,
      joined_at: "2025-06-01",
    },
  ],
};

beforeEach(() => {
  mockUpdateRole.mockReset();
  mockRemoveMember.mockReset();
});

describe("MembershipsTab", () => {
  it("renders rows for each membership", () => {
    render(wrap(<MembershipsTab user={user} />));
    expect(screen.getByText("ava's org")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
  });

  it("marks personal org as locked", () => {
    render(wrap(<MembershipsTab user={user} />));
    const personalRow = screen.getByTestId("membership-row-org-personal");
    expect(personalRow.textContent?.toLowerCase()).toMatch(/personal/);
    expect(personalRow.textContent?.toLowerCase()).toMatch(/locked/);
  });

  it("has a remove button on non-personal rows only", () => {
    render(wrap(<MembershipsTab user={user} />));
    expect(screen.getByTestId("remove-org-team")).toBeInTheDocument();
    expect(screen.queryByTestId("remove-org-personal")).toBeNull();
  });
});
