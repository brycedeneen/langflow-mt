import { BuildStatus, EventDeliveryType } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { buildFlowVerticesWithFallback } from "@/utils/buildUtils";

async function runBuild(stopNodeId: string | null): Promise<void> {
  const flowId = useFlowsManagerStore.getState().currentFlow?.id;
  if (!flowId) {
    return;
  }
  await buildFlowVerticesWithFallback({
    flowId,
    stopNodeId,
    eventDelivery: EventDeliveryType.STREAMING,
    onBuildStart: (elementList) => {
      const ids = elementList.map((e) => e.id);
      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.BUILDING);
    },
    onBuildUpdate: (vertexBuildData, status, runId) => {
      useFlowStore.getState().addDataToFlowPool(
        { ...vertexBuildData, run_id: runId },
        vertexBuildData.id,
      );
      useFlowStore.getState().updateBuildStatus([vertexBuildData.id], status);
    },
    onBuildComplete: () => {},
    onBuildError: (title, list, elementList) => {
      const ids =
        (elementList?.map((e) => e.id).filter(Boolean) as string[]) ?? [];
      if (ids.length > 0) {
        useFlowStore.getState().updateBuildStatus(ids, BuildStatus.ERROR);
      }
      useAlertStore
        .getState()
        .addNotificationToHistory({ title, type: "error", list });
    },
  });
}

/**
 * Build every vertex up to and including `nodeId`.
 * Wires minimal callbacks that update flowBuildStatus + flowPool without
 * resetting prior per-node state (unlike flowStore.buildFlow).
 */
export async function runTestForComponent(nodeId: string): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(nodeId);
  await runBuild(nodeId);
}

/**
 * Build the whole flow.
 * Uses the same minimal-callback pattern as runTestForComponent to avoid
 * resetting prior per-node state (unlike flowStore.buildFlow).
 */
export async function runTestForAll(): Promise<void> {
  useAssistantStore.getState().setSelectedTestComponent(null);
  await runBuild(null);
}
