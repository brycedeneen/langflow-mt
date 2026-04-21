import type { UseMutationResult } from "@tanstack/react-query";
import type {
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type MappingConfigError = {
  path: (string | number)[];
  message: string;
};

export type ValidateMappingConfigResponse = {
  errors: MappingConfigError[];
};

export const usePostValidateMappingConfig: useMutationFunctionType<
  undefined,
  Record<string, unknown>,
  ValidateMappingConfigResponse,
  ResponseErrorDetailAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postValidateMappingConfigFn = async (
    config: Record<string, unknown>,
  ): Promise<ValidateMappingConfigResponse> => {
    try {
      const response = await api.post<ValidateMappingConfigResponse>(
        getURL("VALIDATE", { 1: "validate-mapping-config" }),
        config,
      );
      return response.data;
    } catch (err: any) {
      // 422 responses carry `{detail: {errors: [...]}}` or `{errors: [...]}`
      // depending on FastAPI version — normalize to the flat shape.
      const body = err?.response?.data;
      const errors = body?.errors ?? body?.detail?.errors;
      if (Array.isArray(errors)) return { errors };
      throw err;
    }
  };

  const mutation: UseMutationResult<
    ValidateMappingConfigResponse,
    ResponseErrorDetailAPI,
    Record<string, unknown>
  > = mutate(
    ["usePostValidateMappingConfig"],
    postValidateMappingConfigFn,
    options,
  );

  return mutation;
};
