import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
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
    await validatedQueryFn(
      "api.admin.mark_all_read_api_v1_admin_notifications_mark_all_read_post",
      z.unknown(),
      async () =>
        (
          await api.post<unknown>(
            `${getURL("ADMIN_NOTIFICATIONS")}/mark-all-read`,
          )
        ).data,
    )();
  };

  return mutate(["useMarkAllNotificationsRead"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications"] });
      options?.onSuccess?.(...args);
    },
  });
};
