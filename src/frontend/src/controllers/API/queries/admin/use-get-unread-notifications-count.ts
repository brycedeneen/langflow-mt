import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const UnreadCountSchema = z.object({ unread: z.number().int() }).passthrough();
type UnreadCountResponse = z.infer<typeof UnreadCountSchema>;

export const useGetUnreadNotificationsCount: useQueryFunctionType<
  Record<string, never>,
  UnreadCountResponse
> = (_params, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.unread_count_api_v1_admin_notifications_unread_count_get",
    UnreadCountSchema,
    async () =>
      (
        await api.get<unknown>(
          `${getURL("ADMIN_NOTIFICATIONS")}/unread-count`,
        )
      ).data,
  );
  return query(["admin", "notifications", "unread-count"], fn, { ...options });
};
