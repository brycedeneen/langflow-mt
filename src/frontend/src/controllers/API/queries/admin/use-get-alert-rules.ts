import { validatedQueryFn } from "@/lib/validated-fetch";
import { RuleListResponse } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string };

export const useGetAlertRules: useQueryFunctionType<
  Params,
  z.infer<typeof RuleListResponse>
> = ({ orgId }, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.list_rules_api_v1_admin_orgs__org_id__alert_rules_get",
    RuleListResponse,
    async () =>
      (
        await api.get<unknown>(
          `${getURL("ADMIN_ALERT_RULES")}/${orgId}/alert-rules`,
        )
      ).data,
  );
  return query(["admin", "alert-rules", orgId], fn, { ...options });
};
