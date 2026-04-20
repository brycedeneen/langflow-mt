import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateReadDetail, TemplateUpdateBody } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

type Vars = { templateId: string; body: TemplateUpdateBody };

export function useUpdateTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    templateId,
    body,
  }: Vars): Promise<TemplateReadDetail> => {
    const res = await api.put<TemplateReadDetail>(
      `${getURL("TEMPLATES")}/${templateId}`,
      body,
    );
    return res.data;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "update"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
