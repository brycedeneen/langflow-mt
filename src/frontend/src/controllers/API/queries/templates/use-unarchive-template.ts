import { validatedQueryFn } from "@/lib/validated-fetch";
import { TemplateRead } from "@/schemas/api/_generated";
import type { TemplateRead as TemplateReadType } from "@/types/template";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useUnarchiveTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<TemplateReadType> => {
    return (await validatedQueryFn(
      "api.templates.unarchive_template_api_v1_templates__template_id__unarchive_post",
      TemplateRead,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("TEMPLATES")}/${templateId}/unarchive`,
          )
        ).data,
    )()) as TemplateReadType;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "unarchive"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
