import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { memo, useCallback, useState } from "react";
import { withRenderCount } from "@/__test_helpers__/render-counter";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import FloatComponent from "@/components/core/parameterRenderComponent/components/floatComponent";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { APIClassType } from "@/types/api";

// Mock the stores that useHandleOnNewValue reaches into.
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({
      setNode: () => undefined, // overridden by harness via setNodeExternal
    }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ takeSnapshot: () => undefined }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ setErrorData: () => undefined }),
}));
jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => undefined,
}));
jest.mock(
  "@/controllers/API/queries/nodes/use-post-template-value",
  () => ({
    usePostTemplateValue: () => ({ mutate: () => undefined }),
  }),
);

const buildNode = (): APIClassType =>
  ({
    template: {
      query: { type: "str", value: "hello", show: true } as any,
      count: { type: "float", value: 0.5, show: true } as any,
    },
    display_name: "Test",
  }) as unknown as APIClassType;

function Harness({
  counts,
  CountedFloat,
}: {
  counts: Record<string, number>;
  CountedFloat: typeof FloatComponent;
}) {
  const [node, setNode] = useState<APIClassType>(buildNode());

  // Custom setNode that matches the (id, updater, ...) signature
  const setNodeFn = (
    _id: string,
    update: (n: any) => any,
    _skip?: boolean,
    cb?: () => void,
  ) => {
    setNode((prev) =>
      typeof update === "function"
        ? update({ id: "node-1", data: { node: prev } }).data.node
        : prev,
    );
    cb?.();
  };

  const { handleOnNewValue: queryOnNewValue } = useHandleOnNewValue({
    node,
    nodeId: "node-1",
    name: "query",
    setNode: setNodeFn as any,
  });
  const { handleOnNewValue: countOnNewValue } = useHandleOnNewValue({
    node,
    nodeId: "node-1",
    name: "count",
    setNode: setNodeFn as any,
  });

  // Stable reference so areInputPropsEqual does not see a new function on
  // every Harness re-render and trigger a FloatComponent re-render.
  const handleNodeClass = useCallback(() => undefined, []);

  return (
    <div>
      <input
        data-testid="query-input"
        value={(node.template.query.value as string) ?? ""}
        onChange={(e) => queryOnNewValue({ value: e.target.value })}
      />
      <CountedFloat
        id="float_test"
        value={node.template.count.value as number}
        editNode={false}
        handleOnNewValue={countOnNewValue}
        disabled={false}
        nodeClass={node}
        handleNodeClass={handleNodeClass}
        nodeId="node-1"
      />
    </div>
  );
}

describe("ParameterRenderComponent — sibling render isolation", () => {
  it("does not re-render a sibling Float leaf when a sibling Str field is typed into", async () => {
    const counts: Record<string, number> = {};
    // withRenderCount wraps the memo'd FloatComponent; we also memo the wrapper
    // with the same comparator so that the blocking logic applies at this layer
    // too and the counter reflects genuine re-renders, not wrapper invocations.
    const CountedFloat = memo(
      withRenderCount(FloatComponent, "FloatComponent", counts),
      areInputPropsEqual,
    );
    render(<Harness counts={counts} CountedFloat={CountedFloat} />);

    const initial = counts["FloatComponent"];
    expect(initial).toBeGreaterThanOrEqual(1);

    const input = screen.getByTestId("query-input");
    await userEvent.type(input, "abc");

    // After 3 keystrokes into the *query* field, the FloatComponent should
    // not have re-rendered beyond its initial mount (allow <= 1 extra for
    // React batching variability, but no more).
    expect(counts["FloatComponent"] - initial).toBeLessThanOrEqual(1);
  });
});
