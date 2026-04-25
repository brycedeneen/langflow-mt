import { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

/**
 * Wrap a WebSocket's message handler with schema validation.
 * Replaces socket.onmessage; preserves other lifecycle handlers untouched.
 *
 * Note: WebSocket binary messages (Blob/ArrayBuffer) are coerced to empty string
 * and routed to onInvalid. If a future consumer needs binary support, add a
 * separate wrapper.
 */
export function validatedSocket<T>(
  id: string,
  schema: z.ZodType<T>,
  socket: WebSocket,
  onMessage: (msg: T) => void,
  onInvalid?: (raw: unknown, err: z.ZodError) => void,
): void {
  socket.onmessage = (event) => {
    let raw: unknown;
    const text = typeof event.data === "string" ? event.data : "";
    try { raw = JSON.parse(text); }
    catch (parseErr) {
      const synthetic = new z.ZodError([{
        code: "custom", path: [],
        message: `Invalid JSON: ${(parseErr as Error).message}`,
      }]);
      reportParseFailure({ id, mode: getMode(id), error: synthetic, raw: event.data, boundary: "stream" });
      onInvalid?.(event.data, synthetic);
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
