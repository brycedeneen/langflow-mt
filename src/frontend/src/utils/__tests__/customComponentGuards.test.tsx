/**
 * Tests for the useCustomComponentsAllowed guard hook.
 *
 * Covers design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
 */
import { fireEvent, render, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import {
  flowJsonHasCustomComponent,
  useCustomComponentsAllowed,
} from "../customComponentGuards";

// Hoisted mocks — both stores/queries the hook depends on.
let mockAuthState: any;
let mockConfigData: any;

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: any) => selector(mockAuthState),
}));

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ data: mockConfigData }),
}));

// Spy for CodeAreaModal props — Task 10 tests read this to assert readonly.
const codeAreaModalPropSpy = jest.fn();

// Mock CodeAreaModal at the module level so both caller tests below pick it up.
// The real modal pulls in a very large dep graph (monaco, flowStore, etc.) — a
// prop-spy stub is enough to verify the readonly wiring.
jest.mock("@/modals/codeAreaModal", () => ({
  __esModule: true,
  default: (props: any) => {
    codeAreaModalPropSpy(props);
    return null;
  },
}));

// Sibling modals inside toolbar-modals.tsx pull in large dep graphs (nanoid,
// monaco, flowStore) that Jest's transform config can't handle in this
// lightweight unit-test. Stub them — only CodeAreaModal matters for Task 10.
jest.mock("@/modals/editNodeModal", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/modals/confirmationModal", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/modals/shareModal", () => ({
  __esModule: true,
  default: () => null,
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useCustomComponentsAllowed", () => {
  beforeEach(() => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: false };
  });

  it("returns false for a tenant when the fleet flag is off", () => {
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });

  it("returns true for a platform admin regardless of the fleet flag", () => {
    mockAuthState = { userData: { is_platform_admin: true } };
    mockConfigData = { allow_custom_components: false };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(true);
  });

  it("returns true for any user when the fleet flag is on", () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: true };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(true);
  });

  it("returns false when userData is null (unauthenticated boot state)", () => {
    mockAuthState = { userData: null };
    mockConfigData = { allow_custom_components: false };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });

  it("returns false when config has not loaded yet (data undefined)", () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = undefined;
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });
});

