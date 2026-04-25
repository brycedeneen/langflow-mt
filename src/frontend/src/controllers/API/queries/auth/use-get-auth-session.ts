import type { UseQueryResult } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import {
  SessionResponseSchema,
  type SessionResponse,
} from "@/schemas/app/internal/auth";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type { SessionResponse };

export const useGetAuthSession: useQueryFunctionType<
  undefined,
  SessionResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getAuthSessionFn = validatedQueryFn(
    "api.auth.getSession",
    SessionResponseSchema,
    async () => {
      try {
        const response = await api.get<unknown>(getURL("SESSION"));
        return response.data;
      } catch (error) {
        // If the endpoint fails, return unauthenticated
        console.error("Session validation error:", error);
        return { authenticated: false };
      }
    },
  );

  const queryResult: UseQueryResult<SessionResponse> = query(
    ["useGetAuthSession"],
    getAuthSessionFn,
    {
      refetchOnWindowFocus: false,
      retry: false,
      ...options,
    },
  );

  return queryResult;
};
