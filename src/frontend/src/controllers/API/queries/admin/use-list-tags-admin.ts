import type { useQueryFunctionType } from "@/types/api";
import type { TagRead } from "@/types/tag";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const ADMIN_TAGS_QUERY_KEY = ["admin", "tags"] as const;

export const useListTagsAdmin: useQueryFunctionType<undefined, TagRead[]> = (
  options,
) => {
  const { query } = UseRequestProcessor();

  const listTagsAdminFn = async (): Promise<TagRead[]> => {
    const { data } = await api.get<TagRead[]>(getURL("ADMIN_TAGS"));
    return data;
  };

  return query([...ADMIN_TAGS_QUERY_KEY, "list"], listTagsAdminFn, {
    ...options,
  });
};
