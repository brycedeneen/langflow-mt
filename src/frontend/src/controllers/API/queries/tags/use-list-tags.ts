import { keepPreviousData } from "@tanstack/react-query";
import type { TagRead } from "@/types/tag";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const TAGS_QUERY_KEY = ["tags"] as const;

export function useListTags() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TagRead[]> => {
    const res = await api.get<TagRead[]>(getURL("TAGS"));
    return res.data;
  };
  return query([...TAGS_QUERY_KEY, "list"], fn, {
    placeholderData: keepPreviousData,
  });
}
