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
  const setExamples = useFlowsManagerStore((state) => state.setExamples);

  const responseFn = async () => {
    const data = await validatedQueryFn(
      "api.flows.read_basic_examples_api_v1_flows_basic_examples__get",
      z.array(FlowRead),
      async () =>
        (await api.get<unknown>(`${getURL("FLOWS")}/basic_examples/`)).data,
    )();
    if (data) {
      setExamples(data as FlowType[]);
    }
    return data as FlowType[];
  };

  const queryResult = query(["useGetBasicExamplesQuery"], responseFn, {
    ...options,
    retry: 3,
  });

  return queryResult;
};
