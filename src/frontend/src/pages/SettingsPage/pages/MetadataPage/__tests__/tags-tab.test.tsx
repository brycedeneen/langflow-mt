import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { TagsTab } from "../tags-tab";

const renderWithProviders = (ui: React.ReactElement) =>
  render(<TooltipProvider>{ui}</TooltipProvider>);

const mockCreateTag = jest.fn().mockResolvedValue(undefined);
const mockUpdateTag = jest.fn().mockResolvedValue(undefined);
const mockDeleteTag = jest.fn();

const mockUseListTagsAdmin = jest.fn(() => ({
  data: [
    {
      id: "tag-1",
      name: "Production",
      color: "green",
      description: "Production-ready flows",
      created_by: "user-1",
      created_at: "2026-04-23T00:00:00Z",
      updated_at: "2026-04-23T00:00:00Z",
    },
    {
      id: "tag-2",
      name: "Experimental",
      color: "amber",
      description: null,
      created_by: "user-1",
      created_at: "2026-04-23T00:00:00Z",
      updated_at: "2026-04-23T00:00:00Z",
    },
  ],
  isPending: false,
}));

jest.mock("@/controllers/API/queries/admin", () => ({
  useListTagsAdmin: () => mockUseListTagsAdmin(),
  useCreateTag: () => ({
    mutateAsync: mockCreateTag,
    isPending: false,
  }),
  useUpdateTag: () => ({
    mutateAsync: mockUpdateTag,
    isPending: false,
  }),
  useDeleteTag: () => ({
    mutate: mockDeleteTag,
    isPending: false,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: unknown) => unknown) =>
    selector({ setSuccessData: jest.fn(), setErrorData: jest.fn() }),
}));

const mockUserData = { is_platform_admin: true };
jest.mock("@/hooks/use-is-platform-admin", () => ({
  useIsPlatformAdmin: () => mockUserData.is_platform_admin,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("TagsTab", () => {
  beforeEach(() => {
    mockCreateTag.mockClear();
    mockUpdateTag.mockClear();
    mockDeleteTag.mockClear();
    mockUserData.is_platform_admin = true;
  });

  it("renders the tag list and shows the New tag button for platform admins", () => {
    render(<TagsTab />);
    expect(screen.getByText("Production")).toBeInTheDocument();
    expect(screen.getByText("Experimental")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /new tag/i }),
    ).toBeInTheDocument();
  });

  it("hides the New tag button and row actions for non-platform-admins", () => {
    mockUserData.is_platform_admin = false;
    render(<TagsTab />);
    expect(screen.getByText("Production")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /new tag/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^edit$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^delete$/i }),
    ).not.toBeInTheDocument();
  });

  it("shows empty state when no tags are configured", () => {
    mockUseListTagsAdmin.mockReturnValueOnce({ data: [], isPending: false });
    render(<TagsTab />);
    expect(
      screen.getByText(/no tags yet\. create the first one\./i),
    ).toBeInTheDocument();
  });

  it("calls useCreateTag with the form payload when the create dialog is submitted", async () => {
    renderWithProviders(<TagsTab />);
    fireEvent.click(screen.getByRole("button", { name: /new tag/i }));
    fireEvent.change(screen.getByLabelText(/^name$/i), {
      target: { value: "Staging" },
    });
    fireEvent.change(screen.getByLabelText(/^description$/i), {
      target: { value: "For testing" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockCreateTag).toHaveBeenCalledTimes(1);
    });
    expect(mockCreateTag).toHaveBeenCalledWith({
      name: "Staging",
      color: "slate",
      description: "For testing",
    });
  });
});
