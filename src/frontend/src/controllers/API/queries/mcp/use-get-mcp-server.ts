import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { MCPServerConfig } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type getMCPServerResponse = MCPServerType;

interface IGetMCPServer {
  name: string;
}

export const useGetMCPServer: useMutationFunctionType<
  undefined,
  IGetMCPServer,
  getMCPServerResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const responseFn = async (params: IGetMCPServer) => {
    const data = await validatedQueryFn(
      "api.mcp.get_server_endpoint_api_v2_mcp_servers__server_name__get",
      MCPServerConfig,
      async () =>
        (
          await api.get<Omit<getMCPServerResponse, "name">>(
            `${getURL("MCP_SERVERS", undefined, true)}/${params.name}`,
          )
        ).data,
    )();

    return { ...data, name: params.name } as getMCPServerResponse;
  };

  const queryResult = mutate(["useGetMCPServer"], responseFn, {
    ...options,
  });

  return queryResult;
};
