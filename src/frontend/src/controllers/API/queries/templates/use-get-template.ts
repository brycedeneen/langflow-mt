import { validatedQueryFn } from "@/lib/validated-fetch";
import { TemplateReadDetail } from "@/schemas/api/_generated";
import type { TemplateReadDetail as TemplateReadDetailType } from "@/types/template";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useGetTemplate(templateId: string | null) {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateReadDetailType> => {
    return (await validatedQueryFn(
      "api.templates.get_template_api_v1_templates__template_id__get",
      TemplateReadDetail,
      async () =>
        (await api.get<unknown>(`${getURL("TEMPLATES")}/${templateId}`)).data,
    )()) as TemplateReadDetailType;
  };
  return query([...TEMPLATES_QUERY_KEY, templateId], fn, {
    enabled: templateId !== null,
  });
}
