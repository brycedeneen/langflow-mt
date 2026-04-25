import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgSummary as OrgSummarySchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { OrgCreate } from "./types";

export const useCreateOrganization: useMutationFunctionType<
  undefined,
  OrgCreate,
  z.infer<typeof OrgSummarySchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createOrganizationFn = async (
    payload: OrgCreate,
  ): Promise<z.infer<typeof OrgSummarySchema>> => {
    const data = await validatedQueryFn(
      "api.admin.create_organization_api_v1_admin_organizations_post",
      OrgSummarySchema,
      async () =>
        (await api.post<unknown>(`${getURL("ADMIN_ORGS")}`, payload)).data,
    )();
    return data;
  };

  const mutation = mutate(["useCreateOrganization"], createOrganizationFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
