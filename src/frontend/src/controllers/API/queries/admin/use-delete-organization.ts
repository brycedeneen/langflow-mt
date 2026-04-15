import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { OrgDeleteResult } from "./types";

interface DeleteOrganizationParams {
  orgId: string;
  confirm_name: string;
}

export const useDeleteOrganization: useMutationFunctionType<
  undefined,
  DeleteOrganizationParams,
  OrgDeleteResult
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteOrganizationFn = async ({
    orgId,
    confirm_name,
  }: DeleteOrganizationParams): Promise<OrgDeleteResult> => {
    const { data } = await api.delete<OrgDeleteResult>(
      `${getURL("ADMIN_ORGS")}/${orgId}`,
      { data: { confirm_name } },
    );
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
