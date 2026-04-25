import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteUsageThreshold: useMutationFunctionType<
  undefined,
  { id: string },
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ id }: { id: string }): Promise<void> => {
    await validatedQueryFn(
      "api.admin.delete_threshold_api_v1_admin_usage_thresholds__threshold_id__delete",
      z.unknown(),
      async () =>
        (
          await api.delete<unknown>(`${getURL("ADMIN_USAGE_THRESHOLD")}/${id}`)
        ).data,
    )();
  };
  return mutate(["useDeleteUsageThreshold"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "usage-thresholds"] });
      options?.onSuccess?.(...args);
    },
  });
};
