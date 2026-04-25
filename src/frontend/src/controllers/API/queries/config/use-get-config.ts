import axios from "axios";
import { useEffect } from "react";
import {
  DEFAULT_POLLING_INTERVAL,
  DEFAULT_TIMEOUT,
} from "@/constants/constants";
import { EventDeliveryType } from "@/constants/enums";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

// Base config - common fields shared by all responses
interface BaseConfig {
  type: "public" | "full";
  frontend_timeout: number;
  max_file_size_upload: number;
  event_delivery: EventDeliveryType;
  voice_mode_available: boolean;
  allow_custom_components: boolean;
}

// Public config = base config (unauthenticated users get only base fields)
export type PublicConfigResponse = BaseConfig;

// Full config = base + authenticated-only fields
export interface ConfigResponse extends BaseConfig {
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
  feature_flags: Record<string, any>;
  webhook_polling_interval: number;
  serialization_max_items_length: number;
  webhook_auth_enable: boolean;
  default_folder_name: string;
  hide_getting_started_progress: boolean;
}

// Union type for the response (can be either public or full config)
export type ConfigResponseType = PublicConfigResponse | ConfigResponse;

// Type guard to check if response is full config (uses type discriminator)
export const isFullConfig = (
  config: ConfigResponseType,
): config is ConfigResponse => {
  return config.type === "full";
};

export const useGetConfig: useQueryFunctionType<
  undefined,
  ConfigResponseType
> = (options) => {
  const { query } = UseRequestProcessor();

  const getConfigFn = async () => {
    // The /config endpoint returns different responses based on authentication:
    // - Authenticated: Full ConfigResponse with all settings
    // - Unauthenticated: PublicConfigResponse with limited settings
    const response = await api.get<ConfigResponseType>(`${getURL("CONFIG")}`);
    return response.data;
  };

  const queryResult = query(["useGetConfig"], getConfigFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  // Sync config into stores outside the queryFn so this hook does not
  // subscribe to the stores it mutates (render-loop hazard). Setters are
  // accessed via getState() to avoid subscribing.
  useEffect(() => {
    const data = queryResult.data;
    if (!data) return;

    // Set timeout (present in both response types)
    const timeoutInMilliseconds = data.frontend_timeout
      ? data.frontend_timeout * 1000
      : DEFAULT_TIMEOUT;
    axios.defaults.baseURL = "";
    axios.defaults.timeout = timeoutInMilliseconds;

    const utilityState = useUtilityStore.getState();
    const flowsManagerState = useFlowsManagerStore.getState();

    // Set fields present in both public and full config
    utilityState.setMaxFileSizeUpload(data.max_file_size_upload);
    utilityState.setEventDelivery(
      data.event_delivery ?? EventDeliveryType.POLLING,
    );

    // Set authenticated-only fields if present (full config)
    if (isFullConfig(data)) {
      flowsManagerState.setAutoSaving(data.auto_saving);
      flowsManagerState.setAutoSavingInterval(data.auto_saving_interval);
      flowsManagerState.setHealthCheckMaxRetries(data.health_check_max_retries);
      utilityState.setFeatureFlags(data.feature_flags);
      utilityState.setSerializationMaxItemsLength(
        data.serialization_max_items_length,
      );
      utilityState.setWebhookPollingInterval(
        data.webhook_polling_interval ?? DEFAULT_POLLING_INTERVAL,
      );
      utilityState.setWebhookAuthEnable(data.webhook_auth_enable ?? true);
      utilityState.setDefaultFolderName(
        data.default_folder_name ?? "Starter Project",
      );
      utilityState.setHideGettingStartedProgress(
        data.hide_getting_started_progress ?? false,
      );
    }
  }, [queryResult.data]);

  return queryResult;
};
