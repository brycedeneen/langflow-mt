import { validatedQueryFn } from "@/lib/validated-fetch";
import { MemberRow as MemberRowSchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface AddMemberParams {
  orgId: string;
  user_id: string;
  role?: string;
}

export const useAddMember: useMutationFunctionType<
  undefined,
  AddMemberParams,
  z.infer<typeof MemberRowSchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMemberFn = async ({
    orgId,
    user_id,
    role,
  }: AddMemberParams): Promise<z.infer<typeof MemberRowSchema>> => {
    const data = await validatedQueryFn(
      "api.admin.add_member_api_v1_admin_organizations__org_id__members_post",
      MemberRowSchema,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("ADMIN_ORGS")}/${orgId}/members`,
            { user_id, role },
          )
        ).data,
    )();
    return data;
  };

  const mutation = mutate(["useAddMember"], addMemberFn, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", (variables as unknown as AddMemberParams).orgId],
      });
      options?.onSuccess?.(data, variables, context, ...rest);
    },
  });

  return mutation;
};
