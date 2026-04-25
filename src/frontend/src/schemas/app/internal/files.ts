/**
 * Hand-written zod schemas for /api/v1/files — the profile-pictures listing
 * endpoint is not included in the auto-generated OpenAPI schemas.
 *
 * Source: src/backend/base/langflow/api/v1/files.py
 *   list_profile_pictures → GET /files/profile_pictures/list
 *   Returns: { "files": list[str] }  where each string is "folder/filename.ext"
 */

import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// ---------------------------------------------------------------------------
// Route: GET /files/profile_pictures/list
// Function: list_profile_pictures
// Response: { files: list[str] }
// ---------------------------------------------------------------------------
registerSchema(
  "api.files.list_profile_pictures_api_v1_files_profile_pictures_list_get",
  "permissive",
);

export const ProfilePictureListResponseSchema = z.object({
  files: z.array(z.string()),
});

export type ProfilePictureListResponse = z.infer<
  typeof ProfilePictureListResponseSchema
>;
