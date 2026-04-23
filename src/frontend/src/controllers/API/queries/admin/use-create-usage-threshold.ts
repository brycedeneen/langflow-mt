import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Payload = {
  orgId: string;
  metric: string;
  period: string;
  threshold_value: number;
  cooldown_seconds?: number;
};

export const useCreateUsageThreshold: useMutationFunctionType<
  undefined,
  Payload,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ orgId, ...body }: Payload): Promise<unknown> => {
    const { data } = await api.post(
      `${getURL("ADMIN_USAGE_THRESHOLDS")}/${orgId}/usage/thresholds`,
      body,
    );
    return data;
  };
  return mutate(["useCreateUsageThreshold"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "usage-thresholds"] });
      options?.onSuccess?.(...args);
    },
  });
};
