import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import SavedTemplatesContent from "../index";

const withQueryClient = (ui: ReactNode) => (
  <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>
);

// Mock the list-templates hook. Each test overrides the return value.
const mockUseListTemplates = jest.fn();
jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => mockUseListTemplates(),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

jest.mock("@/controllers/API/queries/memberships", () => ({
  __esModule: true,
  useListMyMemberships: () => ({ data: [], isPending: false }),
}));

jest.mock("@/controllers/API/queries/templates/use-archive-template", () => ({
  __esModule: true,
  useArchiveTemplate: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/templates/use-unarchive-template", () => ({
  __esModule: true,
  useUnarchiveTemplate: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/templates/use-hard-delete-template", () => ({
  __esModule: true,
  useHardDeleteTemplate: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
}));

// genericIconComponent renders <svg>s that pull from lucide dynamic imports;
// stub it out so tests are deterministic.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

describe("SavedTemplatesContent", () => {
  beforeEach(() => {
    mockUseListTemplates.mockReset();
  });

  it("shows a loading skeleton while fetching", () => {
    mockUseListTemplates.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch: jest.fn(),
    });
    render(
      withQueryClient(
        <SavedTemplatesContent
          selectedTemplate={null}
          onSelectTemplate={jest.fn()}
          loading={false}
        />,
      ),
    );
    expect(screen.getByTestId("saved-templates-loading")).toBeInTheDocument();
  });

  it("renders an empty state when the list is empty", () => {
    mockUseListTemplates.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    render(
      withQueryClient(
        <SavedTemplatesContent
          selectedTemplate={null}
          onSelectTemplate={jest.fn()}
          loading={false}
        />,
      ),
    );
    expect(screen.getByTestId("saved-templates-empty")).toBeInTheDocument();
    expect(screen.getByText(/no saved templates yet/i)).toBeInTheDocument();
  });

  it("renders an error state with a retry button", () => {
    const refetch = jest.fn();
    mockUseListTemplates.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    });
    render(
      withQueryClient(
        <SavedTemplatesContent
          selectedTemplate={null}
          onSelectTemplate={jest.fn()}
          loading={false}
        />,
      ),
    );
    expect(screen.getByTestId("saved-templates-error")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders a card per template and maps ids with the tpl: prefix", () => {
    mockUseListTemplates.mockReturnValue({
      data: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Support Agent",
          description: "Frontline triage",
          icon: "Bot",
          gradient: "2",
          categories: [],
          tags: [],
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
        {
          id: "22222222-2222-2222-2222-222222222222",
          name: "Billing Q&A",
          description: null,
          icon: null,
          gradient: null,
          categories: [],
          tags: [],
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
      ],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    const onSelect = jest.fn();
    render(
      withQueryClient(
        <SavedTemplatesContent
          selectedTemplate={null}
          onSelectTemplate={onSelect}
          loading={false}
        />,
      ),
    );
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
    expect(screen.getByText("Billing Q&A")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Support Agent"));
    expect(onSelect).toHaveBeenCalledWith(
      "tpl:11111111-1111-1111-1111-111111111111",
    );
  });

  it("marks the matching card as selected", () => {
    mockUseListTemplates.mockReturnValue({
      data: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Support Agent",
          description: "Frontline triage",
          icon: "Bot",
          gradient: "2",
          categories: [],
          tags: [],
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
      ],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    const { container } = render(
      withQueryClient(
        <SavedTemplatesContent
          selectedTemplate="tpl:11111111-1111-1111-1111-111111111111"
          onSelectTemplate={jest.fn()}
          loading={false}
        />,
      ),
    );
    // TemplateCardComponent applies border-primary on the outer wrapper when selected.
    expect(container.querySelector(".border-primary")).toBeInTheDocument();
  });
});
