import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// VariableRead — sourced from services/database/models/variable/model.py
export const VariableReadSchema = z.looseObject({
  id: z.string().uuid(),
  name: z.string().optional().nullable(),
  type: z.string().optional().nullable(),
  value: z.string().optional().nullable(),
  default_fields: z.array(z.string()).optional().nullable(),
  validation_error: z.string().optional().nullable(),
  is_valid: z.boolean().optional().nullable(),
});

export type VariableRead = z.infer<typeof VariableReadSchema>;

// POST /variables/
registerSchema("api.variables.create", "permissive");

// GET /variables/
registerSchema("api.variables.list", "permissive");

// PATCH /variables/{variable_id}
registerSchema("api.variables.update", "permissive");

// DELETE /variables/{variable_id} — returns 204 No Content
registerSchema("api.variables.delete", "permissive");
