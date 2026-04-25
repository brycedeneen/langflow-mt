/**
 * Hand-written zod schemas for /api/v1/knowledge_bases — router is hidden from
 * OpenAPI (include_in_schema=False).
 *
 * Source: src/backend/base/langflow/api/v1/knowledge_bases.py
 * Python types: KnowledgeBaseInfo, PaginatedChunkResponse, ChunkInfo, TaskResponse
 */

import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

/** Column config item — permissive, exact shape depends on KB creation request */
export const ColumnConfigItemSchema = z.looseObject({
  name: z.string().optional(),
  data_type: z.string().optional(),
});

export const KnowledgeBaseInfoSchema = z.looseObject({
  id: z.string(),
  dir_name: z.string(),
  name: z.string(),
  embedding_provider: z.string().optional(),
  embedding_model: z.string().optional(),
  size: z.number().optional(),
  words: z.number().optional(),
  characters: z.number().optional(),
  chunks: z.number().optional(),
  avg_chunk_size: z.number().optional(),
  chunk_size: z.number().nullable().optional(),
  chunk_overlap: z.number().nullable().optional(),
  separator: z.string().nullable().optional(),
  status: z.string().optional(),
  failure_reason: z.string().nullable().optional(),
  last_job_id: z.string().nullable().optional(),
  source_types: z.array(z.string()).optional(),
  column_config: z.array(ColumnConfigItemSchema).nullable().optional(),
});

export const ChunkInfoSchema = z.looseObject({
  id: z.string(),
  content: z.string(),
  char_count: z.number().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const PaginatedChunkResponseSchema = z.looseObject({
  chunks: z.array(ChunkInfoSchema),
  total: z.number(),
  page: z.number(),
  limit: z.number(),
  total_pages: z.number(),
});

/** Mirrors langflow.api.v1.schemas.TaskResponse */
export const TaskResponseSchema = z.looseObject({
  id: z.string(),
  href: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Route: POST /knowledge_bases  (+ /knowledge_bases/)
// Function: create_knowledge_base
// Response: KnowledgeBaseInfo
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.create_knowledge_base", "permissive");

export type CreateKnowledgeBaseResponse = z.infer<
  typeof KnowledgeBaseInfoSchema
>;

// ---------------------------------------------------------------------------
// Route: POST /knowledge_bases/preview-chunks
// Function: preview_chunks
// Response: dict { files: list[{ file_name, total_chunks, preview_chunks }] }
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.preview_chunks", "permissive");

export const PreviewChunkItemSchema = z.looseObject({
  content: z.string().optional(),
  index: z.number().optional(),
  char_count: z.number().optional(),
  start: z.number().optional(),
  end: z.number().optional(),
});

export const PreviewFileResultSchema = z.looseObject({
  file_name: z.string().optional(),
  total_chunks: z.number().optional(),
  preview_chunks: z.array(PreviewChunkItemSchema).optional(),
});

export const PreviewChunksResponseSchema = z.looseObject({
  files: z.array(PreviewFileResultSchema),
});

export type PreviewChunksResponse = z.infer<typeof PreviewChunksResponseSchema>;

// ---------------------------------------------------------------------------
// Route: POST /knowledge_bases/{kb_name}/ingest
// Function: ingest_files_to_knowledge_base
// Response: dict | TaskResponse  (always TaskResponse in practice for async path)
// ---------------------------------------------------------------------------
registerSchema(
  "api.knowledge_bases.ingest_files_to_knowledge_base",
  "permissive",
);

export const IngestResponseSchema = z
  .union([TaskResponseSchema, z.record(z.string(), z.unknown())])
  .optional();

export type IngestResponse = z.infer<typeof IngestResponseSchema>;

// ---------------------------------------------------------------------------
// Route: GET /knowledge_bases  (+ /knowledge_bases/)
// Function: list_knowledge_bases
// Response: list[KnowledgeBaseInfo]
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.list_knowledge_bases", "permissive");

export const KnowledgeBaseListSchema = z.array(KnowledgeBaseInfoSchema);
export type KnowledgeBaseListResponse = z.infer<typeof KnowledgeBaseListSchema>;

// ---------------------------------------------------------------------------
// Route: GET /knowledge_bases/{kb_name}
// Function: get_knowledge_base
// Response: KnowledgeBaseInfo
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.get_knowledge_base", "permissive");

export type KnowledgeBaseResponse = z.infer<typeof KnowledgeBaseInfoSchema>;

// ---------------------------------------------------------------------------
// Route: GET /knowledge_bases/{kb_name}/chunks
// Function: get_knowledge_base_chunks
// Response: PaginatedChunkResponse
// ---------------------------------------------------------------------------
registerSchema(
  "api.knowledge_bases.get_knowledge_base_chunks",
  "permissive",
);

export type KnowledgeBaseChunksResponse = z.infer<
  typeof PaginatedChunkResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: DELETE /knowledge_bases/{kb_name}
// Function: delete_knowledge_base
// Response: dict[str, str]  → { message: string }
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.delete_knowledge_base", "permissive");

export const DeleteKBResponseSchema = z.looseObject({
  message: z.string(),
});

export type DeleteKBResponse = z.infer<typeof DeleteKBResponseSchema>;

// ---------------------------------------------------------------------------
// Route: DELETE /knowledge_bases  (+ /knowledge_bases/)
// Function: delete_knowledge_bases_bulk
// Response: dict[str, object]  → { message, deleted_count, not_found? }
// ---------------------------------------------------------------------------
registerSchema(
  "api.knowledge_bases.delete_knowledge_bases_bulk",
  "permissive",
);

export const BulkDeleteKBResponseSchema = z.looseObject({
  message: z.string().optional(),
  deleted_count: z.number().optional(),
  not_found: z.string().optional(),
});

export type BulkDeleteKBResponse = z.infer<typeof BulkDeleteKBResponseSchema>;

// ---------------------------------------------------------------------------
// Route: POST /knowledge_bases/{kb_name}/cancel
// Function: cancel_ingestion
// Response: dict[str, str]  → { message: string }
// ---------------------------------------------------------------------------
registerSchema("api.knowledge_bases.cancel_ingestion", "permissive");

export const CancelIngestionResponseSchema = z.looseObject({
  message: z.string(),
});

export type CancelIngestionResponse = z.infer<
  typeof CancelIngestionResponseSchema
>;

// ---------------------------------------------------------------------------
// Convenience re-exports
// ---------------------------------------------------------------------------
export type KnowledgeBaseInfo = z.infer<typeof KnowledgeBaseInfoSchema>;
export type ChunkInfo = z.infer<typeof ChunkInfoSchema>;
export type PaginatedChunkResponse = z.infer<
  typeof PaginatedChunkResponseSchema
>;
