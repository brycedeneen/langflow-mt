import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateRead } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useUnarchiveTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<TemplateRead> => {
    const res = await api.post<TemplateRead>(
      `${getURL("TEMPLATES")}/${templateId}/unarchive`,
    );
    return res.data;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "unarchive"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
