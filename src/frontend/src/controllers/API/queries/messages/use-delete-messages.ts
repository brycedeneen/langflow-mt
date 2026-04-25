import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMessagesParams {
  ids: string[];
}

export const useDeleteMessages: useMutationFunctionType<
  undefined,
  DeleteMessagesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteMessage = async ({ ids }: DeleteMessagesParams): Promise<unknown> => {
    const result = await validatedQueryFn(
      "api.monitor.delete_messages_api_v1_monitor_messages_delete",
      z.unknown(),
      async () =>
        (
          await api.delete<unknown>(`${getURL("MESSAGES")}`, {
            data: ids,
          })
        ).data,
    )();
    return result;
  };

  const mutation: UseMutationResult<
    DeleteMessagesParams,
    any,
    DeleteMessagesParams
  > = mutate(["useDeleteMessages"], deleteMessage, {
    ...options,
    onSettled: (data, error, variables, context, ...rest) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });
      options?.onSettled?.(data, error, variables, context, ...rest);
    },
  });

  return mutation;
};
