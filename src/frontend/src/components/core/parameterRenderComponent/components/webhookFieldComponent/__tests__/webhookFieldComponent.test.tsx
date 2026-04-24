import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AuthContext } from "@/contexts/authContext";
import { TooltipProvider } from "@/components/ui/tooltip";
import WebhookFieldComponent from "..";
import { api } from "@/controllers/API/api";
import useFlowStore from "@/stores/flowStore";
import useAlertStore from "@/stores/alertStore";

jest.mock("@/controllers/API/api", () => ({
  api: { post: jest.fn() },
}));

jest.mock("@/controllers/API/queries/_builds/use-get-builds-polling-mutation", () => ({
  useGetBuildsMutation: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/customization/components/custom-secret-key-modal-button", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/customization/feature-flags", () => ({ ENABLE_DATASTAX_LANGFLOW: false }));
jest.mock("@/customization/utils/get-modal-props", () => ({ getModalPropsApiKey: () => ({}) }));

jest.mock("@/stores/flowStore");
jest.mock("@/stores/alertStore");

const mockPost = api.post as jest.Mock;
const mockUseFlowStore = useFlowStore as unknown as jest.Mock;
const mockUseAlertStore = useAlertStore as unknown as jest.Mock;
const setErrorData = jest.fn();
const setSuccessData = jest.fn();

function renderApiKeyField(flowId = "flow-123") {
  const props: any = {
    value: "",
    handleOnNewValue: jest.fn(),
    editNode: false,
    id: "api_key_input",
    nodeInformationMetadata: { variableName: "api_key", flowId },
    showParameter: true,
  };
  return render(
    <TooltipProvider>
      <AuthContext.Provider value={{ userData: { id: "u1" } } as any}>
        <WebhookFieldComponent {...props} />
      </AuthContext.Provider>
    </TooltipProvider>,
  );
}

beforeEach(() => {
  mockPost.mockReset();
  setErrorData.mockReset();
  setSuccessData.mockReset();
  mockUseAlertStore.mockImplementation((selector: any) =>
    selector({ setErrorData, setSuccessData }),
  );
});

describe("WebhookFieldComponent (api_key variant)", () => {
  it('renders "Generate API Key" when the flow has no webhook yet', () => {
    mockUseFlowStore.mockImplementation((selector: any) =>
      selector({ currentFlow: { id: "flow-123", webhook: false } }),
    );
    renderApiKeyField();
    const btn = screen.getByTestId("btn-generate-webhook-api-key");
    expect(btn).toHaveTextContent("Generate API Key");
  });

  it('renders "Reset API Key" when the flow already has a webhook', () => {
    mockUseFlowStore.mockImplementation((selector: any) =>
      selector({ currentFlow: { id: "flow-123", webhook: true } }),
    );
    renderApiKeyField();
    const btn = screen.getByTestId("btn-generate-webhook-api-key");
    expect(btn).toHaveTextContent("Reset API Key");
  });

  it("POSTs to /flows/{flowId}/webhook-api-key when the button is clicked", async () => {
    mockUseFlowStore.mockImplementation((selector: any) =>
      selector({ currentFlow: { id: "flow-123", webhook: false } }),
    );
    mockPost.mockResolvedValueOnce({ data: { api_key: "ADP-APICPRO-abc123" } });

    renderApiKeyField("flow-123");
    fireEvent.click(screen.getByTestId("btn-generate-webhook-api-key"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][0]).toMatch(/\/flows\/flow-123\/webhook-api-key$/);
    // No positional body or options — reset is a zero-arg POST.
    expect(mockPost.mock.calls[0][1]).toBeUndefined();
  });

  it("shows an error toast when the API call fails", async () => {
    mockUseFlowStore.mockImplementation((selector: any) =>
      selector({ currentFlow: { id: "flow-123", webhook: true } }),
    );
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: "Flow does not have a webhook component" } },
    });

    renderApiKeyField("flow-123");
    fireEvent.click(screen.getByTestId("btn-generate-webhook-api-key"));

    await waitFor(() => expect(setErrorData).toHaveBeenCalledTimes(1));
    expect(setErrorData.mock.calls[0][0]).toEqual({
      title: "Failed to generate API key",
      list: ["Flow does not have a webhook component"],
    });
  });
});
