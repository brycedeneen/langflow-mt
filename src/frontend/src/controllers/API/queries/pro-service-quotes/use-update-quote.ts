import type {
  QuoteRead,
  QuoteUpdatePayload,
} from "@/types/pro-service-quote";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { PRO_SERVICE_QUOTES_QUERY_KEY } from "./use-list-quotes";

type UpdateQuoteVars = {
  quoteId: string;
  body: QuoteUpdatePayload;
};

export function useUpdateQuote() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ quoteId, body }: UpdateQuoteVars): Promise<QuoteRead> => {
    return (
      await api.patch<QuoteRead>(
        `${getURL("PRO_SERVICE_QUOTES")}/${quoteId}`,
        body,
      )
    ).data;
  };
  return mutate([...PRO_SERVICE_QUOTES_QUERY_KEY, "update"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRO_SERVICE_QUOTES_QUERY_KEY });
    },
  });
}
