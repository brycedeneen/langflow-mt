import type { UseMutationResult } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { UserRead } from "@/schemas/api/_generated";
import type { Users, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetUserData: useMutationFunctionType<undefined, any> = (
  options?,
) => {
  const setUserData = useAuthStore((state) => state.setUserData);
  const { mutate } = UseRequestProcessor();

  const getUserData = async () => {
    const data = await validatedQueryFn(
      "api.users.read_current_user_api_v1_users_whoami_get",
      UserRead,
      async () => (await api.get<unknown>(`${getURL("USERS")}/whoami`)).data,
    )();
    setUserData(data as unknown as Users);
    return data;
  };

  const mutation: UseMutationResult = mutate(
    ["useGetUserData"],
    getUserData,
    options,
  );

  return mutation;
};
