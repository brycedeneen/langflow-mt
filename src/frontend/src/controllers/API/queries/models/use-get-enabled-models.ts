import { validatedQueryFn } from "@/lib/validated-fetch";
import { EnabledModelsResponseSchema } from "@/schemas/app/internal/models";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface EnabledModelsResponse {
  enabled_models: Record<string, Record<string, boolean>>;
}

export const useGetEnabledModels: useQueryFunctionType<
  undefined,
  EnabledModelsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getEnabledModelsFn = validatedQueryFn(
    "api.models.get_enabled_models",
    EnabledModelsResponseSchema,
    async () =>
      (await api.get<unknown>(`${getURL("MODELS")}/enabled_models`)).data,
  );

  const queryResult = query(
    ["useGetEnabledModels"],
    getEnabledModelsFn as () => Promise<EnabledModelsResponse>,
    options,
  );

  return queryResult;
};
