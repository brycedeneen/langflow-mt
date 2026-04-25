import { validatedQueryFn } from "@/lib/validated-fetch";
import { AuditLogRead } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetAuditLog: useQueryFunctionType<
  { id: string },
  z.infer<typeof AuditLogRead>
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.get_audit_log_api_v1_admin_audit_logs__audit_id__get",
    AuditLogRead,
    async () =>
      (await api.get<unknown>(`${getURL("ADMIN_AUDIT_LOG")}${params.id}`)).data,
  );
  return query(["admin", "audit-log", params.id], fn, { ...options });
};
