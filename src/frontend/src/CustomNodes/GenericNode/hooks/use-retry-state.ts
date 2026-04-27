import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";

export type RetryState =
  | { status: "retrying"; retry_number: number; max_retries: number }
  | { status: "retry_exhausted" }
  | null;

/**
 * Reads per-vertex retry state from flowBuildStatus.
 * Returns structured retry info or null when the node is not in a retry state.
 */
export function useRetryState(nodeId: string): RetryState {
  return useFlowStore((state) => {
    const entry = state.flowBuildStatus[nodeId];
    if (!entry) return null;

    if (entry.status === BuildStatus.RETRYING) {
      return {
        status: "retrying",
        retry_number: entry.retryMeta?.retry_number ?? 1,
        max_retries: entry.retryMeta?.max_retries ?? 1,
      };
    }
    if (entry.status === BuildStatus.RETRY_EXHAUSTED) {
      return { status: "retry_exhausted" };
    }
    return null;
  });
}
