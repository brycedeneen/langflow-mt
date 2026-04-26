import type { useMutationFunctionType } from "@/types/api";
import type { TagRead, TagWrite } from "@/types/tag";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { ADMIN_TAGS_QUERY_KEY } from "./use-list-tags-admin";

export interface UpdateTagVariables extends TagWrite {
  id: string;
}

export const useUpdateTag: useMutationFunctionType<
  undefined,
  UpdateTagVariables,
  TagRead
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateTagFn = async ({
    id,
    ...payload
  }: UpdateTagVariables): Promise<TagRead> => {
    const { data } = await api.put<TagRead>(
      `${getURL("ADMIN_TAGS")}/${id}`,
      payload,
    );
    return data;
  };

  const mutation = mutate(["useUpdateTag"], updateTagFn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ADMIN_TAGS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      options?.onSuccess?.(...args);
    },
  });

  return mutation;
};
