import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import MappingComponent from "..";

// Mock scrollIntoView for Radix components
Element.prototype.scrollIntoView = jest.fn();

// Mock the mutation hook — returns pre-baked LLM output with one mapping for "full_name"
const mockMutateAsync = jest.fn();
jest.mock(
  "@/controllers/API/queries/assistant/use-data-mapper-auto-map",
  () => ({
    useDataMapperAutoMapMutation: () => ({ mutateAsync: mockMutateAsync }),
  }),
);

// Zustand stores: use a selector-aware mock so both `useFlowStore(selector)`
// and `useFlowStore.getState()` work.
const mockFlowState = {
  edges: [] as Array<{ source: string; target: string }>,
  nodes: [{ id: "n1", data: { node: { id: "n1", display_name: "Driver" } } }],
  getNode: (id: string) =>
    mockFlowState.nodes.find((n) => n.id === id),
};

jest.mock("@/stores/flowStore", () => {
  const useFlowStore: any = (selector?: (state: any) => any) =>
    selector ? selector(mockFlowState) : mockFlowState;
  useFlowStore.getState = () => mockFlowState;
  return { __esModule: true, default: useFlowStore };
});

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector?: (state: any) => any) =>
    selector ? selector({ currentFlowId: "flow-1" }) : { currentFlowId: "flow-1" },
}));

// Mock useVertexBuildShapes so DataMapperModal renders without spinning on builds
jest.mock(
  "@/modals/dataMapperModal/hooks/useVertexBuildShapes",
  () => ({
    useVertexBuildShapes: () => ({ shapes: [], isPending: false }),
  }),
);

// Mock validate mutation so Save path doesn't break (not exercised in these tests)
jest.mock(
  "@/controllers/API/queries/utils/use-post-validate-mapping-config",
  () => ({
    usePostValidateMappingConfig: () => ({
      mutate: jest.fn(),
      isPending: false,
    }),
  }),
);

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
};

const baseConfig = JSON.stringify({
  driver_index: 0,
  inputs: [
    {
      alias: "users",
      schema_source: "autodetect",
      schema: { fields: [{ name: "name", type: "str", required: true }] },
    },
  ],
  destination_schema: [
    { name: "full_name", type: "str", required: true, default: null },
  ],
  mappings: [],
});

const suggestionResponse = {
  data: {
    outputs: [
      {
        outputs: [
          {
            outputs: {
              message: {
                message: JSON.stringify([
                  {
                    destination: "full_name",
                    transform: "direct",
                    sources: [{ input: "users", field: "name" }],
                    config: {},
                  },
                ]),
              },
            },
          },
        ],
      },
    ],
  },
};

describe("MappingComponent suggestions integration", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(suggestionResponse);
  });

  it("renders Suggest button via suggestionsSlot when modal is open", async () => {
    render(
      <MappingComponent
        value={baseConfig}
        handleOnNewValue={jest.fn()}
        nodeId="n1"
        disabled={false}
        id="n1"
        editNode={false}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByTestId("mapping-btn-n1"));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /suggest mappings/i }),
      ).toBeInTheDocument(),
    );
  });

  it("clicking Suggest then Apply-all clears pending state", async () => {
    render(
      <MappingComponent
        value={baseConfig}
        handleOnNewValue={jest.fn()}
        nodeId="n1"
        disabled={false}
        id="n1"
        editNode={false}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByTestId("mapping-btn-n1"));
    const suggestBtn = await screen.findByRole("button", {
      name: /suggest mappings/i,
    });

    await act(async () => {
      fireEvent.click(suggestBtn);
    });

    const applyBtn = await screen.findByRole("button", { name: /apply all/i });
    await act(async () => {
      fireEvent.click(applyBtn);
    });

    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /apply all/i }),
      ).not.toBeInTheDocument(),
    );
  });
});
