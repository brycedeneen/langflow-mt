import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Source: langflow/services/store/schema.py
// Entire /store router is hidden: include_in_schema=False at the router level.

// TagResponse { id: UUID, name: str | None }
export const TagResponseSchema = z
  .object({
    id: z.string(),
    name: z.string().optional().nullable(),
  })
  .passthrough();

export type TagResponse = z.infer<typeof TagResponseSchema>;

// UsersLikesResponse { likes_count: int | None, liked_by_user: bool | None }
export const UsersLikesResponseSchema = z
  .object({
    likes_count: z.number().optional().nullable(),
    liked_by_user: z.boolean().optional().nullable(),
  })
  .passthrough();

export type UsersLikesResponse = z.infer<typeof UsersLikesResponseSchema>;

// CreateComponentResponse { id: UUID }
export const CreateComponentResponseSchema = z
  .object({
    id: z.string(),
  })
  .passthrough();

export type CreateComponentResponse = z.infer<typeof CreateComponentResponseSchema>;

// ListComponentResponse — one entry in the results array
export const ListComponentResponseSchema = z
  .object({
    id: z.string().optional().nullable(),
    name: z.string().optional().nullable(),
    description: z.string().optional().nullable(),
    liked_by_count: z.number().optional().nullable(),
    liked_by_user: z.boolean().optional().nullable(),
    is_component: z.boolean().optional().nullable(),
    metadata: z.record(z.unknown()).optional().nullable(),
    user_created: z.record(z.unknown()).optional().nullable(),
    tags: z.array(TagResponseSchema).optional().nullable(),
    downloads_count: z.number().optional().nullable(),
    last_tested_version: z.string().optional().nullable(),
    private: z.boolean().optional().nullable(),
  })
  .passthrough();

export type ListComponentResponse = z.infer<typeof ListComponentResponseSchema>;

// ListComponentResponseModel { count, authorized, results }
export const ListComponentResponseModelSchema = z
  .object({
    count: z.number().optional().nullable(),
    authorized: z.boolean(),
    results: z.array(ListComponentResponseSchema).optional().nullable(),
  })
  .passthrough();

export type ListComponentResponseModel = z.infer<typeof ListComponentResponseModelSchema>;

// DownloadComponentResponse { id, name, description, data, is_component, metadata }
export const DownloadComponentResponseSchema = z
  .object({
    id: z.string(),
    name: z.string().optional().nullable(),
    description: z.string().optional().nullable(),
    data: z.record(z.unknown()).optional().nullable(),
    is_component: z.boolean().optional().nullable(),
    metadata: z.record(z.unknown()).optional().nullable(),
  })
  .passthrough();

export type DownloadComponentResponse = z.infer<typeof DownloadComponentResponseSchema>;

// GET /store/check/ — returns { enabled: bool }
export const StoreCheckResponseSchema = z
  .object({
    enabled: z.boolean(),
  })
  .passthrough();

export type StoreCheckResponse = z.infer<typeof StoreCheckResponseSchema>;

// GET /store/check/api_key — returns { has_api_key: bool, is_valid: bool }
export const StoreCheckApiKeyResponseSchema = z
  .object({
    has_api_key: z.boolean(),
    is_valid: z.boolean(),
  })
  .passthrough();

export type StoreCheckApiKeyResponse = z.infer<typeof StoreCheckApiKeyResponseSchema>;

// Register one id per route
registerSchema("api.store.check", "permissive");
registerSchema("api.store.checkApiKey", "permissive");
registerSchema("api.store.shareComponent", "permissive");
registerSchema("api.store.updateSharedComponent", "permissive");
registerSchema("api.store.getComponents", "permissive");
registerSchema("api.store.downloadComponent", "permissive");
registerSchema("api.store.getTags", "permissive");
registerSchema("api.store.getUserLikes", "permissive");
registerSchema("api.store.likeComponent", "permissive");
