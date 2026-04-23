import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Payload = { flowId: string };
type Response = {
  estimate: {
    expected_cost_cents: number;
    low_cost_cents: number;
    high_cost_cents: number;
    confidence: "rough" | "low" | "none";
  };
  per_component: Array<{
    node_id: string;
    kind: string;
    model: string;
    cost_cents: number;
    unknown: boolean;
  }>;
};

export const useEstimateFlowCost: useMutationFunctionType<
  undefined,
  Payload,
  Response
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const fn = async ({ flowId }: Payload): Promise<Response> => {
    const { data } = await api.post<Response>(
      `${getURL("FLOW_ESTIMATE_COST")}/${flowId}/estimate-cost`,
    );
    return data;
  };
  return mutate(["useEstimateFlowCost"], fn, { ...options });
};
