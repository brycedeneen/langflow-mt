import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Backend event format from lfx/events/event_manager.py:
//   {"event": "<event_type>", "data": {...}}
// Known event types from create_default_event_manager:
//   token, vertices_sorted, error, end, add_message, remove_message,
//   end_vertex, build_start, build_end
// Webhook SSE hook also observes: connected, heartbeat (custom event names)

const TokenEventSchema = z.object({ event: z.literal("token"), data: z.record(z.string(), z.unknown()) });
const VerticesSortedEventSchema = z.object({ event: z.literal("vertices_sorted"), data: z.record(z.string(), z.unknown()) });
const ErrorEventSchema = z.object({
  event: z.literal("error"),
  data: z.looseObject({ message: z.string() }),
});
const EndEventSchema = z.object({ event: z.literal("end"), data: z.record(z.string(), z.unknown()).optional() });
const AddMessageEventSchema = z.object({ event: z.literal("add_message"), data: z.record(z.string(), z.unknown()) });
const RemoveMessageEventSchema = z.object({ event: z.literal("remove_message"), data: z.record(z.string(), z.unknown()) });
const EndVertexEventSchema = z.object({ event: z.literal("end_vertex"), data: z.record(z.string(), z.unknown()) });
const BuildStartEventSchema = z.object({ event: z.literal("build_start"), data: z.record(z.string(), z.unknown()) });
const BuildEndEventSchema = z.object({ event: z.literal("build_end"), data: z.record(z.string(), z.unknown()) });

export const BuildEventSchema = z.discriminatedUnion("event", [
  TokenEventSchema,
  VerticesSortedEventSchema,
  ErrorEventSchema,
  EndEventSchema,
  AddMessageEventSchema,
  RemoveMessageEventSchema,
  EndVertexEventSchema,
  BuildStartEventSchema,
  BuildEndEventSchema,
]);

registerSchema("stream.buildEvents", "permissive");

export type BuildEvent = z.infer<typeof BuildEventSchema>;
