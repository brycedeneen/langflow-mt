import type { ReactFlowJsonObject } from "@xyflow/react";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

// Mirror of langflow.services.variable.auto_secrets.RefusedSecretField. Server
// echoes one entry per Branch-5 overwrite refusal so we can warn the user that
// their rotation didn't land in Vault (most often: password-manager autofill,
// occasionally: a real rotation that bypassed the "clear field first" path).
type RefusedSecretField = {
  node_id: string;
  field_name: string;
  display_name?: string | null;
};

const useSaveFlow = () => {
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchUpdateFlow();

  const saveFlow = async (flow?: FlowType): Promise<void> => {
    const currentFlow = useFlowStore.getState().currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;
    if (
      customStringify(flow || currentFlow) !== customStringify(currentSavedFlow)
    ) {
      setSaveLoading(true);

      const flowData = currentFlow?.data;
      const nodes = useFlowStore.getState().nodes;
      const edges = useFlowStore.getState().edges;
      const reactFlowInstance = useFlowStore.getState().reactFlowInstance;

      return new Promise<void>((resolve, reject) => {
        if (currentFlow) {
          flow = flow || {
            ...currentFlow,
            data: {
              ...flowData,
              nodes,
              edges,
              viewport: reactFlowInstance?.getViewport() ?? {
                zoom: 1,
                x: 0,
                y: 0,
              },
            },
          };
        }

        if (flow) {
          if (!flow?.data) {
            getFlow(
              { id: flow!.id },
              {
                onSuccess: (flowResponse) => {
                  flow!.data = flowResponse.data as ReactFlowJsonObject<
                    AllNodeType,
                    EdgeType
                  >;
                },
              },
            );
          }

          const {
            id,
            name,
            data,
            description,
            folder_id,
            endpoint_name,
            locked,
          } = flow;
          mutate(
            {
              id,
              name,
              data: data!,
              description,
              folder_id,
              endpoint_name,
              locked,
            },
            {
              onSuccess: (updatedFlow) => {
                const flows = useFlowsManagerStore.getState().flows;
                setSaveLoading(false);

                // Surface autosecret rotation refusals as warning toasts.
                // Severity is "notice" rather than "error": the save itself
                // succeeded — only the secret rotation didn't reach Vault.
                const refused: RefusedSecretField[] =
                  (updatedFlow as { refused_secret_fields?: RefusedSecretField[] })
                    ?.refused_secret_fields ?? [];
                for (const r of refused) {
                  const label = r.display_name || r.field_name;
                  setNoticeData({
                    title:
                      `"${label}" was reset to protect saved credentials. ` +
                      `To update the saved secret, clear the field and save again.`,
                  });
                }

                if (flows) {
                  // updates flow in state
                  setFlows(
                    flows.map((flow) => {
                      if (flow.id === updatedFlow.id) {
                        return updatedFlow;
                      }
                      return flow;
                    }),
                  );
                  setCurrentFlow(updatedFlow);
                  resolve();
                } else {
                  setErrorData({
                    title: "Failed to save flow",
                    list: ["Flows variable undefined"],
                  });
                  reject(new Error("Flows variable undefined"));
                }
              },
              onError: (e) => {
                setErrorData({
                  title: "Failed to save flow",
                  list: [e.message],
                });
                setSaveLoading(false);
                reject(e);
              },
            },
          );
        } else {
          setErrorData({
            title: "Failed to save flow",
            list: ["Flow not found"],
          });
          reject(new Error("Flow not found"));
        }
      });
    }
  };

  return saveFlow;
};

export default useSaveFlow;
