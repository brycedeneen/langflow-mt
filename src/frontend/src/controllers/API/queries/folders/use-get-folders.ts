import { useEffect } from "react";
import type { FolderType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetFoldersQuery: useQueryFunctionType<
  undefined,
  FolderType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getFoldersFn = async (): Promise<FolderType[]> => {
    const res = await api.get(`${getURL("PROJECTS")}/`);
    return res.data;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, {
    ...options,
    enabled: isAuthenticated && (options?.enabled ?? true),
  });

  // Sync folders into the folder store outside the queryFn so this hook does
  // not subscribe to the store it mutates. Read defaultFolderName and setters
  // via getState() to avoid subscribing.
  useEffect(() => {
    const data = queryResult.data;
    if (!data) return;
    const defaultFolderName = useUtilityStore.getState().defaultFolderName;
    const folderState = useFolderStore.getState();
    // Find default folder by name, or fall back to first folder if not found
    const myCollectionId =
      data?.find((f) => f.name === defaultFolderName)?.id ?? data?.[0]?.id;
    folderState.setMyCollectionId(myCollectionId);
    folderState.setFolders(data);
  }, [queryResult.data]);

  return queryResult;
};
