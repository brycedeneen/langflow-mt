import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// GET /model_options/language and /model_options/embedding
// Both return list[dict[str, Any]] — no response_model declared; introspected from
// get_language_model_options / get_embedding_model_options in unified_models.py.
// TODO: backend returns untyped list[dict] — shape inferred from source inspection

export const ModelOptionItemSchema = z
  .object({
    name: z.string().optional(),
    icon: z.string().optional(),
    category: z.string().optional(),
    provider: z.string().optional(),
    metadata: z.record(z.unknown()).optional(),
  })
  .passthrough();

export type ModelOptionItem = z.infer<typeof ModelOptionItemSchema>;

export const ModelOptionsResponseSchema = z.array(ModelOptionItemSchema);

export type ModelOptionsResponse = z.infer<typeof ModelOptionsResponseSchema>;

// GET /model_options/language
registerSchema("api.model_options.language", "permissive");

// GET /model_options/embedding
registerSchema("api.model_options.embedding", "permissive");
