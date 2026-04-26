import type {
  QuoteRead,
  QuoteSubmitRequest,
} from "@/types/pro-service-quote";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { PRO_SERVICE_QUOTES_QUERY_KEY } from "./use-list-quotes";

export function useSubmitQuote(flowId: string) {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (body: QuoteSubmitRequest): Promise<QuoteRead> => {
    return (
      await api.post<QuoteRead>(
        `${getURL("FLOWS")}/${flowId}/pro-service-quotes`,
        body,
      )
    ).data;
  };
  return mutate([...PRO_SERVICE_QUOTES_QUERY_KEY, "submit", flowId], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRO_SERVICE_QUOTES_QUERY_KEY });
    },
  });
}
