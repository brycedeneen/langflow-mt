import type { UseMutationResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { UsersResponse } from "@/schemas/api/_generated";
import type { Users, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface getUsersQueryParams {
  skip: number;
  limit: number;
}

export const useGetUsers: useMutationFunctionType<any, getUsersQueryParams> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function getUsers({
    skip,
    limit,
  }: getUsersQueryParams): Promise<Array<Users>> {
    const res = await validatedQueryFn(
      "api.users.read_all_users_api_v1_users__get",
      UsersResponse,
      async () => {
        const r = await api.get<unknown>(
          `${getURL("USERS")}/?skip=${skip}&limit=${limit}`,
        );
        if ((r as any).status === 200) return r.data;
        return { total_count: 0, users: [] };
      },
    )();
    return res.users as unknown as Users[];
  }

  const mutation: UseMutationResult<
    getUsersQueryParams,
    any,
    getUsersQueryParams
  > = mutate(["useGetUsers"], getUsers, options);

  return mutation;
};
