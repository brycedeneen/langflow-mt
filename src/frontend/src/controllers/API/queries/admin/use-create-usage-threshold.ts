import { validatedQueryFn } from "@/lib/validated-fetch";
import { ThresholdRead } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
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
  z.infer<typeof ThresholdRead>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    orgId,
    ...body
  }: Payload): Promise<z.infer<typeof ThresholdRead>> => {
    const data = await validatedQueryFn(
      "api.admin.create_threshold_api_v1_admin_orgs__org_id__usage_thresholds_post",
      ThresholdRead,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("ADMIN_USAGE_THRESHOLDS")}/${orgId}/usage/thresholds`,
            body,
          )
        ).data,
    )();
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
