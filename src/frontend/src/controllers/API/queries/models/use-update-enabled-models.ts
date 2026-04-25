import { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import {
  UpdateEnabledModelsResponseSchema,
} from "@/schemas/app/internal/models";
import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelStatusUpdate {
  provider: string;
  model_id: string;
  enabled: boolean;
}

export interface UpdateEnabledModelsResponse {
  disabled_models: string[];
}

export const useUpdateEnabledModels: useMutationFunctionType<
  undefined,
  { updates: ModelStatusUpdate[] },
  UpdateEnabledModelsResponse,
  Error
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const updateEnabledModelsFn = async (data: {
    updates: ModelStatusUpdate[];
  }): Promise<UpdateEnabledModelsResponse> => {
    return validatedQueryFn(
      "api.models.update_enabled_models",
      UpdateEnabledModelsResponseSchema,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("MODELS")}/enabled_models`,
            data.updates,
          )
        ).data,
    )() as Promise<UpdateEnabledModelsResponse>;
  };

  const mutation: UseMutationResult<
    UpdateEnabledModelsResponse,
    Error,
    { updates: ModelStatusUpdate[] }
  > = mutate(["useUpdateEnabledModels"], updateEnabledModelsFn, options);

  return mutation;
};
