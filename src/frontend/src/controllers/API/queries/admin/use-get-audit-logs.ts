import { validatedQueryFn } from "@/lib/validated-fetch";
import {
  AuditLogListResponse as AuditLogListResponseSchema,
  AuditLogRead,
} from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

// Re-export for downstream compatibility
export type AuditLogListItem = z.infer<typeof AuditLogRead>;
export type AuditLogListResponse = z.infer<typeof AuditLogListResponseSchema>;

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

export const useGetAuditLogs: useQueryFunctionType<
  AuditLogListParams,
  AuditLogListResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.list_audit_logs_api_v1_admin_audit_logs_get",
    AuditLogListResponseSchema,
    async () =>
      (await api.get<unknown>(getURL("ADMIN_AUDIT_LOGS"), { params })).data,
  );
  return query(["admin", "audit-logs", params], fn, { ...options });
};
