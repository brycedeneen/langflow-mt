import type { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { UserRead } from "@/schemas/api/_generated";
import type { ApiError, Users, useMutationFunctionType } from "@/types/api";
import type { UserInputType } from "@/types/components";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useAddUser: useMutationFunctionType<undefined, UserInputType> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  const addUserFunction = async (user: UserInputType): Promise<Users> => {
    const data = await validatedQueryFn(
      "api.users.add_user_api_v1_users__post",
      UserRead,
      async () => (await api.post<unknown>(`${getURL("USERS")}/`, user)).data,
    )();
    return data as unknown as Users;
  };

  const mutation: UseMutationResult<Users, ApiError, UserInputType> = mutate(
    ["useAddUser"],
    addUserFunction,
    options,
  );

  return mutation;
};
