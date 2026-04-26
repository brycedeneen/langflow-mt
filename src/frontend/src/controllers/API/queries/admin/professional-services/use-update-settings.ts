import type {
  ProServiceSettings,
  ProServiceSettingsWrite,
} from "@/types/pro-service-quote";
import { api } from "../../../api";
import { getURL } from "../../../helpers/constants";
import { UseRequestProcessor } from "../../../services/request-processor";
import { ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY } from "./use-settings";

export function useUpdateProServiceSettings() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (
    body: ProServiceSettingsWrite,
  ): Promise<ProServiceSettings> => {
    return (
      await api.put<ProServiceSettings>(
        getURL("ADMIN_PRO_SERVICE_SETTINGS"),
        body,
      )
    ).data;
  };
  return mutate(
    [...ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY, "update"],
    fn,
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY,
        });
      },
    },
  );
}
