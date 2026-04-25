import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
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
    await validatedQueryFn(
      "api.admin.mark_read_api_v1_admin_notifications__notification_id__read_post",
      z.unknown(),
      async () =>
        (
          await api.post<unknown>(
            `${getURL("ADMIN_NOTIFICATIONS")}/${id}/read`,
          )
        ).data,
    )();
  };

  return mutate(["useMarkNotificationRead"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications"] });
      options?.onSuccess?.(...args);
    },
  });
};
