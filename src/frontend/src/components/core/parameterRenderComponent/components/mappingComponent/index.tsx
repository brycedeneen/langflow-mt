import { useMemo, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { Button } from "@/components/ui/button";
import { DataMapperModal } from "@/modals/dataMapperModal";
import type { MapperConfig } from "@/modals/dataMapperModal/types";
import type { InputProps } from "../../types";

export default function MappingComponent({
  value,
  handleOnNewValue,
  nodeId,
  disabled,
}: InputProps<string>): JSX.Element {
  const [open, setOpen] = useState(false);

  // Parse the current JSON value to show button label and driver chip.
  const parsed: MapperConfig | null = useMemo(() => {
    if (!value) return null;
    try {
      return JSON.parse(value) as MapperConfig;
    } catch {
      return null;
    }
  }, [value]);

  const fieldCount = parsed?.destination_schema?.length ?? 0;
  const driverAlias =
    parsed?.inputs?.[parsed.driver_index ?? 0]?.alias ?? "";
  const buttonLabel =
    fieldCount > 0
      ? `Edit mapping · ${fieldCount} fields`
      : "Configure mapping";

  // Resolve the current flow's ID from the flows-manager store (same pattern as
  // inputFileComponent which also reads currentFlowId this way).
  const flowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Derive connected upstreams from the flow's edge list. Each edge where
  // `target === nodeId` represents an upstream connection; use the source node's
  // display_name as a default alias suggestion for the modal.
  const edges = useFlowStore((state) => state.edges);
  const getNode = useFlowStore((state) => state.getNode);

  const connectedUpstreams = useMemo(() => {
    return edges
      .filter((e) => e.target === nodeId)
      .map((e) => {
        const srcNode = getNode(e.source);
        const alias: string =
          srcNode?.data?.node?.display_name ?? e.source;
        return { alias, vertexId: e.source };
      })
      // Deduplicate by vertexId in case multiple edges come from the same node.
      .filter(
        (u, idx, arr) =>
          arr.findIndex((x) => x.vertexId === u.vertexId) === idx,
      );
  }, [edges, nodeId, getNode]);

  function handleChange(newValue: string) {
    handleOnNewValue({ value: newValue });
  }

  return (
    <>
      <div className="flex flex-col gap-1">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={disabled}
          onClick={() => setOpen(true)}
          data-testid={`mapping-btn-${nodeId}`}
        >
          {buttonLabel}
        </Button>
        {driverAlias && (
          <span className="text-xs text-muted-foreground">
            driver: {driverAlias}
          </span>
        )}
      </div>

      <DataMapperModal
        open={open}
        onClose={() => setOpen(false)}
        value={value ?? ""}
        onChange={handleChange}
        nodeId={nodeId ?? ""}
        flowId={flowId}
        connectedUpstreams={connectedUpstreams}
      />
    </>
  );
}
