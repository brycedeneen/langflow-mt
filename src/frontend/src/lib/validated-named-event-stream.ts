import { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

/**
 * Subscribe to a named SSE event with schema validation.
 *
 * Backend example:
 *   yield {"event": "vertex_build_end", "data": {...}}
 * Frontend:
 *   validatedNamedEventStream("stream.buildEvents.vertexEnd",
 *     VertexEndSchema, source, "vertex_build_end", onVertex);
 *
 * Returns a cleanup function that removes the listener.
 */
export function validatedNamedEventStream<T>(
  id: string,
  schema: z.ZodType<T>,
  source: EventSource,
  eventName: string,
  onMessage: (msg: T) => void,
  onInvalid?: (raw: unknown, err: z.ZodError) => void,
): () => void {
  const handler = (event: Event) => {
    const me = event as MessageEvent;
    let raw: unknown;
    try { raw = JSON.parse(me.data); }
    catch (parseErr) {
      const synthetic = new z.ZodError([{
        code: "custom", path: [],
        message: `Invalid JSON: ${(parseErr as Error).message}`,
      }]);
      reportParseFailure({ id, mode: getMode(id), error: synthetic, raw: me.data, boundary: "stream" });
      onInvalid?.(me.data, synthetic);
      return;
    }
    const result = schema.safeParse(raw);
    if (result.success) { onMessage(result.data); return; }
    const mode = getMode(id);
    reportParseFailure({ id, mode, error: result.error, raw, boundary: "stream" });
    if (mode === "permissive") { onMessage(raw as T); return; }
    onInvalid?.(raw, result.error);
  };
  source.addEventListener(eventName, handler);
  return () => source.removeEventListener(eventName, handler);
}
