import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemberRow } from "./types";

interface UpdateMemberRoleParams {
  orgId: string;
  userId: string;
  role: string;
}

export const useUpdateMemberRole: useMutationFunctionType<
  undefined,
  UpdateMemberRoleParams,
  MemberRow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateRoleFn = async ({
    orgId,
    userId,
    role,
  }: UpdateMemberRoleParams): Promise<MemberRow> => {
    const { data } = await api.patch<MemberRow>(
      `${getURL("ADMIN_ORGS")}/${orgId}/members/${userId}`,
      { role },
    );
    return data;
  };

  const mutation = mutate(["useUpdateMemberRole"], updateRoleFn, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      const { orgId, userId } = variables as unknown as UpdateMemberRoleParams;
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", orgId],
      });
      queryClient.invalidateQueries({
        queryKey: ["admin", "users", userId],
      });
      options?.onSuccess?.(data, variables, context, ...rest);
    },
  });

  return mutation;
};
