import { validatedQueryFn } from "@/lib/validated-fetch";
import { RuleRead } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
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
  z.infer<typeof RuleRead>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    orgId,
    ...body
  }: Payload): Promise<z.infer<typeof RuleRead>> => {
    const data = await validatedQueryFn(
      "api.admin.create_rule_api_v1_admin_orgs__org_id__alert_rules_post",
      RuleRead,
      async () =>
        (
          await api.post<unknown>(
            `${getURL("ADMIN_ALERT_RULES")}/${orgId}/alert-rules`,
            body,
          )
        ).data,
    )();
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
