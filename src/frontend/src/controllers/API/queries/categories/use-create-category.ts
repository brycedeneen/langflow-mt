import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { Category } from "@/types/template";
import { CATEGORIES_QUERY_KEY } from "./use-list-categories";

type CategoryCreateBody = {
  name: string;
  icon?: string;
  color?: string;
  description?: string | null;
};

export function useCreateCategory() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (body: CategoryCreateBody): Promise<Category> => {
    const res = await api.post<Category>(getURL("CATEGORIES"), body);
    return res.data;
  };
  return mutate([...CATEGORIES_QUERY_KEY, "create"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
    },
  });
}
