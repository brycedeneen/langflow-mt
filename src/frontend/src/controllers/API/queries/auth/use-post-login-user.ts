import type { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { TokenResponseSchema } from "@/schemas/app/internal/auth";
import type { LoginType, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLoginUser: useMutationFunctionType<undefined, LoginType> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function loginUserFn({ password, username }: LoginType): Promise<any> {
    const data = await validatedQueryFn(
      "api.auth.login",
      TokenResponseSchema,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("LOGIN")}`,
            new URLSearchParams({
              username: username,
              password: password,
            }).toString(),
            {
              headers: {
                "Content-Type": "application/x-www-form-urlencoded",
              },
            },
          )
        ).data,
    )();
    return data;
  }

  const mutation: UseMutationResult<LoginType, any, LoginType> = mutate(
    ["useLoginUser"],
    loginUserFn,
    {
      retry: false,
      ...options,
      onSuccess: () => {
        // Clear all cache to prevent data from previous user
        queryClient.clear();
      },
      onSettled: () => {
        queryClient.refetchQueries({ queryKey: ["useGetFolders"] });
        queryClient.refetchQueries({ queryKey: ["useGetTags"] });
      },
    },
  );

  return mutation;
};
