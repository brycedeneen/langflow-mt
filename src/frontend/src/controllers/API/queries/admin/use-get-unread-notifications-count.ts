import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Response = { unread: number };

export const useGetUnreadNotificationsCount: useQueryFunctionType<
  Record<string, never>,
  Response
> = (_params, options) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ADMIN_NOTIFICATIONS")}/unread-count`,
    );
    return data;
  };
  return query(["admin", "notifications", "unread-count"], fn, { ...options });
};
