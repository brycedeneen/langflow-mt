import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetInstalledMCP {
  projectId: string;
}

type getInstalledMCPResponse = Array<{
  name: string;
  installed: boolean;
  available: boolean;
}>;

export const useGetInstalledMCP: useQueryFunctionType<
  IGetInstalledMCP,
  getInstalledMCPResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    try {
      return await validatedQueryFn(
        "api.mcp_projects.check_installed_mcp_servers_api_v1_mcp_project__project_id__installed_get",
        z.array(z.unknown()),
        async () =>
          (
            await api.get<getInstalledMCPResponse>(
              `${getURL("MCP")}/${params.projectId}/installed`,
            )
          ).data,
      )() as getInstalledMCPResponse;
    } catch (error) {
      console.error(error);
      return [];
    }
  };

  const queryResult = query(
    ["useGetInstalledMCP", params.projectId],
    responseFn,
    {
      ...options,
    },
  );

  return queryResult;
};
