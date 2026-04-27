import type { UseMutationResult } from "@tanstack/react-query";
import type { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { UsersResponse } from "@/schemas/api/_generated";
import type { ApiError, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface getUsersQueryParams {
  skip: number;
  limit: number;
}

type UsersResponseShape = z.infer<typeof UsersResponse>;

export const useGetUsers: useMutationFunctionType<any, getUsersQueryParams> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function getUsers({
    skip,
    limit,
  }: getUsersQueryParams): Promise<UsersResponseShape> {
    return await validatedQueryFn(
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
  }

  const mutation: UseMutationResult<
    getUsersQueryParams,
    ApiError,
    getUsersQueryParams
  > = mutate(["useGetUsers"], getUsers, options);

  return mutation;
};
