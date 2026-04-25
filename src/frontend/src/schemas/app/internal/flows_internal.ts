import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Shared FlowRead shape — sourced from services/database/models/flow/model.py
// FlowBase fields + FlowRead additions
export const FlowReadSchema = z
  .object({
    id: z.string().uuid(),
    name: z.string(),
    description: z.string().optional().nullable(),
    icon: z.string().optional().nullable(),
    icon_bg_color: z.string().optional().nullable(),
    gradient: z.string().optional().nullable(),
    data: z.record(z.unknown()).optional().nullable(),
    is_component: z.boolean().optional().nullable(),
    updated_at: z.string().optional().nullable(),
    webhook: z.boolean().optional().nullable(),
    built_with_assist: z.boolean().optional().nullable(),
    based_on_template_flow_id: z.string().uuid().optional().nullable(),
    endpoint_name: z.string().optional().nullable(),
    tags: z.array(z.string()).optional().nullable(),
    locked: z.boolean().optional().nullable(),
    mcp_enabled: z.boolean().optional().nullable(),
    action_name: z.string().optional().nullable(),
    action_description: z.string().optional().nullable(),
    access_type: z.string().optional().nullable(),
    webhook_url: z.string().optional().nullable(),
    webhook_secret: z.string().optional().nullable(),
    auto_retry: z.boolean().optional(),
    max_retries: z.number().optional(),
    timeout_seconds: z.number().optional(),
    // FlowRead-specific
    user_id: z.string().uuid().optional().nullable(),
    organization_id: z.string().uuid().optional().nullable(),
    folder_id: z.string().uuid().optional().nullable(),
  })
  .passthrough();

export type FlowRead = z.infer<typeof FlowReadSchema>;

// PUT /flows/{flow_id} — upsert, response_model=FlowRead
registerSchema("api.flows.update_legacy", "permissive");

// POST /flows/expand/ — returns raw dict (expanded flow data); no response_model declared
// TODO: backend returns untyped dict — shape is the full expanded flow node/edge graph
export const ExpandFlowResponseSchema = z.record(z.unknown());

export type ExpandFlowResponse = z.infer<typeof ExpandFlowResponseSchema>;

registerSchema("api.flows.expand", "permissive");
