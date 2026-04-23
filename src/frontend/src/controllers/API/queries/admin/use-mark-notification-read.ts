import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useMarkNotificationRead: useMutationFunctionType<
  undefined,
  { id: string },
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({ id }: { id: string }): Promise<void> => {
    await api.post(`${getURL("ADMIN_NOTIFICATIONS")}/${id}/read`);
  };

  return mutate(["useMarkNotificationRead"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications"] });
      options?.onSuccess?.(...args);
    },
  });
};
