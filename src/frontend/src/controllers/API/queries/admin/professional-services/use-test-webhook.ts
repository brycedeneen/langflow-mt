import type { ProServiceWebhookTestResult } from "@/types/pro-service-quote";
import { api } from "../../../api";
import { getURL } from "../../../helpers/constants";
import { UseRequestProcessor } from "../../../services/request-processor";
import { ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY } from "./use-settings";

export function useTestProServiceWebhook() {
  const { mutate } = UseRequestProcessor();
  const fn = async (): Promise<ProServiceWebhookTestResult> => {
    return (
      await api.post<ProServiceWebhookTestResult>(
        `${getURL("ADMIN_PRO_SERVICE_SETTINGS")}/test-webhook`,
        {},
      )
    ).data;
  };
  return mutate(
    [...ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY, "test-webhook"],
    fn,
  );
}
