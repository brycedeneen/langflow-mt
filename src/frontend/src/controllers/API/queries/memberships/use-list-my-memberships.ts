import { keepPreviousData } from "@tanstack/react-query";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { MyMembership } from "@/schemas/api/_generated";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const MEMBERSHIPS_QUERY_KEY = ["memberships", "me"] as const;

export function useListMyMemberships() {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.memberships.list_my_memberships_api_v1_memberships_me_get",
    z.array(MyMembership),
    async () =>
      (await api.get<unknown>(getURL("MEMBERSHIPS") + "/me")).data,
  );
  return query([...MEMBERSHIPS_QUERY_KEY], fn, {
    placeholderData: keepPreviousData,
  });
}
