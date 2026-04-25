import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useQueryFunctionType } from "@/types/api";
import type { MCPProjectResponseType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFlowsMCP {
  projectId: string;
}

type getFlowsMCPResponse = MCPProjectResponseType;

export const useGetFlowsMCP: useQueryFunctionType<
  IGetFlowsMCP,
  getFlowsMCPResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    try {
      return await validatedQueryFn(
        "api.mcp_projects.list_project_tools_api_v1_mcp_project__project_id__get",
        z.unknown(),
        async () =>
          (
            await api.get<getFlowsMCPResponse>(
              `${getURL("MCP")}/${params.projectId}?mcp_enabled=false`,
            )
          ).data,
      )() as getFlowsMCPResponse;
    } catch (error) {
      console.error(error);
      return { tools: [], auth_settings: undefined };
    }
  };

  const queryResult = query(["useGetFlowsMCP", params.projectId], responseFn, {
    ...options,
  });

  return queryResult;
};
