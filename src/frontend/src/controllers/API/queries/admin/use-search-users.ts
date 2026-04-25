import { validatedQueryFn } from "@/lib/validated-fetch";
import { UserSearchResponse as UserSearchResponseSchema } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface SearchUsersParams {
  q?: string;
  limit?: number;
}

export const useSearchUsers: useQueryFunctionType<
  SearchUsersParams,
  z.infer<typeof UserSearchResponseSchema>
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const searchUsersFn = validatedQueryFn(
    "api.admin.search_users_api_v1_admin_users_get",
    UserSearchResponseSchema,
    async () => {
      const searchParams = new URLSearchParams();
      if (params.q !== undefined) searchParams.set("q", params.q);
      if (params.limit !== undefined)
        searchParams.set("limit", String(params.limit));
      const qs = searchParams.toString();
      const baseUrl = getURL("ADMIN_USERS");
      const url = qs ? `${baseUrl}?${qs}` : baseUrl;
      return (await api.get<unknown>(url)).data;
    },
  );

  const queryResult = query(
    ["admin", "users", { q: params.q, limit: params.limit }],
    searchUsersFn,
    {
      ...options,
    },
  );

  return queryResult;
};
