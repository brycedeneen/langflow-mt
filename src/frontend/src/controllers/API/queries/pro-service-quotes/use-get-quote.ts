import type { QuoteRead } from "@/types/pro-service-quote";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { PRO_SERVICE_QUOTES_QUERY_KEY } from "./use-list-quotes";

export function useGetQuote(quoteId: string | null) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<QuoteRead> => {
    return (
      await api.get<QuoteRead>(`${getURL("PRO_SERVICE_QUOTES")}/${quoteId}`)
    ).data;
  };
  return query([...PRO_SERVICE_QUOTES_QUERY_KEY, "detail", quoteId], fn, {
    enabled: quoteId !== null,
  });
}
