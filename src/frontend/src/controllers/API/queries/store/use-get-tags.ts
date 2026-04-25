import { useEffect } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ITagsDataArray {
  id: string;
  name: string;
}

type tagsQueryResponse = Array<ITagsDataArray>;

export const useGetTagsQuery: useQueryFunctionType<
  undefined,
  tagsQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getTagsFn = async () => {
    return await api.get<tagsQueryResponse>(`${getURL("STORE")}/tags`);
  };

  const responseFn = async () => {
    const { data } = await getTagsFn();
    return data;
  };

  const queryResult = query(["useGetTagsQuery"], responseFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  // Sync tags into the utility store outside the queryFn so this hook does
  // not subscribe to the store it mutates. Setter is read via getState().
  useEffect(() => {
    const data = queryResult.data;
    if (!data) return;
    useUtilityStore.getState().setTags(data);
  }, [queryResult.data]);

  return queryResult;
};
