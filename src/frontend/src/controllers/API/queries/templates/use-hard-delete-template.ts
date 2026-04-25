import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useHardDeleteTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<void> => {
    // TODO: Phase 2.c follow-up — no distinct "hard_delete" operation id in the
    // OpenAPI registry. This hook hits the same DELETE /templates/{id} endpoint
    // as useDeleteTemplate. Using the soft-delete op id as the closest match.
    await validatedQueryFn(
      "api.templates.delete_template_api_v1_templates__template_id__delete",
      z.unknown(),
      async () => (await api.delete<unknown>(`${getURL("TEMPLATES")}/${templateId}`)).data,
    )();
  };
  return mutate([...TEMPLATES_QUERY_KEY, "hardDelete"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
    // On 409, the caller inspects err.response?.status === 409
    // and err.response?.data?.detail?.referencing_flow_ids to surface the
    // "N flow(s) still reference this template" message.
  });
}
