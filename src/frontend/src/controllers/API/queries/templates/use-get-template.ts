import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateReadDetail } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useGetTemplate(templateId: string | null) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateReadDetail> => {
    const res = await api.get<TemplateReadDetail>(
      `${getURL("TEMPLATES")}/${templateId}`,
    );
    return res.data;
  };
  return query([...TEMPLATES_QUERY_KEY, templateId], fn, {
    enabled: templateId !== null,
  });
}
