import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string };
type RuleRead = {
  id: string;
  org_id: string;
  flow_id: string | null;
  rule_type: "consecutive_failures" | "error_rate" | "sla_duration";
  config: Record<string, unknown>;
  is_active: boolean;
  last_fired_at: string | null;
  cooldown_seconds: number;
};
type Response = { items: RuleRead[] };

export const useGetAlertRules: useQueryFunctionType<Params, Response> = (
  { orgId },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ADMIN_ALERT_RULES")}/${orgId}/alert-rules`,
    );
    return data;
  };
  return query(["admin", "alert-rules", orgId], fn, { ...options });
};
