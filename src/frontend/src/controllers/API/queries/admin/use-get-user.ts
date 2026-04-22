import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { UserDetail } from "./types";

interface GetUserParams {
  userId: string;
}

export const useGetUser: useQueryFunctionType<GetUserParams, UserDetail> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();

  const getUserFn = async (): Promise<UserDetail> => {
    const { data } = await api.get<UserDetail>(
      `${getURL("ADMIN_USERS")}/${params.userId}`,
    );
    return data;
  };

  const queryResult = query(
    ["admin", "users", params.userId],
    getUserFn,
    {
      ...options,
    },
  );

  return queryResult;
};
