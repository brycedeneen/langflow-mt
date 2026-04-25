import { validatedQueryFn } from "@/lib/validated-fetch";
import { TemplateReadDetail } from "@/schemas/api/_generated";
import type { TemplateReadDetail as TemplateReadDetailType, TemplateUpdateBody, TemplatePatchBody } from "@/types/template";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

type Vars = { templateId: string; body: TemplateUpdateBody | TemplatePatchBody };

export function useUpdateTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    templateId,
    body,
  }: Vars): Promise<TemplateReadDetailType> => {
    // Note: hook uses PATCH semantics (partial update); id maps to patch operation.
    // PUT id (update_template_api_v1_templates__template_id__put) is also registered
    // but the actual call is PATCH, so we use the patch op id.
    return (await validatedQueryFn(
      "api.templates.patch_template_api_v1_templates__template_id__patch",
      TemplateReadDetail,
      async () =>
        (
          await api.patch<unknown>(
            `${getURL("TEMPLATES")}/${templateId}`,
            body,
          )
        ).data,
    )()) as TemplateReadDetailType;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "update"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
