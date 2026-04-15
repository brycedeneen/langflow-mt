import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { OrgListResponse } from "./types";

interface GetOrganizationsParams {
  q?: string;
  limit?: number;
  offset?: number;
}

export const useGetOrganizations: useQueryFunctionType<
  GetOrganizationsParams,
  OrgListResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getOrganizationsFn = async (): Promise<OrgListResponse> => {
    const baseUrl = getURL("ADMIN_ORGS");
    const searchParams = new URLSearchParams();
    if (params.q !== undefined) searchParams.set("q", params.q);
    if (params.limit !== undefined)
      searchParams.set("limit", String(params.limit));
    if (params.offset !== undefined)
      searchParams.set("offset", String(params.offset));
    const qs = searchParams.toString();
    const url = qs ? `${baseUrl}?${qs}` : baseUrl;

    const { data } = await api.get<OrgListResponse>(url);
    return data;
  };

  const queryResult = query(
    [
      "admin",
      "organizations",
      { q: params.q, limit: params.limit, offset: params.offset },
    ],
    getOrganizationsFn,
    {
      ...options,
    },
  );

  return queryResult;
};
