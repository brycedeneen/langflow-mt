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

  pendingSuggestions?: MappingEntry[];
  showPendingSuggestions?: boolean;
  onAcceptSuggestion?: (destination: string) => void;
  onRejectSuggestion?: (destination: string) => void;
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
      className={`w-[90px] text-[0.8em]${bad ? " border border-destructive" : ""}`}
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
      className="flex flex-wrap items-end gap-2 mt-2 p-2 bg-muted rounded border border-border"
    >
      <div>
        <label className="block text-[0.75em]">Name *</label>
        <input autoFocus type="text" value={name} placeholder="field_name"
          data-testid="data-mapper-field-name-input"
          className={`w-[140px]${nameErr ? " border border-destructive" : ""}`}
          onChange={(e) => { setName(e.target.value); setNameErr(false); }} />
      </div>
      <div>
        <label className="block text-[0.75em]">Type</label>
        <select value={type} data-testid="data-mapper-field-type-select" onChange={(e) => setType(e.target.value as FieldType)}>
          {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-[0.75em]">Default (JSON)</label>
        <input type="text" value={defaultVal} placeholder="null" className="w-[100px]"
          onChange={(e) => setDefaultVal(e.target.value)} />
      </div>
      <label className="flex items-center gap-1 text-[0.85em]">
        <input type="checkbox" checked={required} data-testid="data-mapper-field-required-checkbox" onChange={(e) => setRequired(e.target.checked)} />
        Required
      </label>
      <button type="submit" data-testid="data-mapper-field-add-submit" className="px-3 py-1">Add</button>
      <button type="button" onClick={onCancel} className="px-3 py-1">Cancel</button>
    </form>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

/** Short human-readable summary of a MappingEntry, for read-only pending rows. */
function summarizePendingEntry(entry: MappingEntry): string {
  switch (entry.transform) {
    case "direct": {
      const s = entry.sources[0];
      return s ? `${s.input}.${s.field}` : "—";
    }
    case "template":
      return typeof entry.config.template === "string"
        ? entry.config.template
        : JSON.stringify(entry.config);
    case "static":
      return typeof entry.config.value === "string"
        ? entry.config.value
        : JSON.stringify(entry.config.value ?? null);
    case "variable":
      return typeof entry.config.name === "string"
        ? `$${entry.config.name}`
        : JSON.stringify(entry.config);
    case "expression":
      return typeof entry.config.expr === "string"
        ? entry.config.expr
        : JSON.stringify(entry.config);
    case "array":
      return entry.sources.map((s) => `${s.input}.${s.field}`).join(", ") || "[]";
    default:
      return JSON.stringify(entry.config);
  }
}

export function DestinationTable(props: DestinationTableProps) {
  const { config, errors = [], onConfigChange, pendingSuggestions, showPendingSuggestions } = props;
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <div className="destination-table overflow-x-auto">
      <table className="w-full border-collapse text-[0.9em]">
        <thead>
          <tr className="border-b-2 border-border text-left">
            {["Destination field", "Type", "Required", "Transform", "Source / Config", "Default", "Actions"]
              .map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {config.destination_schema.length === 0 && (
            <tr>
              <td colSpan={7} className="p-4 text-center text-muted-foreground italic">
                No destination fields yet — add one below.
              </td>
            </tr>
          )}

          {config.destination_schema.map((dest, idx) => {
            const mapping = config.mappings.find((m) => m.destination === dest.name);
            const rowError = rowHasError(errors, dest, idx);
            const pendingEntry =
              pendingSuggestions && showPendingSuggestions
                ? pendingSuggestions.find((p) => p.destination === dest.name)
                : undefined;

            const rowClass = pendingEntry
              ? "border-l-[3px] border-l-primary bg-primary/10"
              : rowError
                ? "border-l-[3px] border-l-destructive bg-destructive/5"
                : "";

            return (
              <tr
                key={dest.name}
                className={`border-b border-border ${rowClass}`}
              >
                {/* Destination field: name input + type pill + inline error */}
                <td className="px-2 py-1.5">
                  <input
                    type="text"
                    value={dest.name}
                    className="block w-[130px] font-medium"
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { name: e.target.value }))}
                  />
                  <span className="text-[0.7em] bg-accent text-accent-foreground rounded-sm px-[5px] py-px">{dest.type}</span>
                  {rowError && (
                    <span className="block text-destructive text-[0.75em] mt-0.5">
                      {rowError.message}
                    </span>
                  )}
                </td>

                {/* Type */}
                <td className="px-2 py-1.5">
                  <select value={dest.type}
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { type: e.target.value as FieldType }))}>
                    {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>

                {/* Required */}
                <td className="px-2 py-1.5 text-center">
                  <input type="checkbox" checked={dest.required}
                    onChange={(e) => onConfigChange(updateDestAt(config, idx, { required: e.target.checked }))} />
                </td>

                {/* Transform */}
                <td className="px-2 py-1.5">
                  {pendingEntry
                    ? <span className="text-muted-foreground">{pendingEntry.transform}</span>
                    : <select value={mapping?.transform ?? "direct"}
                        data-testid={`data-mapper-transform-select-${dest.name}`}
                        onChange={(e) =>
                          onConfigChange(setTransformForDestination(config, dest.name, e.target.value as TransformType))}>
                        {TRANSFORM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>}
                </td>

                {/* Source / Config */}
                <td className="px-2 py-1.5">
                  {pendingEntry
                    ? <span className="text-muted-foreground">{summarizePendingEntry(pendingEntry)}</span>
                    : mapping
                      ? <TransformCell mapping={mapping} inputs={config.inputs}
                          onMappingChange={(entry) => onConfigChange(updateMappingEntry(config, entry))} />
                      : <span className="text-muted-foreground">—</span>}
                </td>

                {/* Default */}
                <td className="px-2 py-1.5">
                  <DefaultEditor value={dest.default}
                    onChange={(v) => onConfigChange(updateDestAt(config, idx, { default: v }))} />
                </td>

                {/* Actions */}
                <td className="px-2 py-1.5">
                  <button type="button" aria-label={`Remove ${dest.name}`}
                    className="text-destructive cursor-pointer px-2 py-0.5"
                    onClick={() => onConfigChange(removeDestinationField(config, dest.name))}>
                    −
                  </button>
                </td>

                {pendingEntry && (
                  <td className="px-2 py-1.5 whitespace-nowrap">
                    <button
                      type="button"
                      aria-label={`Accept suggestion for ${dest.name}`}
                      onClick={() => props.onAcceptSuggestion?.(dest.name)}
                    >✓</button>
                    <button
                      type="button"
                      aria-label={`Reject suggestion for ${dest.name}`}
                      onClick={() => props.onRejectSuggestion?.(dest.name)}
                      className="ml-1"
                    >✗</button>
                  </td>
                )}
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
            data-testid="data-mapper-add-field-btn"
            className="mt-2 px-3 py-1">
            + Add destination field
          </button>}
    </div>
  );
}
