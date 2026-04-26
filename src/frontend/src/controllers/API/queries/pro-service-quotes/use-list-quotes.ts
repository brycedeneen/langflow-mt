import { keepPreviousData } from "@tanstack/react-query";
import type {
  ProServiceQuoteStatus,
  QuoteListResponse,
} from "@/types/pro-service-quote";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const PRO_SERVICE_QUOTES_QUERY_KEY = ["pro-service-quotes"];

export type ListQuotesParams = {
  status?: ProServiceQuoteStatus;
  org_id?: string;
};

export function useListQuotes(params?: ListQuotesParams) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<QuoteListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.org_id) searchParams.set("org_id", params.org_id);
    const qs = searchParams.toString();
    const base = getURL("PRO_SERVICE_QUOTES");
    const url = qs ? `${base}?${qs}` : base;
    return (await api.get<QuoteListResponse>(url)).data;
  };
  return query([...PRO_SERVICE_QUOTES_QUERY_KEY, "list", params ?? {}], fn, {
    placeholderData: keepPreviousData,
  });
}
