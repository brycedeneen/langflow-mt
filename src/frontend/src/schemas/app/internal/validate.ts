import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// POST /validate/code
// Request: Code { code: str }
// Response: CodeValidationResponse { imports: dict, function: dict }
export const CodeValidationResponseSchema = z
  .object({
    imports: z.record(z.unknown()),
    function: z.record(z.unknown()),
  })
  .passthrough();

export type CodeValidationResponse = z.infer<typeof CodeValidationResponseSchema>;

// POST /validate/prompt
// Request: ValidatePromptRequest { name, template, custom_fields?, frontend_node?, mustache? }
// Response: PromptValidationResponse { input_variables: list, frontend_node?: object }
export const PromptValidationResponseSchema = z
  .object({
    input_variables: z.array(z.unknown()),
    frontend_node: z.record(z.unknown()).optional().nullable(),
  })
  .passthrough();

export type PromptValidationResponse = z.infer<typeof PromptValidationResponseSchema>;

registerSchema("api.validate.code", "permissive");
registerSchema("api.validate.prompt", "permissive");
