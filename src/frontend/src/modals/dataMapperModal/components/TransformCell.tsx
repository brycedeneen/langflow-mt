import { useState } from "react";
import { InputDef, MappingEntry, SourceRef } from "@/modals/dataMapperModal/types";

export interface TransformCellProps {
  mapping: MappingEntry;
  inputs: InputDef[];
  onMappingChange(next: MappingEntry): void;
}

function SourcePicker({
  source,
  inputs,
  onChange,
}: {
  source: SourceRef | undefined;
  inputs: InputDef[];
  onChange(next: SourceRef): void;
}) {
  const selectedInput = inputs.find((i) => i.alias === source?.input);
  const fields = selectedInput?.schema.fields ?? [];

  function handleInputChange(alias: string) {
    onChange({ input: alias, field: "" });
  }

  function handleFieldChange(field: string) {
    onChange({ input: source?.input ?? "", field });
  }

  return (
    <>
      <select
        value={source?.input ?? ""}
        onChange={(e) => handleInputChange(e.target.value)}
      >
        {!source?.input && <option value="">Select input</option>}
        {inputs.map((i) => (
          <option key={i.alias} value={i.alias}>
            {i.alias}
          </option>
        ))}
      </select>
      <select
        value={source?.field ?? ""}
        onChange={(e) => handleFieldChange(e.target.value)}
      >
        {!source?.field && <option value="">Select field</option>}
        {fields.map((f) => (
          <option key={f.name} value={f.name}>
            {f.name}
          </option>
        ))}
      </select>
    </>
  );
}

function StaticEditor({
  mapping,
  onMappingChange,
}: {
  mapping: MappingEntry;
  onMappingChange(next: MappingEntry): void;
}) {
  const [text, setText] = useState<string>(
    () => JSON.stringify(mapping.config.value ?? ""),
  );
  const [jsonError, setJsonError] = useState(false);

  function handleChange(raw: string) {
    setText(raw);
    try {
      const parsed = JSON.parse(raw);
      setJsonError(false);
      onMappingChange({ ...mapping, config: { ...mapping.config, value: parsed } });
    } catch {
      setJsonError(true);
    }
  }

  return (
    <div>
      <textarea
        value={text}
        rows={2}
        onChange={(e) => handleChange(e.target.value)}
      />
      {jsonError && (
        <span style={{ color: "red", fontSize: "0.75em" }}>Invalid JSON</span>
      )}
    </div>
  );
}

export function TransformCell({ mapping, inputs, onMappingChange }: TransformCellProps) {
  const { transform } = mapping;

  if (transform === "direct") {
    const source = mapping.sources[0];
    return (
      <div className="transform-cell-direct">
        <SourcePicker
          source={source}
          inputs={inputs}
          onChange={(next) =>
            onMappingChange({ ...mapping, sources: [next] })
          }
        />
      </div>
    );
  }

  if (transform === "template") {
    return (
      <textarea
        value={(mapping.config.template as string) ?? ""}
        onChange={(e) =>
          onMappingChange({ ...mapping, config: { template: e.target.value } })
        }
      />
    );
  }

  if (transform === "expression") {
    return (
      <input
        type="text"
        value={(mapping.config.expression as string) ?? ""}
        onChange={(e) =>
          onMappingChange({ ...mapping, config: { expression: e.target.value } })
        }
      />
    );
  }

  if (transform === "static") {
    return <StaticEditor mapping={mapping} onMappingChange={onMappingChange} />;
  }

  if (transform === "variable") {
    return (
      <input
        type="text"
        value={(mapping.config.variable as string) ?? ""}
        onChange={(e) =>
          onMappingChange({ ...mapping, config: { variable: e.target.value } })
        }
      />
    );
  }

  if (transform === "array") {
    return (
      <div className="transform-cell-array">
        {mapping.sources.map((source, index) => (
          <div key={index} className="array-source-row">
            <SourcePicker
              source={source}
              inputs={inputs}
              onChange={(next) => {
                const sources = mapping.sources.map((s, i) =>
                  i === index ? next : s,
                );
                onMappingChange({ ...mapping, sources });
              }}
            />
            <button
              type="button"
              aria-label="Remove source"
              onClick={() =>
                onMappingChange({
                  ...mapping,
                  sources: mapping.sources.filter((_, i) => i !== index),
                })
              }
            >
              −
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            onMappingChange({
              ...mapping,
              sources: [...mapping.sources, { input: "", field: "" }],
            })
          }
        >
          Add source
        </button>
        <label>
          <input
            type="checkbox"
            checked={(mapping.config.skip_missing as boolean) ?? false}
            onChange={(e) =>
              onMappingChange({
                ...mapping,
                config: { ...mapping.config, skip_missing: e.target.checked },
              })
            }
          />
          {" "}Skip missing sources
        </label>
      </div>
    );
  }

  return null;
}
