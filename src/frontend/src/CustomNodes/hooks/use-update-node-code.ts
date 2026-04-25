import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "../../types/api";
import { updateHiddenOutputs } from "../helpers/update-hidden-outputs";

const useUpdateNodeCode = (
  dataId: string,
  dataNode: APIClassType, // Define YourNodeType according to your data structure
  setNode: (id: string, callback: (oldNode) => any) => void,
  updateNodeInternals: (id: string) => void,
) => {
  const setComponentsToUpdate = useFlowStore(
    (state) => state.setComponentsToUpdate,
  );

  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string, type: string) => {
      setNode(dataId, (oldNode) => {
        const newData = {
          ...oldNode.data,
          node: { ...newNodeClass, edited: false },
          description: newNodeClass.description ?? dataNode.description,
          display_name: newNodeClass.display_name ?? dataNode.display_name,
        };
        if (type) {
          newData.type = type;
        }

        newData.node.template[name].value = code;

        const outputs = dataNode.outputs;
        const updatedOutputs = newNodeClass.outputs;

        newData.node!.outputs = updateHiddenOutputs(
          outputs!,
          updatedOutputs!,
        );

        return { ...oldNode, data: newData };
      });

      setComponentsToUpdate((old) =>
        old.filter((component) => component.id !== dataId),
      );
      updateNodeInternals(dataId);
    },
    [dataId, dataNode, setNode, updateNodeInternals, setComponentsToUpdate],
  );

  return updateNodeCode;
};

export default useUpdateNodeCode;
