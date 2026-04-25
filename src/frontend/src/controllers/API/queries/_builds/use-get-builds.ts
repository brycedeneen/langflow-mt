import { keepPreviousData } from "@tanstack/react-query";
import type { AxiosResponse } from "axios";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import useFlowStore from "@/stores/flowStore";
import type { FlowPoolType } from "@/types/zustand/flow";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BuildsQueryParams {
  flowId?: string;
}

export const useGetBuildsQuery: useQueryFunctionType<
  BuildsQueryParams,
  AxiosResponse<{ vertex_builds: FlowPoolType }>
> = (params) => {
  const { query } = UseRequestProcessor();
  const { id: routeFlowId } = useParams();

  const responseFn = async () => {
    const config = {};
    config["params"] = {
      flow_id:
        !params.flowId || params.flowId === "" ? routeFlowId : params.flowId,
    };

    return api.get<{ vertex_builds: FlowPoolType }>(
      `${getURL("BUILDS")}`,
      config,
    );
  };

  const queryResult = query(
    ["useGetBuildsQuery", { key: params.flowId }],
    responseFn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      retry: 0,
      retryDelay: 0,
    },
  );

  // Sync builds into flowStore outside the queryFn so this hook does not
  // mutate the store it would otherwise be subscribed to (render-loop hazard).
  // Read currentFlow via getState() to avoid subscribing here.
  useEffect(() => {
    const data = queryResult.data?.data;
    if (!data) return;
    if (useFlowStore.getState().currentFlow) {
      useFlowStore.getState().setFlowPool(data.vertex_builds);
    }
  }, [queryResult.data]);

  return queryResult;
};
