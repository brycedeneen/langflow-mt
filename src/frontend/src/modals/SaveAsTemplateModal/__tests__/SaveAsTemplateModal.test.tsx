import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import SaveAsTemplateModal from "../index";

function renderWithProviders(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

// ---- Mocks -----------------------------------------------------------
// Mock the create-template mutation: `useCreateTemplate()` returns `{ mutate, isLoading }`.
const mutateMock = jest.fn();
const listMock = jest.fn();
const updateMock = jest.fn();
jest.mock(
  "@/controllers/API/queries/templates",
  () => ({
    useCreateTemplate: () => ({
      mutate: mutateMock,
      isPending: false,
    }),
    useListTemplates: () => ({ data: listMock() }),
    useUpdateTemplate: () => ({
      mutate: updateMock,
      isPending: false,
    }),
  }),
);

// Default: user is a platform admin so Save button is enabled.
jest.mock("@/hooks/use-is-platform-admin", () => ({
  useIsPlatformAdmin: () => true,
}));

// CategoryChipPicker uses useListCategories — return empty list so it shows
// "No categories defined" and doesn't break rendering.
jest.mock("@/controllers/API/queries/categories", () => ({
  useListCategories: () => ({ data: [] }),
}));

// useListMyMemberships: return empty list so admin with no orgs → no selector shown.
jest.mock("@/controllers/API/queries/memberships", () => ({
  useListMyMemberships: () => ({ data: [], isPending: false }),
}));

// Mock alertStore — match the shape of the existing Zustand selector pattern.
// Existing modals import `useAlertStore` as the default export and call it
// with a selector function.
const successMock = jest.fn();
const errorMock = jest.fn();
jest.mock(
  "@/stores/alertStore",
  () => ({
    __esModule: true,
    default: (selector: any) =>
      selector({
        setSuccessData: successMock,
        setErrorData: errorMock,
        setNoticeData: jest.fn(),
      }),
  }),
);

// ---- Fixture --------------------------------------------------------
function baseFlow() {
  return {
    id: "flow-abc",
    description: "Pre-existing description",
    data: {
      nodes: [
        {
          id: "Node-1",
          data: {
            type: "APIRequest",
            node: {
              display_name: "API Request",
              template: {
                cert_pem: {
                  _input_type: "TextFileSecretInput",
                  auto_promote: true,
                  value: "PEMPLAINTEXT",
                  display_name: "Client Certificate",
                },
                bearer_token: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "tok",
                  display_name: "Bearer Token",
                },
                url_input: {
                  _input_type: "MessageTextInput",
                  value: "https://example.com",
                },
              },
            },
          },
        },
        {
          id: "Node-2",
          data: {
            type: "OpenAI",
            node: {
              display_name: "OpenAI",
              template: {
                api_key: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "sk-xxx",
                  display_name: "API Key",
                },
              },
            },
          },
        },
      ],
      edges: [],
    },
  };
}

