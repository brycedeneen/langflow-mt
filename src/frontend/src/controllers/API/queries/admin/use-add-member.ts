import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemberRow } from "./types";

interface AddMemberParams {
  orgId: string;
  user_id: string;
  role?: string;
}

export const useAddMember: useMutationFunctionType<
  undefined,
  AddMemberParams,
  MemberRow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMemberFn = async ({
    orgId,
    user_id,
    role,
  }: AddMemberParams): Promise<MemberRow> => {
    const { data } = await api.post<MemberRow>(
      `${getURL("ADMIN_ORGS")}/${orgId}/members`,
      { user_id, role },
    );
    return data;
  };

  const mutation = mutate(["useAddMember"], addMemberFn, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", (variables as unknown as AddMemberParams).orgId],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
