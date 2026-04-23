/**
 * Tests for the useCustomComponentsAllowed guard hook.
 *
 * Covers design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
 */
import { renderHook } from "@testing-library/react";
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
