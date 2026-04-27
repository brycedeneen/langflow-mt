/**
 * Tests for retry visual states on the canvas node.
 *
 * Covers two layers:
 *   A) getSpecificClassFromBuildStatus maps RETRYING → amber border+pulse,
 *      RETRY_EXHAUSTED → red border.
 *   B) GenericNode renders the amber overlay text when retryState = retrying.
 */

import { render, screen } from "@testing-library/react";

// -----------------------------------------------------------------------
// Shared mocks (needed by GenericNode test suite)
// -----------------------------------------------------------------------

jest.mock("@xyflow/react", () => ({
  Handle: ({
    children,
    "data-testid": testId,
    ...rest
  }: React.PropsWithChildren<{ "data-testid"?: string; [key: string]: any }>) => (
    <div data-testid={testId} {...rest}>
      {children}
    </div>
  ),
  Position: { Left: "left", Right: "right" },
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("react-hotkeys-hook", () => ({
  useHotkeys: jest.fn(),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | undefined | false | null)[]) =>
    classes.filter(Boolean).join(" "),
  classNames: (...classes: (string | undefined | false | null)[]) =>
    classes.filter(Boolean).join(" "),
  logFirstMessage: jest.fn(),
  logHasMessage: jest.fn(),
  logTypeIsError: jest.fn(),
  logTypeIsUnknown: jest.fn(),
  groupByFamily: jest.fn(),
}));

jest.mock("@/utils/styleUtils", () => ({
  nodeColorsName: {},
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: (obj: unknown) => JSON.stringify(obj),
  scapeJSONParse: (str: string) => JSON.parse(str),
  isValidConnection: jest.fn(() => false),
  getGroupOutputNodeId: jest.fn(),
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: (fn: (s: any) => any) => fn,
}));

jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: React.PropsWithChildren) => <>{children}</>,
  TooltipTrigger: ({
    children,
  }: React.PropsWithChildren<{ asChild?: boolean }>) => <>{children}</>,
  TooltipContent: ({ children }: React.PropsWithChildren) => (
    <div role="tooltip">{children}</div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...rest
  }: React.PropsWithChildren<{ onClick?: () => void; [key: string]: any }>) => (
    <button onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (s: any) => any) =>
    selector({ types: {}, templates: {}, data: {} }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ takeSnapshot: jest.fn() }),
}));

jest.mock("@/stores/shortcuts", () => ({
  useShortcutsStore: (selector: (s: any) => any) =>
    selector({ shortcuts: [], update: "", outputInspection: "" }),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (s: any) => any) => selector({ dark: false }),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutate: jest.fn() }),
  }),
);

jest.mock("@/customization/components/custom-NodeStatus", () => ({
  CustomNodeStatus: () => <div data-testid="node-status" />,
}));

jest.mock("@/modals/updateComponentModal", () => ({
  __esModule: true,
  default: () => <div data-testid="update-component-modal" />,
}));

jest.mock("@/shared/hooks/use-alternate", () => ({
  useAlternate: (initial: boolean) => [initial, jest.fn(), jest.fn()],
}));

jest.mock("@/shared/hooks/use-change-on-unfocus", () => ({
  useChangeOnUnfocus: jest.fn(),
}));

jest.mock(
  "@/CustomNodes/GenericNode/components/NodeOutputParameter/NodeOutputs",
  () => ({
    __esModule: true,
    default: () => <div data-testid="node-outputs" />,
  }),
);

jest.mock(
  "@/CustomNodes/GenericNode/components/RenderInputParameters",
  () => ({
    __esModule: true,
    default: () => <div data-testid="render-input-params" />,
  }),
);

jest.mock("@/pages/FlowPage/components/nodeToolbarComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="node-toolbar" />,
}));

jest.mock(
  "@/CustomNodes/GenericNode/components/NodeUpdateComponent",
  () => ({
    __esModule: true,
    default: () => <div data-testid="node-update-component" />,
  }),
);

jest.mock(
  "@/CustomNodes/GenericNode/components/NodeLegacyComponent",
  () => ({
    __esModule: true,
    default: () => <div data-testid="node-legacy-component" />,
  }),
);

jest.mock("@/CustomNodes/GenericNode/components/NodeDescription", () => ({
  __esModule: true,
  default: () => <div data-testid="node-description" />,
}));

jest.mock("@/CustomNodes/GenericNode/components/NodeName", () => ({
  __esModule: true,
  default: () => <div data-testid="node-name" />,
}));

jest.mock("@/CustomNodes/GenericNode/components/nodeIcon", () => ({
  NodeIcon: () => <div data-testid="node-icon" />,
}));

jest.mock("@/CustomNodes/hooks/use-update-node-code", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("@/CustomNodes/helpers/process-node-advanced-fields", () => ({
  processNodeAdvancedFields: jest.fn(),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <svg data-testid={`icon-${name}`} />
  ),
}));

