import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useMarkAllNotificationsRead: useMutationFunctionType<
  undefined,
  void,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (): Promise<void> => {
    await api.post(`${getURL("ADMIN_NOTIFICATIONS")}/mark-all-read`);
  };

  return mutate(["useMarkAllNotificationsRead"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications"] });
      options?.onSuccess?.(...args);
    },
  });
};
