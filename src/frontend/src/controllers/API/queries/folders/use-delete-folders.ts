import type { UseMutationResult } from "@tanstack/react-query";
import { useFolderStore } from "@/stores/foldersStore";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteFoldersParams {
  folder_id: string;
}

export const useDeleteFolders: useMutationFunctionType<
  undefined,
  DeleteFoldersParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFolder = async ({
    folder_id,
  }: DeleteFoldersParams): Promise<string> => {
    await api.delete(`${getURL("PROJECTS")}/${folder_id}`);
    return folder_id;
  };

  const mutation: UseMutationResult<
    DeleteFoldersParams,
    ApiError,
    DeleteFoldersParams
  > = mutate(["useDeleteFolders"], deleteFolder, {
    ...options,
    onSuccess: (...args) => {
      // Update the folder store outside the mutationFn so this hook does not
      // subscribe to the store it mutates. State + setter read via getState().
      const folder_id = args[0];
      const folderState = useFolderStore.getState();
      folderState.setFolders(
        folderState.folders.filter((f) => f.id !== folder_id),
      );
      (options as any)?.onSuccess?.(...args);
    },
    onSettled: (id) => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders", id] });
      queryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
    },
  });

  return mutation;
};
