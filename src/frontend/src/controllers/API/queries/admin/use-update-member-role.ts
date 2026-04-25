import { validatedQueryFn } from "@/lib/validated-fetch";
import { MemberRow as MemberRowSchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateMemberRoleParams {
  orgId: string;
  userId: string;
  role: string;
}

export const useUpdateMemberRole: useMutationFunctionType<
  undefined,
  UpdateMemberRoleParams,
  z.infer<typeof MemberRowSchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateRoleFn = async ({
    orgId,
    userId,
    role,
  }: UpdateMemberRoleParams): Promise<z.infer<typeof MemberRowSchema>> => {
    const data = await validatedQueryFn(
      "api.admin.patch_member_role_api_v1_admin_organizations__org_id__members__user_id__patch",
      MemberRowSchema,
      async () =>
        (
          await api.patch<unknown>(
            `${getURL("ADMIN_ORGS")}/${orgId}/members/${userId}`,
            { role },
          )
        ).data,
    )();
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
