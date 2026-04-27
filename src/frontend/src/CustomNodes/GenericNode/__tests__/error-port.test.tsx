/**
 * Tests for the error output port rendered on GenericNode.
 *
 * We test ErrorOutputPort directly — the component that owns data-testid="output-port-error".
 * GenericNode mounts ErrorOutputPort when an output named "error" with
 * types=["ErrorPayload"] is present in node data; the unit tests here verify
 * the component-level contract (testid present/absent) without requiring the
 * full GenericNode store and React-Flow setup.
 */

import { render, screen } from "@testing-library/react";

// --- Mocks -----------------------------------------------------------

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
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: (obj: unknown) => JSON.stringify(obj),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | undefined | false | null)[]) =>
    classes.filter(Boolean).join(" "),
}));

// Tooltip mocks — just render children / content as-is
jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: React.PropsWithChildren) => <>{children}</>,
  TooltipTrigger: ({
    children,
    asChild,
  }: React.PropsWithChildren<{ asChild?: boolean }>) => <>{children}</>,
  TooltipContent: ({ children }: React.PropsWithChildren) => (
    <div role="tooltip">{children}</div>
  ),
}));

// --- Component under test -------------------------------------------

import ErrorOutputPort from "../components/ErrorOutputPort";

// -------------------------------------------------------------------

describe("ErrorOutputPort", () => {
  it("renders the error port with data-testid='output-port-error' when showNode=true", () => {
    render(
      <ErrorOutputPort nodeId="vtx-1" dataType="HTTPRequest" showNode={true} />,
    );
    expect(screen.getByTestId("output-port-error")).toBeInTheDocument();
  });

  it("renders the error port with data-testid='output-port-error' when showNode=false (collapsed)", () => {
    render(
      <ErrorOutputPort nodeId="vtx-1" dataType="HTTPRequest" showNode={false} />,
    );
    expect(screen.getByTestId("output-port-error")).toBeInTheDocument();
  });

  it("shows the correct tooltip text when showNode=true", () => {
    render(
      <ErrorOutputPort nodeId="vtx-1" dataType="HTTPRequest" showNode={true} />,
    );
    expect(
      screen.getByText(
        "Error output — connects to an Error Handler or Agent.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the Error label text inside the error port", () => {
    render(
      <ErrorOutputPort nodeId="vtx-1" dataType="HTTPRequest" showNode={true} />,
    );
    // The component renders a span with text "Error" inside the port row
    expect(screen.getByText("Error")).toBeInTheDocument();
  });
});

// --- Integration: GenericNode mounts ErrorOutputPort when appropriate ---

/**
 * These tests verify that GenericNode correctly mounts/omits ErrorOutputPort
 * based on the outputs array, without requiring a full React-Flow + Zustand
 * harness.  We mock every store and heavy dependency GenericNode imports.
 */

// Mock all Zustand stores and heavy deps GenericNode needs
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

jest.mock("@/CustomNodes/GenericNode/hooks/use-get-build-status", () => ({
  useBuildStatus: () => null,
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

import GenericNode from "../index";
import type { NodeDataType } from "@/types/flow";

const makeData = (
  outputs: Array<{ display_name: string; name: string; types: string[] }>,
): NodeDataType =>
  ({
    id: "vtx-test",
    type: "HTTPRequest",
    node: {
      template: { code: { value: "" } },
      outputs,
      display_name: "HTTPRequest",
      description: "",
      frozen: false,
      legacy: false,
    },
  }) as unknown as NodeDataType;

describe("GenericNode — error port integration", () => {
  it("renders output-port-error when node has an error output", () => {
    const data = makeData([
      { display_name: "Result", name: "result", types: ["str"] },
      { display_name: "Error", name: "error", types: ["ErrorPayload"] },
    ]);
    render(<GenericNode data={data} selected={false} />);
    expect(screen.getByTestId("output-port-error")).toBeInTheDocument();
  });

  it("does NOT render output-port-error when node has no error output", () => {
    const data = makeData([
      { display_name: "Result", name: "result", types: ["str"] },
    ]);
    render(<GenericNode data={data} selected={false} />);
    expect(screen.queryByTestId("output-port-error")).not.toBeInTheDocument();
  });
});
