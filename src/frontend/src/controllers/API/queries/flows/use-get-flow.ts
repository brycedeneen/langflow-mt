import { useQueryClient } from "@tanstack/react-query";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowSchema } from "@/schemas/api/flows";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFlow {
  id: string;
  public?: boolean;
}

// add types for error handling and success
export const useGetFlow: useMutationFunctionType<undefined, IGetFlow> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();
  const queryClient = useQueryClient();

  const getFlowFn = async (payload: IGetFlow): Promise<FlowType> => {
    const parsed = await validatedQueryFn(
      "api.flows.getFlow",
      FlowSchema,
      async () =>
        (
          await api.get<unknown>(
            `${getURL(payload.public ? "PUBLIC_FLOW" : "FLOWS")}/${payload.id}`,
          )
        ).data,
    )();

    const flowsArrayToProcess = [parsed as FlowType];
    const { flows } = processFlows(flowsArrayToProcess);
    return flows[0];
  };

  const mutation = mutate(["useGetFlow"], getFlowFn, {
    ...options,
    onSettled: (response) => {
      if (response) {
        queryClient.refetchQueries({
          queryKey: [
            "useGetRefreshFlowsQuery",
            { get_all: true, header_flows: true },
          ],
        });
      }
    },
  });

  return mutation;
};
