import { FieldDef, FieldType } from "@/modals/dataMapperModal/types";

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function inferType(v: unknown): FieldType {
  if (v === null || v === undefined) return "str";
  if (typeof v === "string") {
    if (ISO_DATETIME.test(v)) return "datetime";
    if (ISO_DATE.test(v)) return "date";
    return "str";
  }
  if (typeof v === "boolean") return "bool";
  if (typeof v === "number") return Number.isInteger(v) ? "int" : "float";
  if (Array.isArray(v)) return "list";
  if (typeof v === "object") return "dict";
  return "str";
}

export function inferSampleFields(sample: unknown): FieldDef[] {
  const obj =
    Array.isArray(sample) && sample.length > 0 && typeof sample[0] === "object" && sample[0] !== null
      ? (sample[0] as Record<string, unknown>)
      : sample && typeof sample === "object" && !Array.isArray(sample)
      ? (sample as Record<string, unknown>)
      : null;

  if (!obj) return [];

  return Object.entries(obj).map(([name, v]) => ({
    name,
    type: inferType(v),
    required: false,
  }));
}
