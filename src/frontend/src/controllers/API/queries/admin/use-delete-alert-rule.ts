import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteAlertRule: useMutationFunctionType<
  undefined,
  { id: string },
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ id }: { id: string }): Promise<void> => {
    await validatedQueryFn(
      "api.admin.delete_rule_api_v1_admin_alert_rules__rule_id__delete",
      z.unknown(),
      async () =>
        (await api.delete<unknown>(`${getURL("ADMIN_ALERT_RULE")}/${id}`)).data,
    )();
  };
  return mutate(["useDeleteAlertRule"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "alert-rules"] });
      options?.onSuccess?.(...args);
    },
  });
};
