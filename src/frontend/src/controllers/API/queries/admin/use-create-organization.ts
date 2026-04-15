import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { OrgCreate, OrgSummary } from "./types";

export const useCreateOrganization: useMutationFunctionType<
  undefined,
  OrgCreate,
  OrgSummary
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createOrganizationFn = async (
    payload: OrgCreate,
  ): Promise<OrgSummary> => {
    const { data } = await api.post<OrgSummary>(
      `${getURL("ADMIN_ORGS")}`,
      payload,
    );
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
