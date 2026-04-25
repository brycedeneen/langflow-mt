import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { ApiError, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
  id: string;
}

export const usePostUploadFile: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<unknown> => {
    const formData = new FormData();
    formData.append("file", payload.file);

    return await validatedQueryFn(
      "api.files.upload_file_api_v1_files_upload__flow_id__post",
      z.unknown(),
      async () =>
        (
          await api.post<any>(
            `${getURL("FILES")}/upload/${payload.id}`,
            formData,
          )
        ).data,
    )();
  };

  const mutation: UseMutationResult<IPostUploadFile, ApiError, IPostUploadFile> =
    mutate(
      ["usePostUploadFile"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
      options,
    );

  return mutation;
};
