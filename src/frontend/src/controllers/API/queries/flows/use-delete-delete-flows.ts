import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFlows {
  flow_ids: string[];
}

export const useDeleteDeleteFlows: useMutationFunctionType<
  undefined,
  IDeleteFlows
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFlowsFn = async (payload: IDeleteFlows): Promise<unknown> => {
    const parsed = await validatedQueryFn(
      "api.flows.delete_multiple_flows_api_v1_flows__delete",
      z.unknown(),
      async () =>
        (
          await api.delete<unknown>(`${getURL("FLOWS")}/`, {
            data: payload.flow_ids,
          })
        ).data,
    )();
    return parsed;
  };

  const mutation: UseMutationResult<IDeleteFlows, ApiError, IDeleteFlows> = mutate(
    ["useLoginUser"],
    deleteFlowsFn,
    {
      ...options,
      onSettled: () => {
        queryClient.refetchQueries({ queryKey: ["useGetFolder"] });
      },
    },
  );

  return mutation;
};
