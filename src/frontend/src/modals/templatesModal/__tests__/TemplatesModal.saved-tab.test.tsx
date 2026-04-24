import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { track } from "@/customization/utils/analytics";
import { updateIds } from "@/utils/reactflowUtils";
import TemplatesModal from "../index";

const mockAddFlow = jest.fn().mockResolvedValue("new-flow-id");
const mockApiGet = jest.fn();

jest.mock("@/controllers/API/queries/categories", () => ({
  __esModule: true,
  useListCategories: () => ({
    data: [],
    isPending: false,
  }),
  useCreateCategory: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
  useUpdateCategory: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
  useDeleteCategory: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
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

jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => ({
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
  }),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

jest.mock("@/controllers/API/api", () => ({
  __esModule: true,
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  __esModule: true,
  getURL: (key: string) => `/api/v1/${key.toLowerCase()}`,
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ examples: [], setExamples: jest.fn() }),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  __esModule: true,
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

jest.mock("../components/GetStartedComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="get-started-stub" />,
}));

jest.mock("@/utils/reactflowUtils", () => ({
  __esModule: true,
  updateIds: jest.fn(),
}));

describe("TemplatesModal — Saved Templates tab", () => {
  beforeEach(() => {
    mockAddFlow.mockClear();
    mockApiGet.mockReset();
    (updateIds as jest.Mock).mockClear();
    (track as jest.Mock).mockClear();
  });

  it("shows the Saved Templates nav item and switches to it on click", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <TooltipProvider>
            <TemplatesModal open={true} setOpen={jest.fn()} />
          </TooltipProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const navItem = screen.getByTestId("side_nav_options_saved-templates");
    expect(navItem).toBeInTheDocument();

    fireEvent.click(navItem);
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
  });

  it("creates a flow from a saved template on Start building", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        id: "11111111-1111-1111-1111-111111111111",
        name: "Support Agent",
        description: "Frontline triage",
        icon: "Bot",
        gradient: "2",
        nodes: [{ id: "node-a" }],
        edges: [{ id: "edge-a" }],
        created_at: "2026-04-20T00:00:00Z",
        updated_at: "2026-04-20T00:00:00Z",
      },
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <TooltipProvider>
            <TemplatesModal open={true} setOpen={jest.fn()} />
          </TooltipProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByTestId("side_nav_options_saved-templates"));
    fireEvent.click(screen.getByText("Support Agent"));
    fireEvent.click(screen.getByRole("button", { name: /start building/i }));

    await waitFor(() => expect(mockAddFlow).toHaveBeenCalledTimes(1));

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/templates/11111111-1111-1111-1111-111111111111",
    );
    const callArg = mockAddFlow.mock.calls[0][0];
    expect(callArg.flow.name).toBe("Support Agent");
    expect(callArg.flow.data.nodes).toEqual([{ id: "node-a" }]);
    expect(callArg.flow.data.edges).toEqual([{ id: "edge-a" }]);
    expect(callArg.built_with_assist).toBe(false);
    expect(callArg.based_on_template_flow_id).toBeNull();

    expect(updateIds).toHaveBeenCalledWith(callArg.flow.data);
    expect(track).toHaveBeenCalledWith("New Flow Created", {
      template: "Support Agent",
      entry: "start-building",
    });
  });
});
