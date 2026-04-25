import { validatedQueryFn } from "@/lib/validated-fetch";
import { ApiKeyStoreResponseSchema } from "@/schemas/app/internal/api_key";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddApiKey {
  key: string;
}

// add types for error handling and success
export const usePostAddApiKey: useMutationFunctionType<
  undefined,
  IPostAddApiKey
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const postAddApiKeyFn = async (payload: IPostAddApiKey): Promise<unknown> => {
    return validatedQueryFn(
      "api.api_key.store",
      ApiKeyStoreResponseSchema,
      async () =>
        (
          await api.post<unknown>(`${getURL("API_KEY")}/store`, {
            api_key: payload.key,
          })
        ).data,
    )();
  };

  const mutation = mutate(["usePostAddApiKey"], postAddApiKeyFn, options);

  return mutation;
};
