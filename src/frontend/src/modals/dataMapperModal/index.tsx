import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import BaseModal from "@/modals/baseModal";
import { InputsPanel } from "@/modals/dataMapperModal/components/InputsPanel";
import { DestinationTable } from "@/modals/dataMapperModal/components/DestinationTable";
import { useVertexBuildShapes } from "@/modals/dataMapperModal/hooks/useVertexBuildShapes";
import {
  EMPTY_MAPPER_CONFIG,
  type FieldDef,
  type MapperConfig,
} from "@/modals/dataMapperModal/types";
import { usePostValidateMappingConfig } from "@/controllers/API/queries/utils/use-post-validate-mapping-config";
import type { MappingConfigError } from "@/controllers/API/queries/utils/use-post-validate-mapping-config";

export interface DataMapperModalProps {
  open: boolean;
  onClose(): void;
  value: string;
  onChange(newValue: string): void;
  nodeId: string;
  flowId: string;
  connectedUpstreams: { alias: string; vertexId: string }[];
  suggestionsSlot?: React.ReactNode;
}

function parseConfig(value: string): MapperConfig {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object") return parsed as MapperConfig;
  } catch {
    // fall through
  }
  return { ...EMPTY_MAPPER_CONFIG };
}

function seedInputs(
  config: MapperConfig,
  upstreams: { alias: string; vertexId: string }[],
): MapperConfig {
  if (config.inputs.length > 0 || upstreams.length === 0) return config;

  const inputs = upstreams.map((u, idx) => ({
    alias: u.alias,
    schema_source: "autodetect" as const,
    schema: { fields: [] as FieldDef[] },
    sample: null,
    jsonschema: null,
    join:
      idx === 0
        ? null
        : { on: [{ driver_field: "", lookup_field: "" }] },
  }));

  return {
    ...config,
    driver_index: 0,
    inputs,
  };
}

export function DataMapperModal({
  open,
  onClose,
  value,
  onChange,
  flowId,
  connectedUpstreams,
  suggestionsSlot,
}: DataMapperModalProps) {
  const [config, setConfig] = useState<MapperConfig>(() => parseConfig(value));
  const [validationErrors, setValidationErrors] = useState<MappingConfigError[]>([]);

  const { shapes, isPending: shapesPending } = useVertexBuildShapes({
    flowId,
    upstreams: connectedUpstreams,
  });

  // Convert shapes to the Record<alias, FieldDef[] | null> expected by InputsPanel
  const upstreamFields: Record<string, FieldDef[] | null> = React.useMemo(() => {
    const result: Record<string, FieldDef[] | null> = {};
    for (const shape of shapes) {
      result[shape.alias] = shape.fields;
    }
    return result;
  }, [shapes]);

  // On open (or when upstream count changes), re-parse the value and seed inputs if needed
  useEffect(() => {
    if (!open) return;
    const parsed = parseConfig(value);
    const seeded = seedInputs(parsed, connectedUpstreams);
    setConfig(seeded);
    setValidationErrors([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, connectedUpstreams.length]);

  const { mutate: validateConfig, isPending: saving } = usePostValidateMappingConfig();

  function handleSave() {
    validateConfig(config as unknown as Record<string, unknown>, {
      onSuccess: (response) => {
        if (response.errors.length > 0) {
          setValidationErrors(response.errors);
        } else {
          setValidationErrors([]);
          onChange(JSON.stringify(config));
          onClose();
        }
      },
      onError: () => {
        // Network/unexpected errors — keep modal open; errors already normalized by hook
      },
    });
  }

  function handleCancel() {
    onClose();
  }

  const hasErrors = validationErrors.length > 0;

  return (
    <BaseModal
      open={open}
      setOpen={(next) => { if (!next) handleCancel(); }}
      size="x-large"
      onEscapeKeyDown={() => handleCancel()}
    >
      <BaseModal.Header description="">
        <div className="flex w-full items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={handleCancel}
            >
              Cancel
            </Button>
            <span className="text-base font-semibold">Data Mapper</span>
          </div>
          {suggestionsSlot && (
            <div className="suggestions-slot">{suggestionsSlot}</div>
          )}
        </div>
      </BaseModal.Header>

      <BaseModal.Content className="gap-4 overflow-auto p-4">
        {/* Validation error banner */}
        {hasErrors && (
          <div
            role="alert"
            className="rounded border border-destructive bg-destructive/10 px-4 py-2 text-sm text-destructive"
          >
            <strong>Validation errors:</strong>{" "}
            {validationErrors.length} issue
            {validationErrors.length !== 1 ? "s" : ""} found. Fix them below and save again.
          </div>
        )}

        {/* Inputs panel */}
        <section>
          <InputsPanel
            config={config}
            upstreamFields={upstreamFields}
            onConfigChange={setConfig}
          />
        </section>

        {/* Destination table */}
        <section>
          <DestinationTable
            config={config}
            errors={validationErrors}
            onConfigChange={setConfig}
          />
        </section>
      </BaseModal.Content>

      <BaseModal.Footer
        submit={{
          label: "Save",
          loading: saving || shapesPending,
          disabled: saving,
          dataTestId: "data-mapper-save-btn",
          onClick: handleSave,
        }}
      />
    </BaseModal>
  );
}

export default DataMapperModal;
