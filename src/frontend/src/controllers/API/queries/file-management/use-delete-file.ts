import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFile {
  id: string;
}

export const useDeleteFileV2: useMutationFunctionType<IDeleteFile, void> = (
  params,
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFileFn = async (): Promise<unknown> => {
    return await validatedQueryFn(
      "api.files.delete_file_api_v2_files__file_id__delete",
      z.unknown(),
      async () =>
        (
          await api.delete<any>(
            `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
          )
        ).data,
    )();
  };

  const mutation: UseMutationResult<unknown, ApiError, void> = mutate(
    ["useDeleteFileV2"],
    deleteFileFn,
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
