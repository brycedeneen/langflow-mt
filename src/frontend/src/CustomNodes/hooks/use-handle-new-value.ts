import { useUpdateNodeInternals } from "@xyflow/react";
import { debounce } from "lodash";
import { useCallback, useMemo, useRef } from "react";
import { DEBOUNCE_FIELD_LIST } from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType, InputFieldType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { mutateTemplate } from "../helpers/mutate-template";
import { applyTemplateChange } from "./applyTemplateChange";

const DEBOUNCE_TIME_1_SECOND = 1000;


export type handleOnNewValueType = (
  changes: Partial<InputFieldType>,
  options?: {
    skipSnapshot?: boolean;
    setNodeClass?: (node: APIClassType) => void;
  },
) => void;

const useHandleOnNewValue = ({
  node,
  nodeId,
  name,
  setNode: setNodeExternal,
}: {
  node: APIClassType;
  nodeId: string;
  name: string;
  setNode?: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void;
}) => {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = setNodeExternal ?? useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Memoize the postTemplateValue hook to prevent unnecessary re-renders
  const postTemplateValue = usePostTemplateValue(
    useMemo(
      () => ({
        parameterId: name,
        nodeId,
        node,
        tool_mode: node.tool_mode ?? false,
      }),
      [name, nodeId, node, node.tool_mode],
    ),
  );

  // Memoize the node update function
  const updateNodeState = useCallback(
    (newNode: APIClassType) => {
      setNode(
        nodeId,
        (oldNode) => ({
          ...oldNode,
          data: { ...oldNode.data, node: newNode },
        }),
        true,
        () => {
          updateNodeInternals(nodeId);
        },
      );
    },
    [nodeId, setNode, updateNodeInternals],
  );

  const debouncedMutateRef = useRef<any>(null);

  // Read `node` from a ref so the handler always sees the latest template at
  // call time. Previously the handler captured `node` in a useCallback closure;
  // sibling-field memo skips (areInputPropsEqual ignores `handleOnNewValue`)
  // meant a sibling could keep firing an OLD closure whose template predated
  // edits to *other* fields, and applyTemplateChange would then revert those
  // other fields when the sibling updated. See ADP Auth paste-then-blank repro.
  const nodeRef = useRef(node);
  nodeRef.current = node;

  const handleOnNewValue: handleOnNewValueType = useCallback(
    async (changes, options?) => {
      track("Component Edited", { nodeId });

      if (nodeId.toLowerCase().includes("astra") && name === "database_name") {
        track("Database Selected", { nodeId, databaseName: changes.value });
      }

      const currentNode = nodeRef.current;

      if (!currentNode.template) {
        setErrorData({ title: "Template not found in the component" });
        return;
      }

      const parameter = currentNode.template[name];

      if (!parameter) {
        setErrorData({ title: "Parameter not found in the template" });
        return;
      }

      const shouldDebounce = DEBOUNCE_FIELD_LIST.includes(
        (parameter?._input_type as string) ?? "",
      );

      if (!options?.skipSnapshot) takeSnapshot();

      const newNode = applyTemplateChange(currentNode, name, changes);

      const shouldUpdate = newNode.template[name].real_time_refresh;

      const setNodeClass = (newNodeClass: APIClassType) => {
        options?.setNodeClass?.(newNodeClass);
        updateNodeState(newNodeClass);
      };

      if (shouldUpdate && changes.value !== undefined) {
        if (!debouncedMutateRef.current) {
          debouncedMutateRef.current = debounce(
            async (
              value,
              node,
              setNodeClassFn,
              postTemplateFn,
              setErrorDataFn,
            ) => {
              await mutateTemplate(
                value,
                nodeId,
                node,
                setNodeClassFn,
                postTemplateFn,
                setErrorDataFn,
              );
            },
            shouldDebounce ? DEBOUNCE_TIME_1_SECOND : 0,
          );
        }
        debouncedMutateRef.current(
          changes.value,
          newNode,
          setNodeClass,
          postTemplateValue,
          setErrorData,
        );
      }

      updateNodeState(newNode);
    },
    [
      nodeId,
      name,
      takeSnapshot,
      postTemplateValue,
      setErrorData,
      updateNodeState,
    ],
  );

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
