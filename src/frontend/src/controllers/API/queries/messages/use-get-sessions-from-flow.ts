import { keepPreviousData } from "@tanstack/react-query";
import { z } from "zod";
import useFlowStore from "@/stores/flowStore";
import { validatedQueryFn } from "@/lib/validated-fetch";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface SessionsQueryParams {
  id?: string;
}

interface SessionsResponse {
  sessions: string[];
}

export const useGetSessionsFromFlowQuery: useQueryFunctionType<
  SessionsQueryParams,
  SessionsResponse
> = ({ id }, options) => {
  const { query } = UseRequestProcessor();

  const getSessionsFn = async (id?: string) => {
    const isPlaygroundPage = useFlowStore.getState().playgroundPage;
    const config = {};
    if (id) {
      config["params"] = { flow_id: id };
    }

    if (!isPlaygroundPage) {
      const sessions = await validatedQueryFn(
        "api.monitor.get_message_sessions_api_v1_monitor_messages_sessions_get",
        z.array(z.string()),
        async () =>
          (
            await api.get<unknown>(`${getURL("MESSAGES")}/sessions`, config)
          ).data,
      )();
      return { data: sessions };
    } else {
      // For playground mode, get sessions from sessionStorage
      const data = JSON.parse(window.sessionStorage.getItem(id ?? "") || "[]");
      // Extract unique session IDs from stored messages
      const sessionIdsSet = new Set(
        data.map((msg: any) => msg.session_id).filter(Boolean),
      );
      const sessionIds = Array.from(sessionIdsSet);

      // Always include the flow ID as the default session if it's not already present
      if (id && !sessionIds.includes(id)) {
        sessionIds.unshift(id);
      }

      return {
        data: sessionIds,
      };
    }
  };

  const responseFn = async () => {
    const response = await getSessionsFn(id);
    return { sessions: response.data };
  };

  const queryResult = query(
    ["useGetSessionsFromFlowQuery", { id }],
    responseFn,
    {
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
