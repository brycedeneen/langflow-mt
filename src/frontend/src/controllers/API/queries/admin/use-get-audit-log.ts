import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AuditLogListItem } from "./use-get-audit-logs";

export const useGetAuditLog: useQueryFunctionType<{ id: string }, AuditLogListItem> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<AuditLogListItem> => {
    const { data } = await api.get<AuditLogListItem>(`${getURL("ADMIN_AUDIT_LOG")}${params.id}`);
    return data;
  };
  return query(["admin", "audit-log", params.id], fn, { ...options });
};
