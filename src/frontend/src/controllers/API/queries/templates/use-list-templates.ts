import { keepPreviousData } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { TemplateRead } from "@/schemas/api/_generated";
import type { TemplateRead as TemplateReadType } from "@/types/template";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const TEMPLATES_QUERY_KEY = ["templates"];

export type ListTemplatesParams = {
  category?: string;
  scope?: "platform" | "org" | "all";
  created_by_me?: boolean;
  include_archived?: boolean;
};

export function useListTemplates(params?: ListTemplatesParams) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateReadType[]> => {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set("category", params.category);
    if (params?.scope) searchParams.set("scope", params.scope);
    if (params?.created_by_me) searchParams.set("created_by_me", "true");
    if (params?.include_archived)
      searchParams.set("include_archived", "true");
    const qs = searchParams.toString();
    const url = qs ? `${getURL("TEMPLATES")}?${qs}` : getURL("TEMPLATES");
    return (await validatedQueryFn(
      "api.templates.list_templates_api_v1_templates_get",
      z.array(TemplateRead),
      async () => (await api.get<unknown>(url)).data,
    )()) as TemplateReadType[];
  };
  return query(
    [...TEMPLATES_QUERY_KEY, "list", params ?? {}],
    fn,
    {
      placeholderData: keepPreviousData,
    },
  );
}
