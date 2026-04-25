import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// ApiKeyRead — masked key (sourced from services/database/models/api_key/model.py)
export const ApiKeyReadSchema = z
  .object({
    id: z.string(),
    name: z.string().optional().nullable(),
    api_key: z.string(),
    user_id: z.string(),
    created_at: z.string().optional(),
    last_used_at: z.string().optional().nullable(),
    total_uses: z.number().optional(),
    is_active: z.boolean().optional(),
  })
  .passthrough();

// GET /api_key/ — returns ApiKeysResponse { total_count, user_id, api_keys }
export const ApiKeysResponseSchema = z
  .object({
    total_count: z.number(),
    user_id: z.string().uuid(),
    api_keys: z.array(ApiKeyReadSchema),
  })
  .passthrough();

export type ApiKeysResponse = z.infer<typeof ApiKeysResponseSchema>;

// POST /api_key/ — returns UnmaskedApiKeyRead { id, api_key, user_id, name?, last_used_at?, total_uses?, is_active? }
export const UnmaskedApiKeyReadSchema = z
  .object({
    id: z.string(),
    api_key: z.string(),
    user_id: z.string(),
    name: z.string().optional().nullable(),
    last_used_at: z.string().optional().nullable(),
    total_uses: z.number().optional(),
    is_active: z.boolean().optional(),
  })
  .passthrough();

export type UnmaskedApiKeyRead = z.infer<typeof UnmaskedApiKeyReadSchema>;

// DELETE /api_key/{api_key_id} — returns { detail: string }
export const ApiKeyDeleteResponseSchema = z
  .object({
    detail: z.string(),
  })
  .passthrough();

// POST /api_key/store — returns { detail: string }
export const ApiKeyStoreResponseSchema = z
  .object({
    detail: z.string(),
  })
  .passthrough();

registerSchema("api.api_key.list", "permissive");
registerSchema("api.api_key.create", "permissive");
registerSchema("api.api_key.delete", "permissive");
registerSchema("api.api_key.store", "permissive");
