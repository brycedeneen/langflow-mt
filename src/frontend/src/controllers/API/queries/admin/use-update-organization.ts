import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgSummary as OrgSummarySchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateOrganizationParams {
  orgId: string;
  name: string;
}

export const useUpdateOrganization: useMutationFunctionType<
  undefined,
  UpdateOrganizationParams,
  z.infer<typeof OrgSummarySchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateOrganizationFn = async ({
    orgId,
    name,
  }: UpdateOrganizationParams): Promise<z.infer<typeof OrgSummarySchema>> => {
    const data = await validatedQueryFn(
      "api.admin.update_organization_api_v1_admin_organizations__org_id__patch",
      OrgSummarySchema,
      async () =>
        (
          await api.patch<unknown>(`${getURL("ADMIN_ORGS")}/${orgId}`, {
            name,
          })
        ).data,
    )();
    return data;
  };

  const mutation = mutate(["useUpdateOrganization"], updateOrganizationFn, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", variables.orgId],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
