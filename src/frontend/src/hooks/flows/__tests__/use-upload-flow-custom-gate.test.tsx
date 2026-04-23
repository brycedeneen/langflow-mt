import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import useUploadFlow from "../use-upload-flow";

let mockAllowed = true;
const mockSetErrorData = jest.fn();
const mockAddFlow = jest.fn();
const mockPaste = jest.fn();

jest.mock("@/utils/customComponentGuards", () => ({
  useCustomComponentsAllowed: () => mockAllowed,
  flowJsonHasCustomComponent: (flow: any) =>
    Boolean(
      flow?.data?.nodes?.[0]?.data?.node?.template?.code?.value ||
        flow?.nodes?.[0]?.data?.node?.template?.code?.value,
    ),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector?: any) => {
    const state = { setErrorData: mockSetErrorData };
    return typeof selector === "function" ? selector(state) : state;
  },
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: any) => {
    const state = { paste: mockPaste };
    return typeof selector === "function" ? selector(state) : state;
  },
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processDataFromFlow: jest.fn(async () => undefined),
}));

jest.mock("@/helpers/create-file-upload", () => ({
  createFileUpload: jest.fn(async () => []),
}));

// jsdom's File lacks .text(); stub the helper to read via FileReader.
jest.mock("@/helpers/get-objects-from-filelist", () => ({
  getObjectsFromFilelist: jest.fn(async (files: File[]) => {
    const out: any[] = [];
    for (const file of files) {
      const text = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result ?? ""));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file);
      });
      out.push(JSON.parse(text));
    }
    return out;
  }),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useUploadFlow custom-component gate", () => {
  beforeEach(() => {
    mockSetErrorData.mockReset();
    mockAddFlow.mockReset();
    mockPaste.mockReset();
  });

  it("blocks upload and raises an alert when gate is active and flow has custom code", async () => {
    mockAllowed = false;
    const { result } = renderHook(() => useUploadFlow(), { wrapper });
    const customFlow = {
      name: "x",
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "def bad(): pass" } } } },
          },
        ],
        edges: [],
      },
    };
    const file = new File([JSON.stringify(customFlow)], "flow.json", {
      type: "application/json",
    });
    await act(async () => {
      await result.current({ files: [file] });
    });
    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({
        title: expect.stringContaining("Custom components are not allowed"),
      }),
    );
    expect(mockAddFlow).not.toHaveBeenCalled();
    expect(mockPaste).not.toHaveBeenCalled();
  });

  it("allows upload when guard returns true (platform admin or fleet flag on)", async () => {
    mockAllowed = true;
    const { result } = renderHook(() => useUploadFlow(), { wrapper });
    const customFlow = {
      name: "x",
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "def ok(): pass" } } } },
          },
        ],
        edges: [],
      },
    };
    const file = new File([JSON.stringify(customFlow)], "flow.json", {
      type: "application/json",
    });
    await act(async () => {
      await result.current({ files: [file] });
    });
    expect(mockSetErrorData).not.toHaveBeenCalled();
    expect(mockAddFlow).toHaveBeenCalled();
  });

  it("allows upload of catalog-only flow for a gated tenant", async () => {
    mockAllowed = false;
    const { result } = renderHook(() => useUploadFlow(), { wrapper });
    const catalogFlow = {
      name: "y",
      data: { nodes: [], edges: [] },
    };
    const file = new File([JSON.stringify(catalogFlow)], "flow.json", {
      type: "application/json",
    });
    await act(async () => {
      await result.current({ files: [file] });
    });
    expect(mockSetErrorData).not.toHaveBeenCalled();
    expect(mockAddFlow).toHaveBeenCalled();
  });
});
