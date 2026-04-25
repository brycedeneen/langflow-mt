import type { UseQueryResult } from "@tanstack/react-query";
import { z } from "zod";
import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { VariableReadSchema } from "@/schemas/app/internal/variables";
import type { useQueryFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  );
  const setUnavailableFields = useGlobalVariablesStore(
    (state) => state.setUnavailableFields,
  );
  const setGlobalVariablesEntities = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntities,
  );

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return [];
    const data = await validatedQueryFn(
      "api.variables.list",
      z.array(VariableReadSchema),
      async () => (await api.get<unknown>(`${getURL("VARIABLES")}/`)).data,
    )();
    const vars = data as unknown as GlobalVariable[];
    setGlobalVariablesEntries(vars.map((entry) => entry.name ?? ""));
    setUnavailableFields(getUnavailableFields(vars));
    setGlobalVariablesEntities(vars);
    return vars;
  };

  const queryResult: UseQueryResult<GlobalVariable[], Error> = query(
    ["useGetGlobalVariables"],
    getGlobalVariablesFn,
    {
      refetchOnWindowFocus: false,
      enabled: isAuthenticated && (options?.enabled ?? true),
      ...options,
    },
  );

  return queryResult;
};
