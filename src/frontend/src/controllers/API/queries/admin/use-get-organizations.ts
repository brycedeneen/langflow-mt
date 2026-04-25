import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgListResponse as OrgListResponseSchema } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetOrganizationsParams {
  q?: string;
  limit?: number;
  offset?: number;
}

export const useGetOrganizations: useQueryFunctionType<
  GetOrganizationsParams,
  z.infer<typeof OrgListResponseSchema>
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getOrganizationsFn = validatedQueryFn(
    "api.admin.list_organizations_api_v1_admin_organizations_get",
    OrgListResponseSchema,
    async () => {
      const baseUrl = getURL("ADMIN_ORGS");
      const searchParams = new URLSearchParams();
      if (params.q !== undefined) searchParams.set("q", params.q);
      if (params.limit !== undefined)
        searchParams.set("limit", String(params.limit));
      if (params.offset !== undefined)
        searchParams.set("offset", String(params.offset));
      const qs = searchParams.toString();
      const url = qs ? `${baseUrl}?${qs}` : baseUrl;
      return (await api.get<unknown>(url)).data;
    },
  );

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
