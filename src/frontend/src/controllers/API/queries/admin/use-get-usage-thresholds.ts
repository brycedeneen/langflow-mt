import { validatedQueryFn } from "@/lib/validated-fetch";
import { ThresholdListResponse } from "@/schemas/api/_generated";
import type { useQueryFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { orgId: string };

export const useGetUsageThresholds: useQueryFunctionType<
  Params,
  z.infer<typeof ThresholdListResponse>
> = ({ orgId }, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.admin.list_thresholds_api_v1_admin_orgs__org_id__usage_thresholds_get",
    ThresholdListResponse,
    async () =>
      (
        await api.get<unknown>(
          `${getURL("ADMIN_USAGE_THRESHOLDS")}/${orgId}/usage/thresholds`,
        )
      ).data,
  );
  return query(["admin", "usage-thresholds", orgId], fn, { ...options });
};
