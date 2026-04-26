import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { ADMIN_TAGS_QUERY_KEY } from "./use-list-tags-admin";

export interface DeleteTagVariables {
  id: string;
}

export const useDeleteTag: useMutationFunctionType<
  undefined,
  DeleteTagVariables,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteTagFn = async ({ id }: DeleteTagVariables): Promise<void> => {
    await api.delete(`${getURL("ADMIN_TAGS")}/${id}`);
  };

  const mutation = mutate(["useDeleteTag"], deleteTagFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ADMIN_TAGS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
