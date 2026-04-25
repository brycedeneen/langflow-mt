import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFiles {
  ids: string[];
}

export const useDeleteFilesV2: useMutationFunctionType<
  undefined,
  IDeleteFiles
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFileFn = async (params): Promise<any> => {
    return await validatedQueryFn(
      "api.files.delete_files_batch_api_v2_files_batch__delete",
      z.unknown(),
      async () =>
        (
          await api.delete<any>(
            `${getURL("FILE_MANAGEMENT", { mode: "batch/" }, true)}`,
            {
              data: params.ids,
            },
          )
        ).data,
    )();
  };

  const mutation: UseMutationResult<any, any, IDeleteFiles> = mutate(
    ["useDeleteFilesV2"],
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
