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
    onKeysChange(keys.filter((_, i) => i !== index));
  }

  function handleAddKey() {
    onKeysChange([...keys, { driver_field: "", lookup_field: "" }]);
  }

  return (
    <div className="join-key-editor">
      {keys.map((key, index) => (
        <div key={index} className="join-key-row">
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
