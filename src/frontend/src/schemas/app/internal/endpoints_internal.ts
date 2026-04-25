import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// POST /run/session/{flow_id_or_name} (include_in_schema=False, session auth variant)
// Returns RunResponse | StreamingResponse — same shape as the public /run/{flow_id_or_name}.
// RunResponse has outputs: list[RunOutputs] and session_id: str
export const RunOutputResultSchema = z.record(z.string(), z.unknown());

export const RunOutputSchema = z.looseObject({
  component_id: z.string().optional(),
  component_display_name: z.string().optional(),
  component_is_custom: z.boolean().optional(),
  used_frozen_result: z.boolean().optional(),
  results: z.record(z.string(), z.unknown()).optional(),
  artifacts: z.record(z.string(), z.unknown()).optional(),
  outputs: z.record(z.string(), z.unknown()).optional(),
  logs: z.record(z.string(), z.unknown()).optional(),
  messages: z.array(z.record(z.string(), z.unknown())).optional(),
  timedelta: z.number().optional(),
  duration: z.string().optional(),
});

export const RunResponseSchema = z.looseObject({
  outputs: z.array(z.array(RunOutputSchema)).optional(),
  session_id: z.string().optional(),
});

export type RunResponse = z.infer<typeof RunResponseSchema>;

// GET /webhook-events/{flow_id_or_name} (include_in_schema=False)
// SSE endpoint — returns text/event-stream; not a JSON body.
// Typed as unknown; consumers should handle raw SSE frames.
// TODO: SSE stream — no structured JSON response body to validate.
export const WebhookEventsSchema = z.unknown();
export type WebhookEvents = z.infer<typeof WebhookEventsSchema>;

// GET /task/{_task_id} — deprecated, always throws 400. Zero frontend usage.
// Skipped intentionally. Raises HTTP 400 unconditionally.

// POST /custom_component (include_in_schema=False)
// Accepts CustomComponentRequest { code: str, frontend_node?: dict }
// Returns CustomComponentResponse { data: dict, type: str }
export const CustomComponentRequestSchema = z.looseObject({
  code: z.string(),
  frontend_node: z.record(z.string(), z.unknown()).optional().nullable(),
});

export type CustomComponentRequest = z.infer<typeof CustomComponentRequestSchema>;

export const CustomComponentResponseSchema = z.looseObject({
  data: z.record(z.string(), z.unknown()),
  type: z.string(),
});

export type CustomComponentResponse = z.infer<typeof CustomComponentResponseSchema>;

// POST /custom_component/update (include_in_schema=False)
// Accepts UpdateCustomComponentRequest { code, frontend_node?, field, field_value?, template, tool_mode? }
// Returns jsonable_encoder(component_node) — an untyped dict representing the frontend node.
// TODO: backend returns untyped dict (jsonable_encoder result); shape mirrors a component frontend node.
export const UpdateCustomComponentRequestSchema = z.looseObject({
  code: z.string(),
  frontend_node: z.record(z.string(), z.unknown()).optional().nullable(),
  field: z.string(),
  field_value: z.union([z.string(), z.number(), z.boolean(), z.record(z.string(), z.unknown()), z.array(z.unknown())]).optional().nullable(),
  template: z.record(z.string(), z.unknown()),
  tool_mode: z.boolean().optional(),
});

export type UpdateCustomComponentRequest = z.infer<typeof UpdateCustomComponentRequestSchema>;

export const UpdateCustomComponentResponseSchema = z.record(z.string(), z.unknown());
export type UpdateCustomComponentResponse = z.infer<typeof UpdateCustomComponentResponseSchema>;

registerSchema("api.endpoints.run_session", "permissive");
// SSE stream — no structured JSON response; typed as unknown above.
registerSchema("api.endpoints.webhook_events", "permissive");
registerSchema("api.endpoints.custom_component", "permissive");
registerSchema("api.endpoints.custom_component_update", "permissive");
