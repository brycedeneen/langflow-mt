import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowRead } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateFlow {
  id: string;
  name?: string;
  data?: ReactFlowJsonObject;
  description?: string;
  folder_id?: string | null | undefined;
  endpoint_name?: string | null | undefined;
  locked?: boolean | null | undefined;
  access_type?: "PUBLIC" | "PRIVATE" | "PROTECTED";
}

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchUpdateFlowFn = async ({
    id,
    ...payload
  }: IPatchUpdateFlow): Promise<any> => {
    const parsed = await validatedQueryFn(
      "api.flows.update_flow_api_v1_flows__flow_id__patch",
      FlowRead,
      async () => (await api.patch<unknown>(`${getURL("FLOWS")}/${id}`, payload)).data,
    )();
    return parsed;
  };

  const mutation: UseMutationResult<IPatchUpdateFlow, any, IPatchUpdateFlow> =
    mutate(["usePatchUpdateFlow"], PatchUpdateFlowFn, {
      onSettled: (res) => {
        if (res) {
          queryClient.refetchQueries({
            queryKey: ["useGetFolders", res.folder_id],
          });
        }
        queryClient.refetchQueries({
          queryKey: ["useGetFolder"],
        });
      },
      ...options,
    });

  return mutation;
};
