import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useHardDeleteTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<void> => {
    // Synthetic operation id for Sentry telemetry distinguishability.
    // The id is manually registered in generated.meta.ts (see MANUAL ADDITION note).
    // Do NOT replace with the soft-delete id — that defeats the purpose.
    await validatedQueryFn(
      "api.templates.hard_delete_template_api_v1_templates__template_id__hard_delete_post",
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
