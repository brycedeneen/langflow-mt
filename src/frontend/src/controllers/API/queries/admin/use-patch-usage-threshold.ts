import { validatedQueryFn } from "@/lib/validated-fetch";
import { ThresholdRead } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
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
  z.infer<typeof ThresholdRead>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    id,
    ...body
  }: Payload): Promise<z.infer<typeof ThresholdRead>> => {
    const data = await validatedQueryFn(
      "api.admin.patch_threshold_api_v1_admin_usage_thresholds__threshold_id__patch",
      ThresholdRead,
      async () =>
        (
          await api.patch<unknown>(`${getURL("ADMIN_USAGE_THRESHOLD")}/${id}`, body)
        ).data,
    )();
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
