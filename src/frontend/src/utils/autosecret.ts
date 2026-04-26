// Mirror of langflow.services.variable.auto_secrets.AUTOSECRET_PREFIX (and the
// legacy underscore-delimited form). Both prefixes start with `__autosecret`
// so `startsWith` covers both.
export const AUTOSECRET_PREFIX = "__autosecret";

export function isAutosecretMarker(value: unknown): boolean {
  return typeof value === "string" && value.startsWith(AUTOSECRET_PREFIX);
}
