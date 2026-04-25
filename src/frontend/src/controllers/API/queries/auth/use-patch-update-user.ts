import type { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { UserRead } from "@/schemas/api/_generated";
import type { changeUser, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateUserParams {
  user_id: string;
  user: changeUser;
}

export const useUpdateUser: useMutationFunctionType<
  undefined,
  UpdateUserParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function updateUser({ user_id, user }: UpdateUserParams): Promise<any> {
    const data = await validatedQueryFn(
      "api.users.patch_user_api_v1_users__user_id__patch",
      UserRead,
      async () =>
        (await api.patch<unknown>(`${getURL("USERS")}/${user_id}`, user)).data,
    )();
    return data;
  }

  const mutation: UseMutationResult<UpdateUserParams, any, UpdateUserParams> =
    mutate(["useUpdateUser"], updateUser, options);

  return mutation;
};
