import { useEffect } from "react";
import { z } from "zod";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowRead } from "@/schemas/api/_generated";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { useQueryFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetBasicExamplesQuery: useQueryFunctionType<
  undefined,
  FlowType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const data = await validatedQueryFn(
      "api.flows.read_basic_examples_api_v1_flows_basic_examples__get",
      z.array(FlowRead),
      async () =>
        (await api.get<unknown>(`${getURL("FLOWS")}/basic_examples/`)).data,
    )();
    return data as FlowType[];
  };

  const queryResult = query(["useGetBasicExamplesQuery"], responseFn, {
    ...options,
    retry: 3,
  });

  // Sync examples into the flows-manager store outside the queryFn so this
  // hook does not subscribe to the store it mutates. Setter is read via
  // getState().
  useEffect(() => {
    const data = queryResult.data;
    if (!data) return;
    useFlowsManagerStore.getState().setExamples(data);
  }, [queryResult.data]);

  return queryResult;
};
