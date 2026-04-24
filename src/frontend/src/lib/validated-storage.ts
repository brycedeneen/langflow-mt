import type { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

export function validatedStorage<T>(id: string, schema: z.ZodType<T>, base: Storage = localStorage): Storage {
  return {
    get length() { return base.length; },
    key: base.key.bind(base),
    getItem: (key: string) => {
      const raw = base.getItem(key);
      if (raw === null) return null;
      let parsed: unknown;
      try { parsed = JSON.parse(raw); } catch { return null; }
      const result = schema.safeParse(parsed);
      if (result.success) return JSON.stringify(result.data);
      const mode = getMode(id);
      reportParseFailure({ id, mode, error: result.error, raw: parsed, boundary: "storage" });
      if (mode === "strict") { base.removeItem(key); return null; }
      return raw;
    },
    setItem: base.setItem.bind(base),
    removeItem: base.removeItem.bind(base),
    clear: base.clear.bind(base),
  };
}
