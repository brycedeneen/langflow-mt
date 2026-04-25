import { validatedQueryFn } from "@/lib/validated-fetch";
import { UserDetail as UserDetailSchema } from "@/schemas/api/_generated";
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
    const data = await validatedQueryFn(
      "api.admin.get_user_detail_api_v1_admin_users__user_id__get",
      UserDetailSchema,
      async () =>
        (await api.get<unknown>(`${getURL("ADMIN_USERS")}/${params.userId}`))
          .data,
    )();
    return data as unknown as UserDetail;
  };

  const queryResult = query(["admin", "users", params.userId], getUserFn, {
    ...options,
  });

  return queryResult;
};
