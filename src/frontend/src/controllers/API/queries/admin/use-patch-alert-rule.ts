import { validatedQueryFn } from "@/lib/validated-fetch";
import { RuleRead } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
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
  z.infer<typeof RuleRead>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    id,
    ...body
  }: Payload): Promise<z.infer<typeof RuleRead>> => {
    const data = await validatedQueryFn(
      "api.admin.patch_rule_api_v1_admin_alert_rules__rule_id__patch",
      RuleRead,
      async () =>
        (await api.patch<unknown>(`${getURL("ADMIN_ALERT_RULE")}/${id}`, body))
          .data,
    )();
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
