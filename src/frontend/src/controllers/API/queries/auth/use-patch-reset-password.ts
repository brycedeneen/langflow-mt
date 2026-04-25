import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type {
  ApiError,
  resetPasswordType,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface resetPasswordParams {
  user_id: string;
  password: resetPasswordType;
}

export const useResetPassword: useMutationFunctionType<
  undefined,
  resetPasswordParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function resetPassword({
    user_id,
    password,
  }: resetPasswordParams): Promise<unknown> {
    const data = await validatedQueryFn(
      "api.users.reset_password_api_v1_users__user_id__reset_password_patch",
      z.unknown(),
      async () =>
        (
          await api.patch<unknown>(
            `${getURL("USERS")}/${user_id}/reset-password`,
            password,
          )
        ).data,
    )();
    return data;
  }

  const mutation: UseMutationResult<
    resetPasswordParams,
    ApiError,
    resetPasswordParams
  > = mutate(["useResetPassword"], resetPassword, options);

  return mutation;
};
