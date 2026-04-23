import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { unread?: boolean; limit?: number; offset?: number };
type NotificationRead = {
  id: string;
  org_id: string | null;
  category: "usage_threshold" | "alert_rule" | "system";
  severity: "info" | "warning" | "critical";
  title: string;
  body_md: string;
  metadata: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
};
type Response = { items: NotificationRead[]; total: number };

export const useGetAdminNotifications: useQueryFunctionType<Params, Response> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(getURL("ADMIN_NOTIFICATIONS"), {
      params,
    });
    return data;
  };
  return query(["admin", "notifications", params], fn, { ...options });
};
