import { LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { TokenResponseSchema } from "@/schemas/app/internal/auth";
import type { useMutationFunctionType } from "@/types/api";
import { cookieManager } from "@/utils/cookie-manager";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IRefreshAccessToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const useRefreshAccessToken: useMutationFunctionType<
  undefined,
  undefined | void,
  IRefreshAccessToken
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function refreshAccess(): Promise<IRefreshAccessToken> {
    const data = await validatedQueryFn(
      "api.auth.refresh",
      TokenResponseSchema,
      async () => (await api.post<unknown>(`${getURL("REFRESH")}`)).data,
    )();
    cookieManager.set(LANGFLOW_REFRESH_TOKEN, data.refresh_token ?? "");
    return data as IRefreshAccessToken;
  }

  const mutation = mutate(["useRefreshAccessToken"], refreshAccess, {
    ...options,
    retry: 2,
  });

  return mutation;
};
