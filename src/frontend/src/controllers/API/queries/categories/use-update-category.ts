import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { Category } from "@/types/template";
import { CATEGORIES_QUERY_KEY } from "./use-list-categories";

type CategoryUpdateBody = {
  name?: string;
  icon?: string;
  color?: string;
  description?: string | null;
};

type Vars = { categoryId: string; body: CategoryUpdateBody };

export function useUpdateCategory() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ categoryId, body }: Vars): Promise<Category> => {
    const res = await api.put<Category>(
      `${getURL("CATEGORIES")}/${categoryId}`,
      body,
    );
    return res.data;
  };
  return mutate([...CATEGORIES_QUERY_KEY, "update"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
    },
  });
}
