import { validatedQueryFn } from "@/lib/validated-fetch";
import { AuditLogListResponse as AuditLogListResponseSchema } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AuditLogListResponse } from "../admin/use-get-audit-logs";

export type FlowAuditLogParams = {
  flowId: string;
  action?: string;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
};

export const useGetFlowAuditLogs: useQueryFunctionType<
  FlowAuditLogParams,
  AuditLogListResponse
> = ({ flowId, ...params }, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.flows.list_flow_audit_logs",
    AuditLogListResponseSchema,
    async () =>
      (
        await api.get<unknown>(`${getURL("FLOWS")}/${flowId}/audit-logs`, {
          params,
        })
      ).data,
  );
  return query(["flows", flowId, "audit-logs", params], fn, {
    enabled: !!flowId,
    ...options,
  });
};