describe("SaveAsTemplateModal — submit wiring", () => {
  beforeEach(() => {
    mutateMock.mockReset();
    successMock.mockReset();
    errorMock.mockReset();
    listMock.mockReset();
    updateMock.mockReset();
    listMock.mockReturnValue([]); // default: no templates
  });

  it("renders defaults: empty name, prefilled description, FileText icon", () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    expect(screen.getByLabelText(/^name/i)).toHaveValue("");
    expect(screen.getByLabelText(/description/i)).toHaveValue(
      "Pre-existing description",
    );
    expect(screen.getByRole("button", { name: /choose icon/i })).toBeInTheDocument();
    expect(screen.getByText("FileText")).toBeInTheDocument();
  });

  it("Save button disabled until Name is non-empty", () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    const save = screen.getByRole("button", { name: /save as template/i });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Template" },
    });
    expect(save).toBeEnabled();
  });

  it("submit calls mutation with correct payload shape", () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Template" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [payload] = mutateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload).toMatchObject({
      source_flow_id: "flow-abc",
      name: "My Template",
      description: "Pre-existing description",
      icon: "FileText",
      gradient: "0",
    });
    // All 3 detected credentials are blanked by default.
    expect(payload.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-1", field_name: "bearer_token" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
    expect(payload.blanked_fields).toHaveLength(3);
  });

  it("submit does nothing when flow has no id", () => {
    const flow = { ...baseFlow(), id: undefined };
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={flow} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "X" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    expect(mutateMock).not.toHaveBeenCalled();
  });

  it("on 409 response, shows inline Name error and re-enables button", async () => {
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({
        response: { status: 409, data: { detail: "name conflict" } },
      });
    });
    const onClose = jest.fn();
    renderWithProviders(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(errorMock).not.toHaveBeenCalled();
  });

  it("on non-409 error, fires error toast and keeps modal open", async () => {
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 500, data: {} } });
    });
    const onClose = jest.fn();
    renderWithProviders(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Boom" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(errorMock).toHaveBeenCalledTimes(1);
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("on success, fires success toast and calls onClose", async () => {
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onSuccess?.({ id: "template-new", name: "Saved" });
    });
    const onClose = jest.fn();
    renderWithProviders(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Saved" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(successMock).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it("unchecking a field excludes it from blanked_fields on submit", async () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    // Open the strip panel
    const summary = screen.getByText(/what gets stripped/i);
    fireEvent.click(summary);
    // Uncheck "Bearer Token"
    fireEvent.click(screen.getByRole("checkbox", { name: /bearer token/i }));
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [payload] = mutateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload.blanked_fields).toHaveLength(2);
    expect(payload.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
    expect(payload.blanked_fields).not.toContainEqual({
      node_id: "Node-1",
      field_name: "bearer_token",
    });
  });

  it("re-checking a field re-includes it in blanked_fields on submit", () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    fireEvent.click(screen.getByText(/what gets stripped/i));
    const bearer = screen.getByRole("checkbox", { name: /bearer token/i });
    fireEvent.click(bearer); // uncheck
    fireEvent.click(bearer); // re-check
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    const [payload] = mutateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload.blanked_fields).toHaveLength(3);
    expect(payload.blanked_fields).toContainEqual({
      node_id: "Node-1",
      field_name: "bearer_token",
    });
  });

  it("closing and re-opening the modal resets keptFieldKeys to empty", () => {
    const flow = baseFlow();
    const { rerender } = render(
      <TooltipProvider>
        <SaveAsTemplateModal open={true} onClose={() => {}} flow={flow} />
      </TooltipProvider>,
    );
    // Uncheck a field
    fireEvent.click(screen.getByText(/what gets stripped/i));
    fireEvent.click(screen.getByRole("checkbox", { name: /bearer token/i }));

    // Close
    rerender(
      <TooltipProvider>
        <SaveAsTemplateModal open={false} onClose={() => {}} flow={flow} />
      </TooltipProvider>,
    );
    // Re-open
    rerender(
      <TooltipProvider>
        <SaveAsTemplateModal open={true} onClose={() => {}} flow={flow} />
      </TooltipProvider>,
    );

    // Submit immediately — every field should be blanked again
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    const [payload] = mutateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload.blanked_fields).toHaveLength(3);
  });

  it("409 + matching row in list opens the confirm dialog", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "Pre-existing description of the clashing template",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Pre-existing description of the clashing template/),
    ).toBeInTheDocument();
  });

  it("409 with empty list falls back to inline name error and does not open the dialog", async () => {
    listMock.mockReturnValue(undefined);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    });
    expect(
      screen.queryByRole("button", { name: /^overwrite$/i }),
    ).not.toBeInTheDocument();
  });

  it("clicking Overwrite fires the update mutation with the correct payload", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "x",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^overwrite$/i }));

    expect(updateMock).toHaveBeenCalledTimes(1);
    const [vars] = updateMock.mock.calls[0] as [any, ...unknown[]];
    expect(vars.templateId).toBe("T-1");
    expect(vars.body).toMatchObject({
      source_flow_id: "flow-abc",
      name: "Duplicate",
      icon: "FileText",
      gradient: "0",
    });
    expect(vars.body.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-1", field_name: "bearer_token" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
  });

  it("clicking Cancel closes the dialog, shows inline error, and re-enables Save", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "x",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /^overwrite$/i }),
      ).not.toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    expect(screen.getByRole("button", { name: /save as template/i })).toBeEnabled();
    expect(updateMock).not.toHaveBeenCalled();
  });
});
