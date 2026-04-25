import { useUpdateNodeInternals } from "@xyflow/react";
import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";

const useHandleNodeClass = (
  nodeId: string,
  setMyNode?: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void,
) => {
  const setNode = setMyNode ?? useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();

  const handleNodeClass = useCallback(
    (newNodeClass, type?: string) => {
      setNode(nodeId, (oldNode) => {
        const newData: typeof oldNode.data = {
          ...oldNode.data,
          node: newNodeClass,
        };
        if (type) {
          newData.type = type;
        }

        updateNodeInternals(nodeId);

        return { ...oldNode, data: newData };
      });
    },
    [nodeId, setNode, updateNodeInternals],
  );

  return { handleNodeClass };
};

export default useHandleNodeClass;
