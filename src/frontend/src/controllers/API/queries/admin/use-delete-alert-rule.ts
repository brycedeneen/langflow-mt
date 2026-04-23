import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteAlertRule: useMutationFunctionType<
  undefined,
  { id: string },
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ id }: { id: string }): Promise<void> => {
    await api.delete(`${getURL("ADMIN_ALERT_RULE")}/${id}`);
  };
  return mutate(["useDeleteAlertRule"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "alert-rules"] });
      options?.onSuccess?.(...args);
    },
  });
};
