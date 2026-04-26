import type { CustomCellRendererProps } from "ag-grid-react";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import type { APIClassType } from "@/types/api";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import VisibilityToggleButton from "./VisibilityToggleButton";

export default function TableAdvancedToggleCellRender({
  value: { nodeId, parameterId, isTweaks },
}: CustomCellRendererProps) {
  const edges = useFlowStore((state) => state.edges);
  const node = isTweaks
    ? useTweaksStore((state) => state.getNode(nodeId))
    : useFlowStore((state) => state.getNode(nodeId));
  const parameter = node?.data?.node?.template?.[parameterId];

  const setNode = useTweaksStore((state) => state.setNode);

  const disabled = isTargetHandleConnected(
    edges,
    parameterId,
    parameter,
    nodeId,
  );

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data.node as APIClassType,
    nodeId,
    name: parameterId,
    setNode: isTweaks ? setNode : undefined,
  });

  return (
    parameter && (
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <div className="flex h-full w-full items-center justify-center">
            <VisibilityToggleButton
              id={"show" + parameterId}
              checked={!parameter.advanced}
              disabled={disabled}
              onToggle={() => handleOnNewValue({ advanced: !parameter.advanced })}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
          avoidCollisions={false}
          sticky="always"
        >
          {disabled
            ? isTweaks
              ? "Cannot enable input of connected handles"
              : "Cannot change visibility of connected handles"
            : isTweaks
              ? "Toggle input of the field in the API"
              : "Change visibility of the field"}
        </TooltipContent>
      </Tooltip>
    )
  );
}
