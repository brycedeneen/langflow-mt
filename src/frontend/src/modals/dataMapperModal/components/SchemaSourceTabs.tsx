import { useState } from "react";
import { FieldDef, SchemaSource } from "@/modals/dataMapperModal/types";

export interface SchemaSourceTabsProps {
  source: SchemaSource;
  fields?: FieldDef[] | null;
  onSourceChange: (s: SchemaSource) => void;
  onSampleChange: (sample: unknown) => void;
  onJsonSchemaChange: (schema: Record<string, unknown>) => void;
}

const TAB_LABELS: Record<SchemaSource, string> = {
  autodetect: "Autodetect",
  sample: "Paste sample",
  jsonschema: "JSON Schema",
};

export function SchemaSourceTabs(props: SchemaSourceTabsProps) {
  const { source, fields, onSourceChange, onSampleChange, onJsonSchemaChange } = props;
  const [sampleText, setSampleText] = useState("");
  const [schemaText, setSchemaText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  return (
    <div className="schema-source-tabs">
      <div role="tablist" className="tab-row">
        {(["autodetect", "sample", "jsonschema"] as SchemaSource[]).map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={source === s}
            onClick={() => onSourceChange(s)}
          >
            {TAB_LABELS[s]}
          </button>
        ))}
      </div>

      {source === "autodetect" && (
        <div>
          {fields && fields.length > 0 ? (
            <span>{fields.length} fields detected</span>
          ) : (
            <p className="hint">
              No recent flow run found — run this flow once, or switch to Paste sample / JSON Schema.
            </p>
          )}
        </div>
      )}

      {source === "sample" && (
        <div>
          <textarea
            value={sampleText}
            onChange={(e) => {
              setSampleText(e.target.value);
              try {
                onSampleChange(JSON.parse(e.target.value));
                setParseError(null);
              } catch (err: any) {
                setParseError(err?.message ?? "Invalid JSON");
              }
            }}
            placeholder='Paste a representative JSON payload, e.g. {"user_id": "u-1", "email": "a@b.co"}'
          />
          {parseError && <p className="error">{parseError}</p>}
        </div>
      )}

      {source === "jsonschema" && (
        <div>
          <textarea
            value={schemaText}
            onChange={(e) => {
              setSchemaText(e.target.value);
              try {
                onJsonSchemaChange(JSON.parse(e.target.value));
                setParseError(null);
              } catch (err: any) {
                setParseError(err?.message ?? "Invalid JSON");
              }
            }}
            placeholder="Paste a JSON Schema document"
          />
          {parseError && <p className="error">{parseError}</p>}
        </div>
      )}
    </div>
  );
}
