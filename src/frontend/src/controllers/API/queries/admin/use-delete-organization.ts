import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgDeleteResult as OrgDeleteResultSchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteOrganizationParams {
  orgId: string;
  confirm_name: string;
}

export const useDeleteOrganization: useMutationFunctionType<
  undefined,
  DeleteOrganizationParams,
  z.infer<typeof OrgDeleteResultSchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteOrganizationFn = async ({
    orgId,
    confirm_name,
  }: DeleteOrganizationParams): Promise<z.infer<typeof OrgDeleteResultSchema>> => {
    const data = await validatedQueryFn(
      "api.admin.delete_organization_api_v1_admin_organizations__org_id__delete",
      OrgDeleteResultSchema,
      async () =>
        (
          await api.delete<unknown>(`${getURL("ADMIN_ORGS")}/${orgId}`, {
            data: { confirm_name },
          })
        ).data,
    )();
    return data;
  };

  const mutation = mutate(["useDeleteOrganization"], deleteOrganizationFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
