/**
 * Tests for reconcileEdgeHandleIds — rewrites stale edge handle strings so
 * React Flow's DOM-level handle lookup succeeds after a component's
 * input_types/output_types change (fixes error #008).
 */

import type { FlowType } from "@/types/flow";
import {
  handlesMatch,
  reconcileEdgeHandleIds,
  scapedJSONStringfy,
  scapeJSONParse,
} from "@/utils/reactflowUtils";

// Stub out modules that pull in DOM/zustand side effects at import time.
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: () => ({ edges: [] }) },
}));
jest.mock("@/customization/utils/custom-download-json", () => ({
  customDownloadNodeJson: jest.fn(),
}));
jest.mock("@/customization/utils/custom-reactFlowUtils", () => ({
  customDownloadFlow: jest.fn(),
}));

function makeFlow({
  parserInputTypes,
  storedTargetInputTypes,
  apiOutputTypes,
  storedSourceOutputTypes,
  storedTargetFieldName = "input_data",
}: {
  parserInputTypes: string[];
  storedTargetInputTypes: string[];
  apiOutputTypes?: string[];
  storedSourceOutputTypes?: string[];
  storedTargetFieldName?: string;
}): FlowType {
  const parserId = "ParserComponent-AAAAA";
  const apiId = "APIRequest-BBBBB";

  const storedTargetHandle = scapedJSONStringfy({
    fieldName: storedTargetFieldName,
    id: parserId,
    inputTypes: storedTargetInputTypes,
    type: "other",
  });

  const storedSourceHandle = scapedJSONStringfy({
    dataType: "APIRequest",
    id: apiId,
    name: "data",
    output_types: storedSourceOutputTypes ?? ["JSON"],
  });

  const parserNode = {
    id: parserId,
    type: "genericNode",
    data: {
      id: parserId,
      type: "ParserComponent",
      node: {
        template: {
          input_data: {
            type: "other",
            input_types: parserInputTypes,
          },
        },
        outputs: [],
      },
    },
  };

  const apiNode = {
    id: apiId,
    type: "genericNode",
    data: {
      id: apiId,
      type: "APIRequest",
      node: {
        template: {},
        outputs: [
          {
            name: "data",
            types: apiOutputTypes ?? ["JSON"],
            selected: (apiOutputTypes ?? ["JSON"])[0],
          },
        ],
      },
    },
  };

  const edge = {
    id: "edge-1",
    source: apiId,
    target: parserId,
    sourceHandle: storedSourceHandle,
    targetHandle: storedTargetHandle,
    data: {
      sourceHandle: scapeJSONParse(storedSourceHandle),
      targetHandle: scapeJSONParse(storedTargetHandle),
    },
  };

  return {
    id: "flow-1",
    name: "test",
    data: {
      nodes: [apiNode, parserNode],
      edges: [edge],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  } as unknown as FlowType;
}

describe("reconcileEdgeHandleIds", () => {
  it("rewrites target handle when component input_types grew (Parser case)", () => {
    const flow = makeFlow({
      parserInputTypes: ["DataFrame", "Table", "Data", "JSON"],
      storedTargetInputTypes: ["DataFrame", "Data"],
    });
    const edge = flow.data!.edges[0];
    const before = edge.targetHandle;

    reconcileEdgeHandleIds(flow);

    const after = edge.targetHandle;
    expect(after).not.toEqual(before);
    const parsed = scapeJSONParse(after!);
    expect(parsed.inputTypes).toEqual([
      "DataFrame",
      "Table",
      "Data",
      "JSON",
    ]);
    // handlesMatch against the rewritten string is trivially true; the
    // meaningful invariant is that it equals the exact id the node renders.
    expect(handlesMatch(after!, before!)).toBe(true);
  });

  it("leaves handle untouched when the fieldName no longer exists", () => {
    const flow = makeFlow({
      parserInputTypes: ["DataFrame", "Table", "Data", "JSON"],
      storedTargetInputTypes: ["DataFrame", "Data"],
      storedTargetFieldName: "missing_field",
    });
    const edge = flow.data!.edges[0];
    const before = edge.targetHandle;

    reconcileEdgeHandleIds(flow);

    expect(edge.targetHandle).toEqual(before);
  });

  it("is a no-op when stored handle already matches current schema", () => {
    const flow = makeFlow({
      parserInputTypes: ["DataFrame", "Data"],
      storedTargetInputTypes: ["DataFrame", "Data"],
    });
    const edge = flow.data!.edges[0];
    const before = edge.targetHandle;

    reconcileEdgeHandleIds(flow);

    expect(edge.targetHandle).toEqual(before);
  });

  it("rewrites source handle when output migrated (Data → JSON)", () => {
    const flow = makeFlow({
      parserInputTypes: ["DataFrame", "Data"],
      storedTargetInputTypes: ["DataFrame", "Data"],
      apiOutputTypes: ["JSON"],
      storedSourceOutputTypes: ["Data"],
    });
    const edge = flow.data!.edges[0];
    const before = edge.sourceHandle;

    reconcileEdgeHandleIds(flow);

    const after = edge.sourceHandle;
    expect(after).not.toEqual(before);
    const parsed = scapeJSONParse(after!);
    expect(parsed.output_types).toEqual(["JSON"]);
  });

  it("does not touch edges whose nodes are missing", () => {
    const flow = makeFlow({
      parserInputTypes: ["DataFrame", "Table", "Data", "JSON"],
      storedTargetInputTypes: ["DataFrame", "Data"],
    });
    const edge = flow.data!.edges[0];
    const before = edge.targetHandle;
    // simulate a missing target node
    flow.data!.nodes = flow.data!.nodes.filter((n) => n.id !== edge.target);

    reconcileEdgeHandleIds(flow);

    expect(edge.targetHandle).toEqual(before);
  });
});
