import type { useMutationFunctionType } from "@/types/api";
import type { TagRead, TagWrite } from "@/types/tag";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { ADMIN_TAGS_QUERY_KEY } from "./use-list-tags-admin";

export const useCreateTag: useMutationFunctionType<
  undefined,
  TagWrite,
  TagRead
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createTagFn = async (payload: TagWrite): Promise<TagRead> => {
    const { data } = await api.post<TagRead>(`${getURL("ADMIN_TAGS")}`, payload);
    return data;
  };

  const mutation = mutate(["useCreateTag"], createTagFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ADMIN_TAGS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
