import { UseMutationOptions, useMutation } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { ValidateProviderResponseSchema } from "@/schemas/app/internal/models";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface ValidateProviderRequest {
  provider: string;
  variables: Record<string, string>;
}

export interface ValidateProviderResponse {
  valid: boolean;
  error: string | null;
}

export const useValidateProvider = (
  options?: Omit<
    UseMutationOptions<
      ValidateProviderResponse,
      Error,
      ValidateProviderRequest
    >,
    "mutationFn"
  >,
) => {
  return useMutation<ValidateProviderResponse, Error, ValidateProviderRequest>({
    mutationFn: async (request: ValidateProviderRequest) => {
      return validatedQueryFn(
        "api.models.validate_provider",
        ValidateProviderResponseSchema,
        async () =>
          (
            await api.post<unknown>(
              `${getURL("MODELS")}/validate-provider`,
              request,
            )
          ).data,
      )() as Promise<ValidateProviderResponse>;
    },
    retry: 0,
    ...options,
  });
};
