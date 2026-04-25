import { validatedQueryFn } from "@/lib/validated-fetch";
import { TemplateReadDetail } from "@/schemas/api/_generated";
import type { TemplateCreateBody, TemplateReadDetail as TemplateReadDetailType } from "@/types/template";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useCreateTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (body: TemplateCreateBody): Promise<TemplateReadDetailType> => {
    return (await validatedQueryFn(
      "api.templates.create_template_api_v1_templates_post",
      TemplateReadDetail,
      async () => (await api.post<unknown>(getURL("TEMPLATES"), body)).data,
    )()) as TemplateReadDetailType;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "create"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
