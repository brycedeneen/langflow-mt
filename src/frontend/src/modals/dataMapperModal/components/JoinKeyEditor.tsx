import { useRef } from "react";
import { FieldDef, JoinKey } from "@/modals/dataMapperModal/types";

export interface JoinKeyEditorProps {
  keys: JoinKey[];
  driverFields: FieldDef[];
  lookupFields: FieldDef[];
  onKeysChange(next: JoinKey[]): void;
}

export function JoinKeyEditor({
  keys,
  driverFields,
  lookupFields,
  onKeysChange,
}: JoinKeyEditorProps) {
  // Per-row stable React keys. JoinKey is the wire format (mirrors a Python
  // schema) so we can't add _id to the type — instead keep a parallel ids
  // ref in lockstep with `keys` via the local mutation helpers below. On
  // external length changes we best-effort grow/truncate.
  const idsRef = useRef<string[]>([]);
  while (idsRef.current.length < keys.length) {
    idsRef.current.push(crypto.randomUUID());
  }
  if (idsRef.current.length > keys.length) {
    idsRef.current = idsRef.current.slice(0, keys.length);
  }

  function handleDriverChange(index: number, value: string) {
    const next = keys.map((k, i) =>
      i === index ? { ...k, driver_field: value } : k,
    );
    onKeysChange(next);
  }

  function handleLookupChange(index: number, value: string) {
    const next = keys.map((k, i) =>
      i === index ? { ...k, lookup_field: value } : k,
    );
    onKeysChange(next);
  }

  function handleRemove(index: number) {
    idsRef.current = idsRef.current.filter((_, i) => i !== index);
    onKeysChange(keys.filter((_, i) => i !== index));
  }

  function handleAddKey() {
    idsRef.current = [...idsRef.current, crypto.randomUUID()];
    onKeysChange([...keys, { driver_field: "", lookup_field: "" }]);
  }

  return (
    <div className="join-key-editor">
      {keys.map((key, index) => (
        <div
          key={idsRef.current[index] ?? `join-key-fallback-${index}`}
          className="join-key-row"
        >
          <select
            value={key.driver_field}
            onChange={(e) => handleDriverChange(index, e.target.value)}
          >
            {key.driver_field === "" && (
              <option value="">Select field</option>
            )}
            {driverFields.map((f) => (
              <option key={f.name} value={f.name}>
                {f.name}
              </option>
            ))}
          </select>
          <span>=</span>
          <select
            value={key.lookup_field}
            onChange={(e) => handleLookupChange(index, e.target.value)}
          >
            {key.lookup_field === "" && (
              <option value="">Select field</option>
            )}
            {lookupFields.map((f) => (
              <option key={f.name} value={f.name}>
                {f.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            aria-label="−"
            onClick={() => handleRemove(index)}
            disabled={keys.length === 1}
          >
            −
          </button>
        </div>
      ))}
      <button type="button" onClick={handleAddKey}>
        + Add key
      </button>
    </div>
  );
}
