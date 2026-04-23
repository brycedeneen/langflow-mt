import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = {
  orgId: string;
  metric?: "runs" | "run_seconds" | "tokens" | "cost_cents";
  window?: "1d" | "7d" | "30d";
};
type Response = {
  metric: string;
  series: Array<{ date: string; value: number }>;
};

export const useGetOrgUsageCharts: useQueryFunctionType<Params, Response> = (
  { orgId, metric = "runs", window = "30d" },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ORG_USAGE_CHARTS")}/${orgId}/usage/charts`,
      { params: { metric, window } },
    );
    return data;
  };
  return query(["org-usage-charts", orgId, metric, window], fn, { ...options });
};
