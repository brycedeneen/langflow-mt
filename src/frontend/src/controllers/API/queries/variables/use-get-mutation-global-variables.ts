import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { VariableReadSchema } from "@/schemas/app/internal/variables";
import type { useMutationFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariablesMutation: useMutationFunctionType<
  undefined
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  );
  const setUnavailableFields = useGlobalVariablesStore(
    (state) => state.setUnavailableFields,
  );

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    const data = await validatedQueryFn(
      "api.variables.list",
      z.array(VariableReadSchema),
      async () => (await api.get<unknown>(`${getURL("VARIABLES")}/`)).data,
    )();
    const vars = data as unknown as GlobalVariable[];
    setGlobalVariablesEntries(vars.map((entry) => entry.name ?? ""));
    setUnavailableFields(getUnavailableFields(vars));
    return vars;
  };

  const mutation: UseMutationResult<undefined, Error, GlobalVariable[]> =
    mutate(["useGetGlobalVariables"], getGlobalVariablesFn, options);

  return mutation;
};
