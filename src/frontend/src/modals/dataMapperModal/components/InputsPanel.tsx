import { FieldDef, InputDef, MapperConfig } from "@/modals/dataMapperModal/types";
import {
  addJoinKey,
  removeJoinKey,
  setDriverIndex,
  setJoinKey,
} from "@/modals/dataMapperModal/util/configBuilder";
import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";
import { JoinKeyEditor } from "@/modals/dataMapperModal/components/JoinKeyEditor";
import { SchemaSourceTabs } from "@/modals/dataMapperModal/components/SchemaSourceTabs";

export interface InputsPanelProps {
  config: MapperConfig;
  upstreamFields: Record<string, FieldDef[] | null>; // keyed by input alias; null = not autodetected
  onConfigChange(next: MapperConfig): void;
}

function updateInputAt(
  config: MapperConfig,
  idx: number,
  partial: Partial<InputDef>,
): MapperConfig {
  const next = { ...config, inputs: [...config.inputs] };
  next.inputs[idx] = { ...next.inputs[idx], ...partial };
  return next;
}

export function InputsPanel({
  config,
  upstreamFields,
  onConfigChange,
}: InputsPanelProps) {
  const driverInput = config.inputs[config.driver_index];
  const driverFields = driverInput?.schema.fields ?? [];

  return (
    <div className="inputs-panel" style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
      {config.inputs.map((input, idx) => {
        const isDriver = idx === config.driver_index;

        return (
          <div
            key={input.alias}
            className="input-card"
            style={{ border: "1px solid #ccc", borderRadius: 4, padding: "0.75rem", minWidth: 260 }}
          >
            {/* Driver toggle + Alias */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                <input
                  type="radio"
                  name="driver"
                  checked={isDriver}
                  onChange={() => onConfigChange(setDriverIndex(config, idx))}
                />
                Driver
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                Alias:
                <input
                  type="text"
                  value={input.alias}
                  onChange={(e) =>
                    onConfigChange(
                      updateInputAt(config, idx, { alias: e.target.value }),
                    )
                  }
                  style={{ marginLeft: "0.25rem" }}
                />
              </label>
            </div>

            {/* Schema source tabs */}
            <SchemaSourceTabs
              source={input.schema_source}
              fields={upstreamFields[input.alias] ?? input.schema.fields}
              onSourceChange={(s) =>
                onConfigChange(updateInputAt(config, idx, { schema_source: s }))
              }
              onSampleChange={(sample) => {
                const inferredFields = inferSampleFields(sample);
                onConfigChange(
                  updateInputAt(config, idx, {
                    sample: sample as InputDef["sample"],
                    schema: { fields: inferredFields },
                  }),
                );
              }}
              onJsonSchemaChange={(schema) =>
                onConfigChange(updateInputAt(config, idx, { jsonschema: schema }))
              }
            />

            {/* Join key editor — only for non-driver inputs */}
            {!isDriver && (
              <JoinKeyEditor
                keys={input.join?.on ?? []}
                driverFields={driverFields}
                lookupFields={input.schema.fields}
                onKeysChange={(next) => {
                  // Reflect the new keys array back into the config via immutable helpers.
                  // We rebuild the full join.on list by applying add/set/remove in terms
                  // of the delta, but since onKeysChange provides the complete next array,
                  // use a single updateInputAt with a reconstructed join object.
                  onConfigChange(
                    updateInputAt(config, idx, {
                      join: { on: next },
                    }),
                  );
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
