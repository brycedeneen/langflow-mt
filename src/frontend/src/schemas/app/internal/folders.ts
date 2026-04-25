/**
 * Hand-written zod schemas for /api/v1/folders — router is hidden from OpenAPI
 * (include_in_schema=False). All routes are redirect shims pointing to /api/v1/projects/.
 *
 * Source: src/backend/base/langflow/api/v1/folders.py
 */

import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

export const FlowReadSchema = z.looseObject({
  id: z.string().optional(),
  name: z.string().optional(),
  description: z.string().optional(),
  data: z.record(z.string(), z.unknown()).optional(),
  is_component: z.boolean().optional(),
  updated_at: z.string().optional(),
  created_at: z.string().optional(),
  folder_id: z.string().optional(),
  user_id: z.string().optional(),
});

export const FolderReadSchema = z.looseObject({
  id: z.string().optional(),
  name: z.string().optional(),
  description: z.string().optional(),
  parent_id: z.string().nullable().optional(),
  user_id: z.string().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});

export const FolderReadWithFlowsSchema = FolderReadSchema.extend({
  flows: z.array(FlowReadSchema).optional(),
});

export const FolderWithPaginatedFlowsSchema = z.looseObject({
  folder: FolderReadSchema.optional(),
  flows: z
    .looseObject({
      items: z.array(FlowReadSchema).optional(),
      total: z.number().optional(),
      page: z.number().optional(),
      size: z.number().optional(),
      pages: z.number().optional(),
    })
    .optional(),
});

// ---------------------------------------------------------------------------
// Route: POST /folders/  → 307 redirect → FolderRead
// Function: create_folder_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.create_folder_redirect", "permissive");

export type FolderCreateRedirectResponse = z.infer<typeof FolderReadSchema>;

// ---------------------------------------------------------------------------
// Route: GET /folders/  → 307 redirect → list[FolderRead]
// Function: read_folders_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.read_folders_redirect", "permissive");

export const FolderListSchema = z.array(FolderReadSchema);
export type FolderListResponse = z.infer<typeof FolderListSchema>;

// ---------------------------------------------------------------------------
// Route: GET /folders/{folder_id}  → 307 redirect → FolderWithPaginatedFlows | FolderReadWithFlows
// Function: read_folder_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.read_folder_redirect", "permissive");

export const FolderDetailResponseSchema = z.union([
  FolderWithPaginatedFlowsSchema,
  FolderReadWithFlowsSchema,
]);
export type FolderDetailResponse = z.infer<typeof FolderDetailResponseSchema>;

// ---------------------------------------------------------------------------
// Route: PATCH /folders/{folder_id}  → 307 redirect → FolderRead
// Function: update_folder_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.update_folder_redirect", "permissive");

export type FolderUpdateRedirectResponse = z.infer<typeof FolderReadSchema>;

// ---------------------------------------------------------------------------
// Route: DELETE /folders/{folder_id}  → 307 redirect → 204 No Content
// Function: delete_folder_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.delete_folder_redirect", "permissive");

// No body schema — 204 response

// ---------------------------------------------------------------------------
// Route: GET /folders/download/{folder_id}  → 307 redirect → raw download
// Function: download_file_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.download_file_redirect", "permissive");

// No typed body schema — resolves to a file download after redirect

// ---------------------------------------------------------------------------
// Route: POST /folders/upload/  → 307 redirect → list[FlowRead]
// Function: upload_file_redirect
// ---------------------------------------------------------------------------
registerSchema("api.folders.upload_file_redirect", "permissive");

export const FolderUploadResponseSchema = z.array(FlowReadSchema);
export type FolderUploadResponse = z.infer<typeof FolderUploadResponseSchema>;

// ---------------------------------------------------------------------------
// Convenience re-exports
// ---------------------------------------------------------------------------
export type FolderRead = z.infer<typeof FolderReadSchema>;
export type FolderReadWithFlows = z.infer<typeof FolderReadWithFlowsSchema>;
export type FolderWithPaginatedFlows = z.infer<
  typeof FolderWithPaginatedFlowsSchema
>;