describe("flowJsonHasCustomComponent", () => {
  it("returns false for null / non-object input", () => {
    expect(flowJsonHasCustomComponent(null)).toBe(false);
    expect(flowJsonHasCustomComponent(undefined)).toBe(false);
    expect(flowJsonHasCustomComponent("not-a-flow" as any)).toBe(false);
  });

  it("returns false for a flow with no nodes", () => {
    expect(flowJsonHasCustomComponent({ data: { nodes: [], edges: [] } })).toBe(false);
    expect(flowJsonHasCustomComponent({ nodes: [], edges: [] })).toBe(false);
  });

  it("returns true when a node has a non-empty code.value", () => {
    const flow = {
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "def evil(): pass" } } } },
          },
        ],
        edges: [],
      },
    };
    expect(flowJsonHasCustomComponent(flow)).toBe(true);
  });

  it("handles bare-flow shape (no outer data wrapper)", () => {
    const flow = {
      nodes: [
        {
          id: "n1",
          data: { node: { template: { code: { value: "def evil(): pass" } } } },
        },
      ],
      edges: [],
    };
    expect(flowJsonHasCustomComponent(flow)).toBe(true);
  });

  it("returns false when a node has an empty code.value", () => {
    const flow = {
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "" } } } },
          },
        ],
        edges: [],
      },
    };
    expect(flowJsonHasCustomComponent(flow)).toBe(false);
  });

  it("returns false when a node has no code field at all", () => {
    const flow = {
      data: {
        nodes: [
          { id: "n1", data: { node: { template: {} } } },
        ],
        edges: [],
      },
    };
    expect(flowJsonHasCustomComponent(flow)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Task 10 — CodeAreaModal readonly wiring at the two user-facing edit-code
// callers.
//
// The callers rely on useCustomComponentsAllowed() to decide whether to force
// readonly=true. These tests drive the hook via the already-hoisted
// mockAuthState / mockConfigData mocks above, and assert that the real caller
// passes readonly={!allowed} through to CodeAreaModal (whose default export is
// stubbed by the module-level jest.mock at the top of this file).
// ---------------------------------------------------------------------------

describe("CodeAreaModal readonly gating — toolbar-modals (Task 10)", () => {
  beforeEach(() => {
    codeAreaModalPropSpy.mockClear();
  });

  const renderToolbarModals = () => {
    // Require inside the test so the module-level jest.mock for
    // @/modals/codeAreaModal is in effect.
    const {
      default: ToolbarModals,
    } = require("@/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals");

    const props: any = {
      showModalAdvanced: false,
      showconfirmShare: false,
      showOverrideModal: false,
      openModal: true,
      hasCode: true,
      setShowModalAdvanced: jest.fn(),
      setShowconfirmShare: jest.fn(),
      setShowOverrideModal: jest.fn(),
      setOpenModal: jest.fn(),
      data: {
        id: "component-1",
        node: { template: { code: { value: "" } } },
      },
      flowComponent: { name: "f" } as any,
      handleOnNewValue: jest.fn(),
      handleNodeClass: jest.fn(),
      setToolMode: jest.fn(),
      setSuccessData: jest.fn(),
      addFlow: jest.fn(),
    };

    return render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ToolbarModals {...props} />
      </QueryClientProvider>,
    );
  };

  it("passes readonly=true when the guard returns false (tenant, flag off)", async () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: false };

    renderToolbarModals();

    // CodeAreaModal is React.lazy()-loaded; wait for the Suspense boundary to
    // resolve through the jest module mock before asserting on the spy.
    await waitFor(() => expect(codeAreaModalPropSpy).toHaveBeenCalled());
    const lastCall =
      codeAreaModalPropSpy.mock.calls[codeAreaModalPropSpy.mock.calls.length - 1][0];
    expect(lastCall.readonly).toBe(true);
  });

  it("passes readonly=false for a platform admin", async () => {
    mockAuthState = { userData: { is_platform_admin: true } };
    mockConfigData = { allow_custom_components: false };

    renderToolbarModals();

    await waitFor(() => expect(codeAreaModalPropSpy).toHaveBeenCalled());
    const lastCall =
      codeAreaModalPropSpy.mock.calls[codeAreaModalPropSpy.mock.calls.length - 1][0];
    expect(lastCall.readonly).toBe(false);
  });

  it("passes readonly=false when the fleet flag is on", async () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: true };

    renderToolbarModals();

    await waitFor(() => expect(codeAreaModalPropSpy).toHaveBeenCalled());
    const lastCall =
      codeAreaModalPropSpy.mock.calls[codeAreaModalPropSpy.mock.calls.length - 1][0];
    expect(lastCall.readonly).toBe(false);
  });
});

describe("CodeAreaModal readonly gating — codeAreaComponent (Task 10)", () => {
  beforeEach(() => {
    codeAreaModalPropSpy.mockClear();
  });

  const renderCodeAreaComponent = () => {
    const {
      default: CodeAreaComponent,
    } = require("@/components/core/parameterRenderComponent/components/codeAreaComponent");

    const props: any = {
      value: "",
      handleOnNewValue: jest.fn(),
      disabled: false,
      editNode: false,
      nodeClass: { template: {} },
      handleNodeClass: jest.fn(),
      id: "code-area-1",
      placeholder: "code",
      showParameter: true,
    };

    return render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <CodeAreaComponent {...props} />
      </QueryClientProvider>,
    );
  };

  it("passes readonly=true when the guard returns false (tenant, flag off)", async () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: false };

    const { getByTestId } = renderCodeAreaComponent();

    // CodeAreaModal is now React.lazy()-loaded and only mounts after the user
    // clicks the trigger. Click the wrapper button (test-id matches the inner
    // span's id) to mount the modal, then wait for Suspense to resolve.
    fireEvent.click(getByTestId("code-area-1").closest("button")!);
    await waitFor(() => expect(codeAreaModalPropSpy).toHaveBeenCalled());
    const lastCall =
      codeAreaModalPropSpy.mock.calls[codeAreaModalPropSpy.mock.calls.length - 1][0];
    expect(lastCall.readonly).toBe(true);
  });

  it("passes readonly=false for a platform admin", async () => {
    mockAuthState = { userData: { is_platform_admin: true } };
    mockConfigData = { allow_custom_components: false };

    const { getByTestId } = renderCodeAreaComponent();

    fireEvent.click(getByTestId("code-area-1").closest("button")!);
    await waitFor(() => expect(codeAreaModalPropSpy).toHaveBeenCalled());
    const lastCall =
      codeAreaModalPropSpy.mock.calls[codeAreaModalPropSpy.mock.calls.length - 1][0];
    expect(lastCall.readonly).toBe(false);
  });
});
