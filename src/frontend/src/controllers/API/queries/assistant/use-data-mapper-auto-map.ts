import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface DataMapperAutoMapInput {
  driver: { alias: string; fields: unknown[]; sample?: unknown };
  destinations: unknown[];
  lookups?: unknown[];
}

export interface AutoMapMutationArgs {
  inputPayload: DataMapperAutoMapInput;
  signal?: AbortSignal;
}

export const useDataMapperAutoMapMutation = () =>
  useMutation({
    mutationFn: async ({ inputPayload, signal }: AutoMapMutationArgs) =>
      api.post(
        getURL("RUN_SESSION", { assistantFlowId: "DataMapperAutoMap" }),
        {
          input_value: JSON.stringify(inputPayload),
          input_type: "chat",
          output_type: "chat",
          stream: true,
        },
        { signal },
      ),
  });
