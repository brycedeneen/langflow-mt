import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type AuditLogListItem = {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  actor_email: string;
  actor_is_super: boolean;
  org_id: string | null;
  target_type: string;
  target_id: string;
  action: string;
  diff: Record<string, unknown>;
  diff_hash: string;
  request_metadata: Record<string, unknown>;
};

export type AuditLogListResponse = {
  items: AuditLogListItem[];
  total: number;
  page: number;
  size: number;
};

export type AuditLogListParams = {
  org_id?: string;
  actor_user_id?: string;
  target_type?: string;
  target_id?: string;
  action?: string;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
};

export const useGetAuditLogs: useQueryFunctionType<AuditLogListParams, AuditLogListResponse> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<AuditLogListResponse> => {
    const { data } = await api.get<AuditLogListResponse>(getURL("ADMIN_AUDIT_LOGS"), {
      params,
    });
    return data;
  };
  return query(["admin", "audit-logs", params], fn, { ...options });
};
