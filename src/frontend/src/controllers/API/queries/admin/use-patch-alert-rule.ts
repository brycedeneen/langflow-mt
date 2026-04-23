import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Payload = {
  id: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
  cooldown_seconds?: number;
};

export const usePatchAlertRule: useMutationFunctionType<
  undefined,
  Payload,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ id, ...body }: Payload): Promise<unknown> => {
    const { data } = await api.patch(`${getURL("ADMIN_ALERT_RULE")}/${id}`, body);
    return data;
  };
  return mutate(["usePatchAlertRule"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "alert-rules"] });
      options?.onSuccess?.(...args);
    },
  });
};
