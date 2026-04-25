import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { refreshAllModelInputs } from "@/hooks/use-refresh-model-inputs";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteGlobalVariablesParams {
  id: string | undefined;
}

export const useDeleteGlobalVariables: useMutationFunctionType<
  undefined,
  DeleteGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteGlobalVariables = async ({
    id,
  }: DeleteGlobalVariablesParams): Promise<unknown> => {
    return validatedQueryFn(
      "api.variables.delete",
      z.unknown(),
      async () =>
        (await api.delete<unknown>(`${getURL("VARIABLES")}/${id}`)).data,
    )();
  };

  const mutation: UseMutationResult<
    DeleteGlobalVariablesParams,
    any,
    DeleteGlobalVariablesParams
  > = mutate(["useDeleteGlobalVariables"], deleteGlobalVariables, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] });
    },
    ...options,
  });

  return mutation;
};
