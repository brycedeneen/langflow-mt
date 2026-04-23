import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Payload = {
  id: string;
  threshold_value?: number;
  is_active?: boolean;
  cooldown_seconds?: number;
};

export const usePatchUsageThreshold: useMutationFunctionType<
  undefined,
  Payload,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ id, ...body }: Payload): Promise<unknown> => {
    const { data } = await api.patch(
      `${getURL("ADMIN_USAGE_THRESHOLD")}/${id}`,
      body,
    );
    return data;
  };
  return mutate(["usePatchUsageThreshold"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "usage-thresholds"] });
      options?.onSuccess?.(...args);
    },
  });
};
