import type { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { VariableReadSchema } from "@/schemas/app/internal/variables";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchGlobalVariablesParams {
  name?: string;
  value?: string;
  id: string;
  default_fields?: string[];
  category?: string;
}

export const usePatchGlobalVariables: useMutationFunctionType<
  undefined,
  PatchGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchGlobalVariables(
    GlobalVariable: PatchGlobalVariablesParams,
  ): Promise<unknown> {
    return validatedQueryFn(
      "api.variables.update",
      VariableReadSchema,
      async () =>
        (
          await api.patch<unknown>(
            `${getURL("VARIABLES")}/${GlobalVariable.id}`,
            GlobalVariable,
          )
        ).data,
    )();
  }

  const mutation: UseMutationResult<
    PatchGlobalVariablesParams,
    any,
    PatchGlobalVariablesParams
  > = mutate(["usePatchGlobalVariables"], patchGlobalVariables, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] });
    },
    ...options,
    retry: false,
  });

  return mutation;
};
