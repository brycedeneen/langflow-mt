import { memo, useMemo, useState } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import { useShallow } from "zustand/react/shallow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { Button } from "@/components/ui/button";
import { DataMapperModal } from "@/modals/dataMapperModal";
import { MappingSuggestions } from "@/modals/dataMapperModal/components/MappingSuggestions";
import { useMappingSuggestions } from "@/modals/dataMapperModal/hooks/useMappingSuggestions";
import { applyMappingSuggestion } from "@/modals/dataMapperModal/util/applyMappingSuggestion";
import { EMPTY_MAPPER_CONFIG, type MapperConfig } from "@/modals/dataMapperModal/types";
import type { InputProps } from "../../types";

function MappingComponent({
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
  // `target === nodeId` represents an upstream connection; use the source
  // node's display_name as a default alias suggestion for the modal.
  //
  // We only resolve these when the modal is about to open — reading edges on
  // every render subscribes to the flowStore which re-renders this component
  // on every flowPool update (the build endpoint mutates it), which would
  // re-mount the modal and re-fire the monitor/builds query in a loop.
  const upstreamSeedKey = useFlowStore(
    useShallow((state) =>
      state.edges
        .filter((e) => e.target === nodeId)
        .map((e) => e.source)
        .sort()
        .join(","),
    ),
  );

  const connectedUpstreams = useMemo(() => {
    if (!upstreamSeedKey) return [];
    const sourceIds = upstreamSeedKey.split(",").filter(Boolean);
    const { getNode } = useFlowStore.getState();
    const seen = new Set<string>();
    const result: { alias: string; vertexId: string }[] = [];
    for (const source of sourceIds) {
      if (seen.has(source)) continue;
      seen.add(source);
      const srcNode = getNode(source);
      const alias: string =
        srcNode?.data?.node?.display_name ?? source;
      result.push({ alias, vertexId: source });
    }
    return result;
  }, [upstreamSeedKey]);

  function handleChange(newValue: string) {
    handleOnNewValue({ value: newValue });
  }

  // Parse the value into a MapperConfig usable by the suggestions hook.
  const parsedConfig: MapperConfig = useMemo(() => {
    if (!value) return EMPTY_MAPPER_CONFIG;
    try {
      return JSON.parse(value) as MapperConfig;
    } catch {
      return EMPTY_MAPPER_CONFIG;
    }
  }, [value]);

  const suggestions = useMappingSuggestions({ config: parsedConfig });
  const [showPending, setShowPending] = useState(true);

  const allCustomized = useMemo(
    () =>
      parsedConfig.destination_schema.length > 0 &&
      parsedConfig.destination_schema.every((d) => {
        const m = parsedConfig.mappings.find((x) => x.destination === d.name);
        if (!m) return false;
        return !(
          m.transform === "direct" &&
          m.sources.length === 0 &&
          Object.keys(m.config).length === 0
        );
      }),
    [parsedConfig],
  );

  const acceptSuggestion = (destination: string) => {
    const entry = suggestions.entries.find((e) => e.destination === destination);
    if (!entry) return;
    const next = applyMappingSuggestion(parsedConfig, entry);
    handleChange(JSON.stringify(next));
    const remaining = suggestions.entries.filter(
      (e) => e.destination !== destination,
    );
    suggestions.setEntries(remaining);
    if (remaining.length === 0) suggestions.reset();
  };

  const rejectSuggestion = (destination: string) => {
    const remaining = suggestions.entries.filter(
      (e) => e.destination !== destination,
    );
    suggestions.setEntries(remaining);
    if (remaining.length === 0) suggestions.reset();
  };

  const applyAllSuggestions = () => {
    let next = parsedConfig;
    for (const entry of suggestions.entries) {
      next = applyMappingSuggestion(next, entry);
    }
    handleChange(JSON.stringify(next));
    suggestions.reset();
  };

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

      {open && (
        <DataMapperModal
          open={open}
          onClose={() => setOpen(false)}
          value={value ?? ""}
          onChange={handleChange}
          nodeId={nodeId ?? ""}
          flowId={flowId}
          connectedUpstreams={connectedUpstreams}
          suggestionsSlot={
            <MappingSuggestions
              state={suggestions.state}
              error={suggestions.error}
              pendingCount={suggestions.entries.length}
              showPending={showPending}
              allDestinationsCustomized={allCustomized}
              onSuggest={suggestions.run}
              onCancel={suggestions.cancel}
              onApplyAll={applyAllSuggestions}
              onTogglePending={setShowPending}
              onRetry={suggestions.run}
            />
          }
          pendingSuggestions={suggestions.entries}
          showPendingSuggestions={showPending}
          onAcceptSuggestion={acceptSuggestion}
          onRejectSuggestion={rejectSuggestion}
        />
      )}
    </>
  );
}

export default memo(MappingComponent, areInputPropsEqual);
