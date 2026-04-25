import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowRead } from "@/schemas/api/_generated";
import { useFolderStore } from "@/stores/foldersStore";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddFlow {
  name: string;
  data: ReactFlowJsonObject;
  description: string;
  is_component: boolean;
  folder_id: string;
  endpoint_name: string | undefined;
  icon: string | undefined;
  gradient: string | undefined;
  tags: string[] | undefined;
  locked?: boolean | null;
  mcp_enabled: boolean | undefined;
  built_with_assist?: boolean;
  based_on_template_id?: string | null;
}

export const usePostAddFlow: useMutationFunctionType<
  undefined,
  IPostAddFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const postAddFlowFn = async (payload: IPostAddFlow): Promise<unknown> => {
    const parsed = await validatedQueryFn(
      "api.flows.create_flow_api_v1_flows__post",
      FlowRead,
      async () =>
        (
          await api.post<unknown>(`${getURL("FLOWS")}/`, {
            name: payload.name,
            data: payload.data,
            description: payload.description,
            is_component: payload.is_component,
            folder_id: payload.folder_id || null,
            icon: payload.icon || null,
            gradient: payload.gradient || null,
            endpoint_name: payload.endpoint_name || null,
            tags: payload.tags || null,
            locked: payload.locked ?? null,
            mcp_enabled: payload.mcp_enabled || null,
            built_with_assist: payload.built_with_assist ?? false,
            based_on_template_id: payload.based_on_template_id ?? null,
          })
        ).data,
    )();
    return parsed;
  };

  const mutation: UseMutationResult<IPostAddFlow, ApiError, IPostAddFlow> = mutate(
    ["usePostAddFlow"],
    postAddFlowFn,
    {
      ...options,
      onSettled: (response) => {
        if (response) {
          queryClient.refetchQueries({
            queryKey: [
              "useGetRefreshFlowsQuery",
              { get_all: true, header_flows: true },
            ],
          });

          queryClient.refetchQueries({
            queryKey: [
              "useGetFolder",
              (response as { folder_id?: string }).folder_id ?? myCollectionId,
            ],
          });
        }
      },
    },
  );

  return mutation;
};
