import type { UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchInstallMCPParams {
  project_id: string;
}

interface PatchInstallMCPResponse {
  message: string;
}

export type MCPTransport = "sse" | "streamablehttp";

interface PatchInstallMCPBody {
  client: string;
  transport?: MCPTransport;
}

export const usePatchInstallMCP: useMutationFunctionType<
  PatchInstallMCPParams,
  PatchInstallMCPBody,
  PatchInstallMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchInstallMCP(
    body: PatchInstallMCPBody,
  ): Promise<PatchInstallMCPResponse> {
    try {
      const res = await validatedQueryFn(
        "api.mcp_projects.install_mcp_config_api_v1_mcp_project__project_id__install_post",
        z.unknown(),
        async () =>
          (
            await api.post(
              `${getURL("MCP")}/${params.project_id}/install`,
              body,
            )
          ).data,
      )() as { message?: string };

      return { message: res?.message || "MCP installed successfully" };
    } catch (error: any) {
      // Transform the error to include a message that can be handled by the UI
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "Failed to install MCP";
      throw new Error(errorMessage);
    }
  }

  const mutation: UseMutationResult<
    PatchInstallMCPResponse,
    any,
    PatchInstallMCPBody
  > = mutate(["usePatchInstallMCP", params.project_id], patchInstallMCP, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetInstalledMCP", params.project_id],
      });
      options?.onSuccess?.(data, variables, context, ...rest);
    },
  });

  return mutation;
};
