import { useMemo } from "react";
import { BuildStatus } from "@/constants/enums";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";
import { PipelineCard } from "./pipeline-card";
import { TestAllButton } from "./test-all-button";
import { computeDagLayout, type LayoutEdge, type LayoutNode } from "./dag-layout";
import type { TestStatus } from "./status-badge";

function deriveStatus(
  entry: { status: BuildStatus } | undefined,
): TestStatus {
  if (!entry) return "not_tested";
  switch (entry.status) {
    case BuildStatus.BUILDING:
      return "testing";
    case BuildStatus.BUILT:
      return "passed";
    case BuildStatus.ERROR:
      return "failed";
    case BuildStatus.TO_BUILD:
    case BuildStatus.INACTIVE:
    default:
      return "not_tested";
  }
}

type Props = {
  onSend: (text: string) => void;
};

export function FlowPipelineView({ onSend }: Props) {
  const nodes = useFlowStore((s) => s.nodes);
  const edges = useFlowStore((s) => s.edges);
  const flowBuildStatus = useFlowStore((s) => s.flowBuildStatus);
  const flowPool = useFlowStore((s) => s.flowPool);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);

  const layoutNodes: LayoutNode[] = useMemo(
    () =>
      nodes.map((n: any) => ({
        id: n.id,
        data: {
          type: n.data?.type ?? n.id,
          display_name:
            n.data?.node?.display_name ?? n.data?.display_name ?? n.id,
          category: n.data?.node?.category ?? n.data?.category,
        },
      })),
    [nodes],
  );

  const layoutEdges: LayoutEdge[] = useMemo(
    () =>
      edges.map((e: any) => ({
        source: e.source,
        target: e.target,
        targetHandleFieldName: e.data?.targetHandle?.fieldName,
      })),
    [edges],
  );

  const layout = useMemo(
    () => computeDagLayout(layoutNodes, layoutEdges),
    [layoutNodes, layoutEdges],
  );

  const anyTesting = useMemo(
    () =>
      Object.values(flowBuildStatus ?? {}).some(
        (v: { status: BuildStatus }) => v?.status === BuildStatus.BUILDING,
      ),
    [flowBuildStatus],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center text-muted-foreground">
        <div className="text-sm">No components yet. Go back to chat and add some.</div>
        <button
          type="button"
          className="text-sm underline"
          onClick={() => setLayoutMode("fullscreen")}
        >
          Back to chat
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">Pipeline</div>
        <TestAllButton anyTesting={anyTesting} />
      </div>
      <div className="flex flex-col gap-6">
        {layout.levels.map((level) => (
          <div key={level.level} className="flex flex-wrap gap-3">
            {level.cards.map((card) => {
              const latest = flowPool?.[card.node.id]?.slice(-1)[0] ?? null;
              const status = deriveStatus(flowBuildStatus?.[card.node.id]);
              return (
                <div
                  key={card.node.id}
                  className={
                    card.parallelSiblings.length > 0
                      ? "min-w-[240px] flex-1"
                      : "w-full"
                  }
                >
                  <PipelineCard
                    node={card.node}
                    groupedChildren={card.groupedChildren}
                    status={status}
                    latestResult={latest}
                    onSend={onSend}
                  />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
