import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import AccountTab from "../AccountTab";

const mockUpdate = jest.fn();
const mockDelete = jest.fn();

jest.mock("@/controllers/API/queries/auth", () => ({
  useUpdateUser: () => ({ mutate: mockUpdate }),
  useDeleteUsers: () => ({ mutate: mockDelete }),
}));

const qc = new QueryClient();
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={qc}>
    <TooltipProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

const userFixture = {
  id: "u1",
  username: "ava.chen",
  is_active: true,
  is_platform_admin: false,
  is_superuser: false,
  create_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-02-01T00:00:00Z",
  last_login_at: "2026-04-22T09:00:00Z",
  memberships: [],
};

beforeEach(() => {
  mockUpdate.mockReset();
  mockDelete.mockReset();
});

describe("AccountTab", () => {
  it("renders identity facts", () => {
    render(wrap(<AccountTab user={userFixture} />));
    expect(screen.getByText("ava.chen")).toBeInTheDocument();
    expect(screen.getByText(/2025-01-01/)).toBeInTheDocument();
  });

  it("shows active toggle in correct state", () => {
    render(wrap(<AccountTab user={userFixture} />));
    const toggle = screen.getByTestId("active-toggle");
    expect(toggle).toHaveAttribute("data-state", "checked");
  });

  it("shows platform-admin toggle in correct state", () => {
    render(wrap(<AccountTab user={userFixture} />));
    const toggle = screen.getByTestId("platform-admin-toggle");
    expect(toggle).toHaveAttribute("data-state", "unchecked");
  });

  it("confirms before deleting user", async () => {
    render(wrap(<AccountTab user={userFixture} />));
    await userEvent.click(
      screen.getByRole("button", { name: /delete user/i }),
    );
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
