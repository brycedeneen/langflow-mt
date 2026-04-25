import { keepPreviousData } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { langflow__services__database__models__file__model__File } from "@/schemas/api/_generated";
import type { FileType } from "@/types/file_management";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type FilesResponse = FileType[];

export const useGetFilesV2: useQueryFunctionType<undefined, FilesResponse> = (
  config,
) => {
  const { query } = UseRequestProcessor();

  const getFilesFn = async () => {
    const data = await validatedQueryFn(
      "api.files.list_files_api_v2_files__get",
      z.array(langflow__services__database__models__file__model__File),
      async () =>
        (
          await api.get<FilesResponse>(
            `${getURL("FILE_MANAGEMENT", {}, true)}`,
          )
        ).data,
    )();
    return (data ?? []) as FilesResponse;
  };

  const queryResult = query(["useGetFilesV2"], getFilesFn, {
    placeholderData: keepPreviousData,
    ...config,
  });

  return queryResult;
};
