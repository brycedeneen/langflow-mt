import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteUserParams {
  user_id: string;
}

export const useDeleteUsers: useMutationFunctionType<
  undefined,
  DeleteUserParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const deleteMessage = async ({ user_id }: DeleteUserParams): Promise<any> => {
    const data = await validatedQueryFn(
      "api.users.delete_user_api_v1_users__user_id__delete",
      z.unknown(),
      async () =>
        (await api.delete<unknown>(`${getURL("USERS")}/${user_id}`)).data,
    )();
    return data;
  };

  const mutation: UseMutationResult<DeleteUserParams, any, DeleteUserParams> =
    mutate(["useDeleteUsers"], deleteMessage, options);

  return mutation;
};
