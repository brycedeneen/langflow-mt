import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { Category } from "@/types/template";

export const CATEGORIES_QUERY_KEY = ["categories"] as const;

export function useListCategories() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Category[]> => {
    const res = await api.get<Category[]>(getURL("CATEGORIES"));
    return res.data;
  };
  return query([...CATEGORIES_QUERY_KEY, "list"], fn, {
    placeholderData: keepPreviousData,
  });
}
