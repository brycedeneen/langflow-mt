import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateRead } from "@/types/template";

export const TEMPLATES_QUERY_KEY = ["templates"];

export function useListTemplates() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateRead[]> => {
    const res = await api.get<TemplateRead[]>(getURL("TEMPLATES"));
    return res.data;
  };
  return query(TEMPLATES_QUERY_KEY, fn, {
    placeholderData: keepPreviousData,
  });
}
