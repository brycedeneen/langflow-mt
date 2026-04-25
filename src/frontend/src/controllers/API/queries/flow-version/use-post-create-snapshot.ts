import type { UseMutationResult } from "@tanstack/react-query";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import type { FlowVersionCreate, FlowVersionEntry } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ICreateSnapshot {
  flowId: string;
  description?: string | null;
}

export const usePostCreateSnapshot: useMutationFunctionType<
  undefined,
  ICreateSnapshot
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createSnapshotFn = async (
    payload: ICreateSnapshot,
  ): Promise<FlowVersionEntry> => {
    const body: FlowVersionCreate = { description: payload.description };
    const response = await api.post<FlowVersionEntry>(
      `${getURL("FLOWS")}/${payload.flowId}/versions/`,
      body,
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowVersionEntry, ApiError, ICreateSnapshot> =
    mutate(["usePostCreateSnapshot"], createSnapshotFn, {
      ...options,
      onSettled: (_, __, variables) => {
        const vars = variables as ICreateSnapshot | undefined;
        queryClient.refetchQueries({
          queryKey: ["useGetFlowVersions", { flowId: vars?.flowId }],
        });
      },
    });

  return mutation;
};
