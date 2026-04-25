import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useDeleteTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<void> => {
    await validatedQueryFn(
      "api.templates.delete_template_api_v1_templates__template_id__delete",
      z.unknown(),
      async () => (await api.delete<unknown>(`${getURL("TEMPLATES")}/${templateId}`)).data,
    )();
  };
  return mutate([...TEMPLATES_QUERY_KEY, "delete"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
