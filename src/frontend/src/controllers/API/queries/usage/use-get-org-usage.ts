import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string; window?: "1d" | "7d" | "30d" };
type Response = {
  runs: number;
  run_seconds: number;
  tokens: number;
  cost_cents: number;
  window_days: number;
};

export const useGetOrgUsage: useQueryFunctionType<Params, Response> = (
  { orgId, window = "7d" },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ORG_USAGE_KPI")}/${orgId}/usage`,
      { params: { window } },
    );
    return data;
  };
  return query(["org-usage", orgId, window], fn, { ...options });
};
