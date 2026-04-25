import { keepPreviousData } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ProfilePicturesQueryResponse extends Record<string, string[]> {
  files: string[];
}

export const useGetProfilePicturesQuery: useQueryFunctionType<
  undefined,
  ProfilePicturesQueryResponse
> = () => {
  const { query } = UseRequestProcessor();

  const getProfilePicturesFn =
    async (): Promise<ProfilePicturesQueryResponse> => {
      return await validatedQueryFn(
        "api.files.list_profile_pictures_api_v1_files_profile_pictures_list_get",
        z.unknown(),
        async () =>
          (
            await api.get<ProfilePicturesQueryResponse>(
              `${getURL("FILES")}/profile_pictures/list`,
            )
          ).data,
      )() as ProfilePicturesQueryResponse;
    };

  const responseFn = async () => {
    const data = await getProfilePicturesFn();

    const profilePictures = {};

    data?.files?.forEach((profile_picture) => {
      const [folder, path] = profile_picture.split("/");

      if (profilePictures[folder]) {
        profilePictures[folder].push(path);
      } else {
        profilePictures[folder] = [path];
      }
    });

    return profilePictures;
  };

  const queryResult = query(["useGetProfilePicturesQuery"], responseFn, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
