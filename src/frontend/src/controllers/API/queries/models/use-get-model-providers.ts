import { validatedQueryFn } from "@/lib/validated-fetch";
import { ListModelsResponseSchema } from "@/schemas/app/internal/models";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelProviderInfo {
  provider: string;
  models: Array<{
    model_name: string;
    metadata: Record<string, any>;
  }>;
  is_enabled: boolean;
  is_configured?: boolean;
  api_docs_url?: string;
}

export interface ModelProviderWithStatus extends ModelProviderInfo {
  icon?: string;
}

export interface GetModelProvidersParams {
  includeDeprecated?: boolean;
  includeUnsupported?: boolean;
}

export const useGetModelProviders: useQueryFunctionType<
  GetModelProvidersParams | undefined,
  ModelProviderWithStatus[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getModelProvidersFn = async (): Promise<ModelProviderWithStatus[]> => {
    // Build query params
    const queryParams = new URLSearchParams();
    if (params?.includeDeprecated) {
      queryParams.append("include_deprecated", "true");
    }
    if (params?.includeUnsupported) {
      queryParams.append("include_unsupported", "true");
    }

    const url = `${getURL("MODELS")}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;

    // Fetch the models with provider information including is_enabled status from server
    // Let errors propagate so React Query can retry and preserve stale data
    const providersData = await validatedQueryFn(
      "api.models.list_models",
      ListModelsResponseSchema,
      async () => (await api.get<unknown>(url)).data,
    )();

    return (providersData as unknown as ModelProviderInfo[]).map((providerInfo) => ({
      ...providerInfo,
      icon: getProviderIcon(providerInfo.provider),
    }));
  };

  const queryResult = query(
    [
      "useGetModelProviders",
      params?.includeDeprecated,
      params?.includeUnsupported,
    ],
    getModelProvidersFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};

// Helper function to map provider names to icon names
const getProviderIcon = (providerName: string): string => {
  const iconMap: Record<string, string> = {
    OpenAI: "OpenAI",
    Anthropic: "Anthropic",
    "Google Generative AI": "GoogleGenerativeAI",
    Groq: "Groq",
    "Amazon Bedrock": "Bedrock",
    NVIDIA: "NVIDIA",
    Cohere: "Cohere",
    "Azure OpenAI": "AzureOpenAI",
    SambaNova: "SambaNova",
    Ollama: "Ollama",
  };

  return iconMap[providerName] || "Bot";
};
