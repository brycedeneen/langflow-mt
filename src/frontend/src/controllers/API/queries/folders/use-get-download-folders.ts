import type { UseMutationResult } from "@tanstack/react-query";
import { customGetDownloadTypeFolders } from "@/customization/utils/custom-get-download-folders";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetDownloadFolders {
  folderId: string;
}

export const useGetDownloadFolders: useMutationFunctionType<
  any, // Changed to any since we're getting the full response
  IGetDownloadFolders
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const downloadFoldersFn = async (
    payload: IGetDownloadFolders,
  ): Promise<unknown> => {
    const response = await api.get<unknown>(
      `${getURL("PROJECTS")}/download/${payload.folderId}`,
      customGetDownloadTypeFolders(),
    );
    return response;
  };

  const mutation: UseMutationResult<unknown, ApiError, IGetDownloadFolders> = mutate(
    ["useGetDownloadFolders"],
    downloadFoldersFn,
    options,
  );

  return mutation;
};
