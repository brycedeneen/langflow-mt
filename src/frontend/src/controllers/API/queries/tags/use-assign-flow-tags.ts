import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TAGS_QUERY_KEY } from "./use-list-tags";

export interface AssignFlowTagsVariables {
  flowId: string;
  tagIds: string[];
}

export const useAssignFlowTags: useMutationFunctionType<
  undefined,
  AssignFlowTagsVariables,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const assignFlowTagsFn = async ({
    flowId,
    tagIds,
  }: AssignFlowTagsVariables): Promise<void> => {
    await api.put(`${getURL("FLOWS")}/${flowId}/tags`, { tag_ids: tagIds });
  };

  const mutation = mutate(["useAssignFlowTags"], assignFlowTagsFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["useGetFolder"] });
      queryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
      queryClient.invalidateQueries({ queryKey: TAGS_QUERY_KEY });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
