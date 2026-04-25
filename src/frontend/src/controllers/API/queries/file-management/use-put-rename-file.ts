import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { langflow__services__database__models__file__model__File } from "@/schemas/api/_generated";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostRenameFile {
  id: string;
  name: string;
}

export const usePostRenameFileV2: useMutationFunctionType<
  undefined,
  IPostRenameFile
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postRenameFileFn = async (payload: IPostRenameFile): Promise<unknown> => {
    return await validatedQueryFn(
      "api.files.edit_file_name_api_v2_files__file_id__put",
      langflow__services__database__models__file__model__File,
      async () =>
        (
          await api.put<any>(
            `${getURL("FILE_MANAGEMENT", { id: payload.id }, true)}?name=${encodeURI(payload.name)}`,
          )
        ).data,
    )();
  };

  const mutation: UseMutationResult<IPostRenameFile, ApiError, IPostRenameFile> =
    mutate(
      ["usePostRenameFileV2"],
      async (payload: IPostRenameFile) => {
        const res = await postRenameFileFn(payload);
        return res;
      },
      {
        onSettled: (data, error, variables, context, ...rest) => {
          queryClient.invalidateQueries({
            queryKey: ["useGetFilesV2"],
          });
          options?.onSettled?.(data, error, variables, context, ...rest);
        },
        ...options,
      },
    );

  return mutation;
};
