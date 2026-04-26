import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "../templates/use-list-templates";
import { TAGS_QUERY_KEY } from "./use-list-tags";

export interface AssignTemplateTagsVariables {
  templateId: string;
  tagIds: string[];
}

export const useAssignTemplateTags: useMutationFunctionType<
  undefined,
  AssignTemplateTagsVariables,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const assignTemplateTagsFn = async ({
    templateId,
    tagIds,
  }: AssignTemplateTagsVariables): Promise<void> => {
    await api.put(`${getURL("TEMPLATES")}/${templateId}/tags`, {
      tag_ids: tagIds,
    });
  };

  const mutation = mutate(["useAssignTemplateTags"], assignTemplateTagsFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: TAGS_QUERY_KEY });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
