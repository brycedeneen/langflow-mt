import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface RemoveMemberParams {
  orgId: string;
  userId: string;
}

export const useRemoveMember: useMutationFunctionType<
  undefined,
  RemoveMemberParams,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const removeMemberFn = async ({
    orgId,
    userId,
  }: RemoveMemberParams): Promise<void> => {
    await api.delete(
      `${getURL("ADMIN_ORGS")}/${orgId}/members/${userId}`,
    );
  };

  const mutation = mutate(["useRemoveMember"], removeMemberFn, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", (variables as unknown as RemoveMemberParams).orgId],
      });
      options?.onSuccess?.(data, variables, context, ...rest);
    },
  });

  return mutation;
};
