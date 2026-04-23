import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string };
type ThresholdRead = {
  id: string;
  org_id: string;
  metric: "runs" | "run_seconds" | "tokens";
  period: "daily" | "monthly";
  threshold_value: number;
  is_active: boolean;
  last_fired_at: string | null;
  cooldown_seconds: number;
};
type Response = { items: ThresholdRead[] };

export const useGetUsageThresholds: useQueryFunctionType<Params, Response> = (
  { orgId },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ADMIN_USAGE_THRESHOLDS")}/${orgId}/usage/thresholds`,
    );
    return data;
  };
  return query(["admin", "usage-thresholds", orgId], fn, { ...options });
};
