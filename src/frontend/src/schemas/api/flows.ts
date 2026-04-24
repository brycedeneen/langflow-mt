import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Phase 0 walking-skeleton schema. Intentionally permissive — only the two
// fields every Flow response carries are required; everything else passes
// through. Phase 1's openapi-zod-client regeneration produces the
// authoritative shape, at which point this file is overwritten.
export const FlowSchema = z
  .object({
    id: z.string(),
    name: z.string(),
  })
  .passthrough();

registerSchema("api.flows.getFlow", "permissive");

export type FlowSchemaType = z.infer<typeof FlowSchema>;
