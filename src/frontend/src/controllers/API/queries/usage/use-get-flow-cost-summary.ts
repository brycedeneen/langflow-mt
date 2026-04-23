import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { flowId: string };
type Response = {
  flow_id: string;
  window_days: number;
  total_cost_cents: number;
  total_runs: number;
  sparkline: Array<{ date: string; cost_cents: number }>;
};

export const useGetFlowCostSummary: useQueryFunctionType<Params, Response> = (
  { flowId },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("FLOW_COST_SUMMARY")}/${flowId}/cost-summary`,
    );
    return data;
  };
  return query(["flow-cost-summary", flowId], fn, { ...options });
};
