import { useState } from "react";
import {
  DestFieldDef,
  FieldType,
  MapperConfig,
  MappingEntry,
  TransformType,
} from "@/modals/dataMapperModal/types";
import {
  addDestinationField,
  removeDestinationField,
  setTransformForDestination,
} from "@/modals/dataMapperModal/util/configBuilder";
import { TransformCell } from "@/modals/dataMapperModal/components/TransformCell";
import type { MappingConfigError } from "@/controllers/API/queries/utils/use-post-validate-mapping-config";

export interface DestinationTableProps {
  config: MapperConfig;
  errors?: MappingConfigError[];
  onConfigChange(next: MapperConfig): void;
}

const FIELD_TYPES: FieldType[] = [
  "str", "int", "float", "bool", "list", "dict", "date", "datetime",
];

const TRANSFORM_TYPES: TransformType[] = [
  "direct", "template", "expression", "static", "variable", "array",
];

/** Update a dest field in-place; mirrors a name rename into the matching MappingEntry. */
function updateDestAt(
  config: MapperConfig,
  idx: number,
  partial: Partial<DestFieldDef>,
): MapperConfig {
  const oldName = config.destination_schema[idx].name;
  const newDest: DestFieldDef = { ...config.destination_schema[idx], ...partial };

  return {
    ...config,
    destination_schema: config.destination_schema.map((d, i) =>
      i === idx ? newDest : d,
    ),
    mappings: config.mappings.map((m) =>
      m.destination === oldName && oldName !== newDest.name
        ? { ...m, destination: newDest.name }
        : m,
    ),
  };
}

/** Splice an updated MappingEntry back into mappings by destination name. */
function updateMappingEntry(config: MapperConfig, entry: MappingEntry): MapperConfig {
  return {
    ...config,
    mappings: config.mappings.map((m) =>
      m.destination === entry.destination ? entry : m,
    ),
  };
}

/** Return the first error whose path or message references this dest row. */
function rowHasError(
  errors: MappingConfigError[],
  dest: DestFieldDef,
  idx: number,
): MappingConfigError | undefined {
  return errors.find(
    (e) =>
      (e.path[0] === "mappings" && e.path[1] === idx) ||
      (e.path[0] === "destination_schema" && e.path[1] === idx) ||
      e.message.includes(dest.name),
  );
}

// ── Small default-value JSON input ──────────────────────────────────────────

function DefaultEditor({ value, onChange }: { value: unknown; onChange(v: unknown): void }) {
  const [text, setText] = useState(() =>
    value === null || value === undefined ? "" : JSON.stringify(value),
  );
  const [bad, setBad] = useState(false);

  function handleChange(raw: string) {
    setText(raw);
    if (!raw.trim()) { setBad(false); onChange(null); return; }
    try { onChange(JSON.parse(raw)); setBad(false); }
    catch { setBad(true); }
  }

  return (
    <input
      type="text"
      value={text}
      onChange={(e) => handleChange(e.target.value)}
      placeholder="null"
      style={{ width: 90, fontSize: "0.8em", border: bad ? "1px solid red" : undefined }}
    />
  );
}

// ── Add-field inline form ────────────────────────────────────────────────────

