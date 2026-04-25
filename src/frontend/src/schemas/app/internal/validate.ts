import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// POST /validate/code
// Request: Code { code: str }
// Response: CodeValidationResponse { imports: dict, function: dict }
export const CodeValidationResponseSchema = z.looseObject({
  imports: z.record(z.string(), z.unknown()),
  function: z.record(z.string(), z.unknown()),
});

export type CodeValidationResponse = z.infer<typeof CodeValidationResponseSchema>;

// POST /validate/prompt
// Request: ValidatePromptRequest { name, template, custom_fields?, frontend_node?, mustache? }
// Response: PromptValidationResponse { input_variables: list, frontend_node?: object }
export const PromptValidationResponseSchema = z.looseObject({
  input_variables: z.array(z.unknown()),
  frontend_node: z.record(z.string(), z.unknown()).optional().nullable(),
});

export type PromptValidationResponse = z.infer<typeof PromptValidationResponseSchema>;

registerSchema("api.validate.code", "permissive");
registerSchema("api.validate.prompt", "permissive");
