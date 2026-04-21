// Mirror of src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py.
// Keep in sync by hand — small surface, rare changes.

export type FieldType =
  | "str" | "int" | "float" | "bool"
  | "list" | "dict"
  | "date" | "datetime";

export type TransformType =
  | "direct" | "static" | "variable"
  | "template" | "expression" | "array";

export type SchemaSource = "autodetect" | "sample" | "jsonschema";

export interface FieldDef {
  name: string;
  type: FieldType;
  required: boolean;
}

export interface InputSchema { fields: FieldDef[]; }

export interface JoinKey {
  driver_field: string;
  lookup_field: string;
}

export interface JoinDef { on: JoinKey[]; }

export interface InputDef {
  alias: string;
  schema_source: SchemaSource;
  schema: InputSchema;
  sample?: Record<string, unknown> | unknown[] | null;
  jsonschema?: Record<string, unknown> | null;
  join?: JoinDef | null;
}

export interface DestFieldDef {
  name: string;
  type: FieldType;
  required: boolean;
  default: unknown;
}

export interface SourceRef { input: string; field: string; }

export interface MappingEntry {
  destination: string;
  transform: TransformType;
  sources: SourceRef[];
  config: Record<string, unknown>;
}

export interface MapperConfig {
  driver_index: number;
  inputs: InputDef[];
  destination_schema: DestFieldDef[];
  mappings: MappingEntry[];
}

export const EMPTY_MAPPER_CONFIG: MapperConfig = {
  driver_index: 0,
  inputs: [],
  destination_schema: [],
  mappings: [],
};
