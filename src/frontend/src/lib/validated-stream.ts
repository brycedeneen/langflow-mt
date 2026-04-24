import { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

export function validatedEventStream<T>(
  id: string,
  schema: z.ZodType<T>,
  source: EventSource,
  onMessage: (msg: T) => void,
  onInvalid?: (raw: unknown, err: z.ZodError) => void,
): void {
  source.onmessage = (event) => {
    let raw: unknown;
    try { raw = JSON.parse((event as MessageEvent).data); }
    catch (parseErr) {
      const synthetic = new z.ZodError([{
        code: "custom", path: [],
        message: `Invalid JSON: ${(parseErr as Error).message}`,
      }]);
      reportParseFailure({ id, mode: getMode(id), error: synthetic, raw: (event as MessageEvent).data, boundary: "stream" });
      onInvalid?.((event as MessageEvent).data, synthetic);
      return;
    }
    const result = schema.safeParse(raw);
    if (result.success) { onMessage(result.data); return; }
    const mode = getMode(id);
    reportParseFailure({ id, mode, error: result.error, raw, boundary: "stream" });
    if (mode === "permissive") { onMessage(raw as T); return; }
    onInvalid?.(raw, result.error);
  };
}
