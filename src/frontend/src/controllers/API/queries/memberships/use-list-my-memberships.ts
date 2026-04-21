import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MyMembership } from "@/types/template";

export const MEMBERSHIPS_QUERY_KEY = ["memberships", "me"] as const;

export function useListMyMemberships() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<MyMembership[]> => {
    const res = await api.get<MyMembership[]>(getURL("MEMBERSHIPS") + "/me");
    return res.data;
  };
  return query([...MEMBERSHIPS_QUERY_KEY], fn, {
    placeholderData: keepPreviousData,
  });
}
