import type { ProServiceSettings } from "@/types/pro-service-quote";
import { api } from "../../../api";
import { getURL } from "../../../helpers/constants";
import { UseRequestProcessor } from "../../../services/request-processor";

export const ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY = [
  "admin",
  "professional-services",
  "settings",
];

export function useGetProServiceSettings() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<ProServiceSettings> => {
    return (
      await api.get<ProServiceSettings>(getURL("ADMIN_PRO_SERVICE_SETTINGS"))
    ).data;
  };
  return query(ADMIN_PRO_SERVICE_SETTINGS_QUERY_KEY, fn);
}
