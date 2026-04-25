import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgDetail as OrgDetailSchema } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { OrgDetail } from "./types";

interface GetOrganizationParams {
  orgId: string;
}

export const useGetOrganization: useQueryFunctionType<
  GetOrganizationParams,
  OrgDetail
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getOrganizationFn = async (): Promise<OrgDetail> => {
    const data = await validatedQueryFn(
      "api.admin.get_organization_api_v1_admin_organizations__org_id__get",
      OrgDetailSchema,
      async () =>
        (await api.get<unknown>(`${getURL("ADMIN_ORGS")}/${params.orgId}`))
          .data,
    )();
    return data as unknown as OrgDetail;
  };

  const queryResult = query(
    ["admin", "organizations", params.orgId],
    getOrganizationFn,
    {
      ...options,
    },
  );

  return queryResult;
};
