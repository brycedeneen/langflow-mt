import { validatedQueryFn } from "@/lib/validated-fetch";
import { NotificationListResponse } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { unread?: boolean; limit?: number; offset?: number };

export const useGetAdminNotifications: useQueryFunctionType<
  Params,
  z.infer<typeof NotificationListResponse>
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.list_notifications_api_v1_admin_notifications_get",
    NotificationListResponse,
    async () =>
      (await api.get<unknown>(getURL("ADMIN_NOTIFICATIONS"), { params })).data,
  );
  return query(["admin", "notifications", params], fn, { ...options });
};
