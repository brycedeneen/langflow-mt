import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMCPServerResponse {
  message: string;
}

interface DeleteMCPServerType {
  name: string;
}

export const useDeleteMCPServer: useMutationFunctionType<
  undefined,
  DeleteMCPServerType,
  DeleteMCPServerResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteMCPServer(
    payload: MCPServerType,
  ): Promise<DeleteMCPServerResponse> {
    try {
      const res = await validatedQueryFn(
        "api.mcp.delete_server_api_v2_mcp_servers__server_name__delete",
        z.unknown(),
        async () =>
          (
            await api.delete(
              `${getURL("MCP_SERVERS", undefined, true)}/${payload.name}`,
            )
          ).data,
      )() as { message?: string };

      return {
        message: res?.message || "MCP Server deleted successfully",
      };
    } catch (error: any) {
      // Transform the error to include a message that can be handled by the UI
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete MCP Server";
      throw new Error(errorMessage);
    }
  }

  const mutation: UseMutationResult<
    DeleteMCPServerResponse,
    any,
    MCPServerType
  > = mutate(["useDeleteMCPServer"], deleteMCPServer, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      queryClient.refetchQueries({
        queryKey: ["useGetMCPServers"],
      });
      options?.onSuccess?.(data, variables, context, ...rest);
    },
  });

  return mutation;
};
