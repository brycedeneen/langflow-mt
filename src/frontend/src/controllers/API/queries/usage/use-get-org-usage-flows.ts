import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string; window?: string; page?: number; size?: number };
type FlowRow = {
  flow_id: string;
  name: string;
  runs: number;
  run_seconds: number;
  tokens: number;
  cost_cents: number;
};
type Response = { items: FlowRow[]; total: number };

export const useGetOrgUsageFlows: useQueryFunctionType<Params, Response> = (
  { orgId, window = "30d", page = 1, size = 25 },
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(
      `${getURL("ORG_USAGE_FLOWS")}/${orgId}/usage/flows`,
      { params: { window, page, size } },
    );
    return data;
  };
  return query(["org-usage-flows", orgId, window, page, size], fn, { ...options });
};