function AddFieldForm({ onAdd, onCancel }: { onAdd(f: DestFieldDef): void; onCancel(): void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState<FieldType>("str");
  const [required, setRequired] = useState(false);
  const [defaultVal, setDefaultVal] = useState("");
  const [nameErr, setNameErr] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) { setNameErr(true); return; }
    let parsed: unknown = null;
    if (defaultVal.trim()) {
      try { parsed = JSON.parse(defaultVal); } catch { parsed = defaultVal; }
    }
    onAdd({ name: trimmed, type, required, default: parsed });
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "0.5rem",
        marginTop: "0.5rem", padding: "0.5rem", background: "#f8f8f8",
        borderRadius: 4, border: "1px solid #e0e0e0" }}
    >
      <div>
        <label style={{ fontSize: "0.75em", display: "block" }}>Name *</label>
        <input autoFocus type="text" value={name} placeholder="field_name"
          style={{ width: 140, border: nameErr ? "1px solid red" : undefined }}
          onChange={(e) => { setName(e.target.value); setNameErr(false); }} />
      </div>
      <div>
        <label style={{ fontSize: "0.75em", display: "block" }}>Type</label>
        <select value={type} onChange={(e) => setType(e.target.value as FieldType)}>
          {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div>
        <label style={{ fontSize: "0.75em", display: "block" }}>Default (JSON)</label>
        <input type="text" value={defaultVal} placeholder="null" style={{ width: 100 }}
          onChange={(e) => setDefaultVal(e.target.value)} />
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85em" }}>
        <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
        Required
      </label>
      <button type="submit" style={{ padding: "0.25rem 0.75rem" }}>Add</button>
      <button type="button" onClick={onCancel} style={{ padding: "0.25rem 0.75rem" }}>Cancel</button>
    </form>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function DestinationTable({ config, errors = [], onConfigChange }: DestinationTableProps) {
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <div className="destination-table" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9em" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e0e0e0", textAlign: "left" }}>
            {["Destination field", "Type", "Required", "Transform", "Source / Config", "Default", "Actions"]
              .map((h) => <th key={h} style={{ padding: "0.4rem 0.5rem" }}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {config.destination_schema.length === 0 && (
            <tr>
              <td colSpan={7} style={{ padding: "1rem", textAlign: "center", color: "#888", fontStyle: "italic" }}>
                No destination fields yet — add one below.
              </td>
            </tr>
          )}

          {config.destination_schema.map((dest, idx) => {
            const mapping = config.mappings.find((m) => m.destination === dest.name);
            const rowError = rowHasError(errors, dest, idx);

            return (
              <tr
                key={`${dest.name}-${idx}`}
                style={{
                  borderLeft: rowError ? "3px solid red" : undefined,
                  borderBottom: "1px solid #f0f0f0",
                  background: rowError ? "#fff5f5" : undefined,
                }}
              >
                {/* Destination field: name input + type pill + inline error */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  <input
                    type="text"
                    value={dest.name}
                    style={{ width: 130, fontWeight: 500, display: "block" }}
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { name: e.target.value }))}
                  />
                  <span style={{ fontSize: "0.7em", background: "#e8e8f4", borderRadius: 3,
                    padding: "1px 5px", color: "#444" }}>{dest.type}</span>
                  {rowError && (
                    <span style={{ display: "block", color: "red", fontSize: "0.75em", marginTop: 2 }}>
                      {rowError.message}
                    </span>
                  )}
                </td>

                {/* Type */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  <select value={dest.type}
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { type: e.target.value as FieldType }))}>
                    {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>

                {/* Required */}
                <td style={{ padding: "0.4rem 0.5rem", textAlign: "center" }}>
                  <input type="checkbox" checked={dest.required}
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { required: e.target.checked }))} />
                </td>

                {/* Transform */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  <select value={mapping?.transform ?? "direct"}
                    onChange={(e) =>
                      onConfigChange(setTransformForDestination(config, dest.name, e.target.value as TransformType))}>
                    {TRANSFORM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>

                {/* Source / Config */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  {mapping
                    ? <TransformCell mapping={mapping} inputs={config.inputs}
                        onMappingChange={(entry) => onConfigChange(updateMappingEntry(config, entry))} />
                    : <span style={{ color: "#aaa" }}>—</span>}
                </td>

                {/* Default */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  <DefaultEditor value={dest.default}
                    onChange={(v) => onConfigChange(updateDestAt(config, idx, { default: v }))} />
                </td>

                {/* Actions */}
                <td style={{ padding: "0.4rem 0.5rem" }}>
                  <button type="button" aria-label={`Remove ${dest.name}`}
                    style={{ color: "red", cursor: "pointer", padding: "0.1rem 0.5rem" }}
                    onClick={() => onConfigChange(removeDestinationField(config, dest.name))}>
                    −
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {showAddForm
        ? <AddFieldForm
            onAdd={(field) => { onConfigChange(addDestinationField(config, field)); setShowAddForm(false); }}
            onCancel={() => setShowAddForm(false)} />
        : <button type="button" onClick={() => setShowAddForm(true)}
            style={{ marginTop: "0.5rem", padding: "0.25rem 0.75rem" }}>
            + Add destination field
          </button>}
    </div>
  );
}
