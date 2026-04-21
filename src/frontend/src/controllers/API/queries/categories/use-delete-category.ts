import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { CATEGORIES_QUERY_KEY } from "./use-list-categories";

export function useDeleteCategory() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ categoryId }: { categoryId: string }): Promise<void> => {
    await api.delete(`${getURL("CATEGORIES")}/${categoryId}`);
  };
  return mutate([...CATEGORIES_QUERY_KEY, "delete"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
    },
  });
}
