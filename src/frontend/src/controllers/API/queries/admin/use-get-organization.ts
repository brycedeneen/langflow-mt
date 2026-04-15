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
    const { data } = await api.get<OrgDetail>(
      `${getURL("ADMIN_ORGS")}/${params.orgId}`,
    );
    return data;
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
