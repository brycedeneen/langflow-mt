import type { UseMutationResult } from "@tanstack/react-query";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { langflow__api__schemas__UploadFileResponse } from "@/schemas/api/_generated";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DuplicateFileQueryParams {
  id: string;
  filename: string;
  type: string;
}

export const useDuplicateFileV2: useMutationFunctionType<
  DuplicateFileQueryParams,
  void
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const duplicateFileFn = async (): Promise<unknown> => {
    // First download the file
    const response = await fetch(
      `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
      {
        headers: {
          Accept: "*/*",
        },
        credentials: getFetchCredentials(),
      },
    );
    const blob = await response.blob();

    // Create a File object from the blob
    const file = new File([blob], params.filename + "." + params.type, {
      type: blob.type,
    });

    // Upload the file
    const formData = new FormData();
    formData.append("file", file);

    return await validatedQueryFn(
      "api.files.upload_user_file_api_v2_files__post",
      langflow__api__schemas__UploadFileResponse,
      async () =>
        (
          await api.post<any>(
            `${getURL("FILE_MANAGEMENT", {}, true)}/`,
            formData,
          )
        ).data,
    )();
  };

  const mutation: UseMutationResult<unknown, ApiError, void> = mutate(
    ["useDuplicateFileV2"],
    duplicateFileFn,
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
