import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Payload = {
  orgId: string;
  rule_type: string;
  config: Record<string, unknown>;
  flow_id?: string;
  cooldown_seconds?: number;
};

export const useCreateAlertRule: useMutationFunctionType<
  undefined,
  Payload,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ orgId, ...body }: Payload): Promise<unknown> => {
    const { data } = await api.post(
      `${getURL("ADMIN_ALERT_RULES")}/${orgId}/alert-rules`,
      body,
    );
    return data;
  };
  return mutate(["useCreateAlertRule"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "alert-rules"] });
      options?.onSuccess?.(...args);
    },
  });
};
