/**
 * Tests for the secret-rotation toast surfaced from useSaveFlow when the
 * server's autosave response carries `refused_secret_fields` (Branch-5
 * overwrite refusals from `auto_secrets.py::promote_plaintext_secrets_to_variables`).
 *
 * The save itself succeeded — only the secret rotation didn't reach Vault —
 * so the toast severity must be "notice", not "error".
 */

import { act, renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks — hoisted before imports
// ---------------------------------------------------------------------------

const setErrorDataMock = jest.fn();
const setNoticeDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setErrorData: setErrorDataMock,
      setNoticeData: setNoticeDataMock,
    }),
}));

const setFlowsMock = jest.fn();
const setSaveLoadingMock = jest.fn();
jest.mock("@/stores/flowsManagerStore", () => {
  const store: any = (selector: any) =>
    selector({
      setFlows: setFlowsMock,
      setSaveLoading: setSaveLoadingMock,
    });
  store.getState = () => ({
    flows: [{ id: "flow-1", name: "Test Flow" }],
    currentFlow: { id: "flow-1", name: "Test Flow" },
  });
  return { __esModule: true, default: store };
});

const setCurrentFlowMock = jest.fn();
jest.mock("@/stores/flowStore", () => {
  const store: any = (selector: any) =>
    selector({ setCurrentFlow: setCurrentFlowMock });
  store.getState = () => ({
    currentFlow: {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [] },
    },
    nodes: [],
    edges: [],
    reactFlowInstance: { getViewport: () => ({ zoom: 1, x: 0, y: 0 }) },
  });
  return { __esModule: true, default: store };
});

// usePatchUpdateFlow returns a `mutate(payload, { onSuccess, onError })` shape.
// We capture the mutate spy so each test can drive `onSuccess` with whatever
// the server "echoes back" — including refused_secret_fields.
const mutateMock = jest.fn();
jest.mock("@/controllers/API/queries/flows/use-patch-update-flow", () => ({
  usePatchUpdateFlow: () => ({ mutate: mutateMock }),
}));

jest.mock("@/controllers/API/queries/flows/use-get-flow", () => ({
  useGetFlow: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  customStringify: (v: unknown) => JSON.stringify(v),
}));

// ---------------------------------------------------------------------------
// Subject under test
// ---------------------------------------------------------------------------

import useSaveFlow from "../use-save-flow";

describe("useSaveFlow refused_secret_fields handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("fires a notice toast per refused field with display_name when present", async () => {
    const { result } = renderHook(() => useSaveFlow());
    const saveFlow = result.current;

    // Fire saveFlow with a flow whose stringify differs from the saved one
    // (so we hit the mutate branch).
    const dirtyFlow: any = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [{ id: "n1" }], edges: [] },
    };

    // Drive mutate so onSuccess runs synchronously with our fixture.
    mutateMock.mockImplementation((_payload, { onSuccess }) => {
      onSuccess({
        id: "flow-1",
        name: "Test Flow",
        data: { nodes: [], edges: [] },
        refused_secret_fields: [
          { node_id: "ADPAuth-1", field_name: "client_id", display_name: "Client ID" },
          { node_id: "ADPAuth-1", field_name: "api_key", display_name: null },
        ],
      });
    });

    await act(async () => {
      await saveFlow(dirtyFlow);
    });

    expect(setNoticeDataMock).toHaveBeenCalledTimes(2);
    expect(setNoticeDataMock).toHaveBeenNthCalledWith(1, {
      title:
        '"Client ID" was reset to protect saved credentials. ' +
        "To update the saved secret, clear the field and save again.",
    });
    // Falls back to field_name when display_name is missing.
    expect(setNoticeDataMock).toHaveBeenNthCalledWith(2, {
      title:
        '"api_key" was reset to protect saved credentials. ' +
        "To update the saved secret, clear the field and save again.",
    });
    // Save succeeded — must NOT raise an error toast.
    expect(setErrorDataMock).not.toHaveBeenCalled();
  });

  it("does not toast when refused_secret_fields is empty/missing", async () => {
    const { result } = renderHook(() => useSaveFlow());
    const saveFlow = result.current;
    const dirtyFlow: any = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [{ id: "n2" }], edges: [] },
    };

    mutateMock.mockImplementation((_payload, { onSuccess }) => {
      // No refused_secret_fields at all (legacy/successful save).
      onSuccess({
        id: "flow-1",
        name: "Test Flow",
        data: { nodes: [], edges: [] },
      });
    });

    await act(async () => {
      await saveFlow(dirtyFlow);
    });

    expect(setNoticeDataMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).not.toHaveBeenCalled();
  });
});
