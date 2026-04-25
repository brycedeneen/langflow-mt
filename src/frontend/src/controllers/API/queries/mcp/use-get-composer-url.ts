import { validatedQueryFn } from "@/lib/validated-fetch";
import { ComposerUrlResponse } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { ComposerUrlResponseType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type UseGetProjectComposerUrlParams = {
  projectId: string;
};

export const useGetProjectComposerUrl: useQueryFunctionType<
  UseGetProjectComposerUrlParams,
  ComposerUrlResponseType
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<ComposerUrlResponseType> => {
    try {
      return await validatedQueryFn(
        "api.mcp_projects.get_project_composer_url_api_v1_mcp_project__project_id__composer_url_get",
        ComposerUrlResponse,
        async () => (await api.get(`${getURL("MCP")}/${projectId}/composer-url`)).data,
      )() as ComposerUrlResponseType;
    } catch (error) {
      console.error(error);
      throw error;
    }
  };

  return query(["project-composer-url", projectId], responseFn, {
    staleTime: 30000, // 30 seconds
    retry: 1,
    // Backend returns 200 responses with error_message field instead of HTTP errors
    ...options,
  });
};
