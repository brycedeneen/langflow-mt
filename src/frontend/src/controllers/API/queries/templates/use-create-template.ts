import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TemplateCreateBody, TemplateReadDetail } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useCreateTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (body: TemplateCreateBody): Promise<TemplateReadDetail> => {
    const res = await api.post<TemplateReadDetail>(getURL("TEMPLATES"), body);
    return res.data;
  };
  return mutate([...TEMPLATES_QUERY_KEY, "create"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