// flowStore mock
jest.mock("@/stores/flowStore", () => {
  const state = {
    deleteNode: jest.fn(),
    setNode: jest.fn(),
    edges: [],
    setEdges: jest.fn(),
    dismissedNodes: [],
    addDismissedNodes: jest.fn(),
    removeDismissedNodes: jest.fn(),
    dismissedNodesLegacy: [],
    addDismissedNodesLegacy: jest.fn(),
    componentsToUpdate: [],
    currentFlow: null,
    rightClickedNodeId: null,
    nodes: [],
    flowPool: {},
    filterType: null,
    handleDragging: null,
    setHandleDragging: jest.fn(),
    setFilterType: jest.fn(),
    setFilterEdge: jest.fn(),
    setFilterComponent: jest.fn(),
    onConnect: jest.fn(),
    flowBuildStatus: {},
  };
  const store = Object.assign(
    (selector: (s: typeof state) => any) => selector(state),
    { getState: () => state },
  );
  return { __esModule: true, default: store };
});

// useBuildStatus — return null (no active build)
jest.mock("@/CustomNodes/GenericNode/hooks/use-get-build-status", () => ({
  useBuildStatus: () => null,
}));

// useRetryState — controlled per-test
const mockUseRetryState = jest.fn<any, [string]>(() => null);
jest.mock("@/CustomNodes/GenericNode/hooks/use-retry-state", () => ({
  useRetryState: (nodeId: string) => mockUseRetryState(nodeId),
}));

// -----------------------------------------------------------------------
// Imports
// -----------------------------------------------------------------------

import GenericNode from "../index";
import type { NodeDataType } from "@/types/flow";
import { getSpecificClassFromBuildStatus } from "@/CustomNodes/helpers/get-class-from-build-status";
import { BuildStatus } from "@/constants/enums";

const makeData = (): NodeDataType =>
  ({
    id: "vtx-retry-test",
    type: "SomeComponent",
    node: {
      template: { code: { value: "" } },
      outputs: [{ display_name: "Result", name: "result", types: ["str"] }],
      display_name: "SomeComponent",
      description: "",
      frozen: false,
      legacy: false,
    },
  }) as unknown as NodeDataType;

// -----------------------------------------------------------------------
// Suite A: border class helper
// -----------------------------------------------------------------------

describe("getSpecificClassFromBuildStatus — retry states", () => {
  it("returns amber warning border + animate-pulse for RETRYING", () => {
    const cls = getSpecificClassFromBuildStatus(
      BuildStatus.RETRYING,
      null,
      false,
    );
    expect(cls).toContain("border-warning");
    expect(cls).toContain("animate-pulse");
  });

  it("returns red destructive border for RETRY_EXHAUSTED when not building", () => {
    const cls = getSpecificClassFromBuildStatus(
      BuildStatus.RETRY_EXHAUSTED,
      null,
      false,
    );
    expect(cls).toContain("border-destructive");
  });

  it("does NOT return destructive border for RETRY_EXHAUSTED while a build is in progress", () => {
    const cls = getSpecificClassFromBuildStatus(
      BuildStatus.RETRY_EXHAUSTED,
      null,
      true,
    );
    expect(cls).not.toContain("border-destructive");
  });
});

// -----------------------------------------------------------------------
// Suite B: GenericNode overlay
// -----------------------------------------------------------------------

describe("GenericNode retry visuals", () => {
  beforeEach(() => {
    mockUseRetryState.mockReturnValue(null);
  });

  it("renders amber retry overlay text when vertex.retrying state is active", () => {
    mockUseRetryState.mockReturnValue({
      status: "retrying",
      retry_number: 1,
      max_retries: 3,
    });

    render(<GenericNode data={makeData()} selected={false} />);

    expect(screen.getByTestId("retry-overlay")).toBeInTheDocument();
    expect(screen.getByText(/Retrying attempt 1 of 3/)).toBeInTheDocument();
  });

  it("shows correct retry_number when on second attempt", () => {
    mockUseRetryState.mockReturnValue({
      status: "retrying",
      retry_number: 2,
      max_retries: 3,
    });

    render(<GenericNode data={makeData()} selected={false} />);

    expect(screen.getByText(/Retrying attempt 2 of 3/)).toBeInTheDocument();
  });

  it("does NOT render retry overlay when no retry state", () => {
    mockUseRetryState.mockReturnValue(null);

    render(<GenericNode data={makeData()} selected={false} />);

    expect(screen.queryByTestId("retry-overlay")).not.toBeInTheDocument();
  });

  it("does NOT render retry overlay for retry_exhausted (red border only, no banner)", () => {
    mockUseRetryState.mockReturnValue({ status: "retry_exhausted" });

    render(<GenericNode data={makeData()} selected={false} />);

    expect(screen.queryByTestId("retry-overlay")).not.toBeInTheDocument();
  });
});
