import type { PreviewResponse } from "@/types/pro-service-quote";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { PRO_SERVICE_QUOTES_QUERY_KEY } from "./use-list-quotes";

/**
 * Generate a non-persistent pro-service estimate for a flow.
 *
 * The preview endpoint takes no body — the backend derives the estimate from
 * the flow's component graph plus the org's configured rates.
 */
export function usePreviewQuote(flowId: string) {
  const { mutate } = UseRequestProcessor();
  const fn = async (): Promise<PreviewResponse> => {
    return (
      await api.post<PreviewResponse>(
        `${getURL("FLOWS")}/${flowId}/pro-service-quotes/preview`,
        {},
      )
    ).data;
  };
  return mutate([...PRO_SERVICE_QUOTES_QUERY_KEY, "preview", flowId], fn);
}
