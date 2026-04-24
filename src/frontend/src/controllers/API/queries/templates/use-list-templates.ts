import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateRead } from "@/types/template";

export const TEMPLATES_QUERY_KEY = ["templates"];

export type ListTemplatesParams = {
  category?: string;
  scope?: "platform" | "org" | "all";
  created_by_me?: boolean;
  include_archived?: boolean;
  tag_id?: string[];
};

export function useListTemplates(params?: ListTemplatesParams) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateRead[]> => {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set("category", params.category);
    if (params?.scope) searchParams.set("scope", params.scope);
    if (params?.created_by_me) searchParams.set("created_by_me", "true");
    if (params?.include_archived)
      searchParams.set("include_archived", "true");
    if (params?.tag_id && params.tag_id.length > 0) {
      for (const id of params.tag_id) {
        searchParams.append("tag_id", id);
      }
    }
    const qs = searchParams.toString();
    const url = qs ? `${getURL("TEMPLATES")}?${qs}` : getURL("TEMPLATES");
    const res = await api.get<TemplateRead[]>(url);
    return res.data;
  };
  return query(
    [...TEMPLATES_QUERY_KEY, "list", params ?? {}],
    fn,
    {
      placeholderData: keepPreviousData,
    },
  );
}
