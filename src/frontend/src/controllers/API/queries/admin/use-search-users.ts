import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { UserSearchResponse } from "./types";

interface SearchUsersParams {
  q?: string;
  limit?: number;
}

export const useSearchUsers: useQueryFunctionType<
  SearchUsersParams,
  UserSearchResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const searchUsersFn = async (): Promise<UserSearchResponse> => {
    const searchParams = new URLSearchParams();
    if (params.q !== undefined) searchParams.set("q", params.q);
    if (params.limit !== undefined)
      searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    const baseUrl = getURL("ADMIN_USERS");
    const url = qs ? `${baseUrl}?${qs}` : baseUrl;

    const { data } = await api.get<UserSearchResponse>(url);
    return data;
  };

  const queryResult = query(
    ["admin", "users", { q: params.q, limit: params.limit }],
    searchUsersFn,
    {
      ...options,
    },
  );

  return queryResult;
};
