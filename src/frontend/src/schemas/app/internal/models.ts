/**
 * Hand-written zod schemas for /api/v1/models — router is hidden from OpenAPI
 * (include_in_schema=False).
 *
 * Source: src/backend/base/langflow/api/v1/models.py
 * Covers model providers, default model selection, enabled-model lists, validation.
 */

import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// ---------------------------------------------------------------------------
// Provider variable descriptor
// Each entry in the provider-variable-mapping value array looks like:
//   { variable_name, variable_key, description, required, is_secret, is_list, options? }
// ---------------------------------------------------------------------------
export const ProviderVariableSchema = z.looseObject({
  variable_name: z.string().optional(),
  variable_key: z.string().optional(),
  description: z.string().optional(),
  required: z.boolean().optional(),
  is_secret: z.boolean().optional(),
  is_list: z.boolean().optional(),
  options: z.array(z.string()).optional(),
});

// ---------------------------------------------------------------------------
// Model metadata — capabilities flags
// ---------------------------------------------------------------------------
export const ModelMetadataSchema = z.looseObject({
  tool_calling: z.boolean().optional(),
  reasoning: z.boolean().optional(),
  search: z.boolean().optional(),
  preview: z.boolean().optional(),
  deprecated: z.boolean().optional(),
  not_supported: z.boolean().optional(),
  default: z.boolean().optional(),
});

// ---------------------------------------------------------------------------
// Single model descriptor within a provider dict
// ---------------------------------------------------------------------------
export const ModelDescriptorSchema = z.looseObject({
  model_name: z.string().optional(),
  display_name: z.string().optional(),
  label: z.string().optional(),
  model_type: z.string().optional(),
  metadata: ModelMetadataSchema.optional(),
});

// ---------------------------------------------------------------------------
// Provider dict — returned by GET /models (list_models)
// Shape from get_unified_models_detailed + is_configured / is_enabled added
// ---------------------------------------------------------------------------
export const ProviderModelsDictSchema = z.looseObject({
  provider: z.string().optional(),
  label: z.string().optional(),
  models: z.array(ModelDescriptorSchema).optional(),
  is_configured: z.boolean().optional(),
  is_enabled: z.boolean().optional(),
});

// ---------------------------------------------------------------------------
// Route: GET /models/providers
// Function: list_model_providers
// Response: list[str]
// ---------------------------------------------------------------------------
registerSchema("api.models.list_model_providers", "permissive");

export const ListModelProvidersResponseSchema = z.array(z.string());
export type ListModelProvidersResponse = z.infer<
  typeof ListModelProvidersResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: GET /models  (root — list models)
// Function: list_models
// Response: list[ProviderModelsDict]  (varies heavily by filters)
// ---------------------------------------------------------------------------
registerSchema("api.models.list_models", "permissive");

export const ListModelsResponseSchema = z.array(ProviderModelsDictSchema);
export type ListModelsResponse = z.infer<typeof ListModelsResponseSchema>;

// ---------------------------------------------------------------------------
// Route: GET /models/provider-variable-mapping
// Function: get_model_provider_mapping
// Response: dict[str, list[ProviderVariable]]
// ---------------------------------------------------------------------------
registerSchema("api.models.get_model_provider_mapping", "permissive");

export const ProviderVariableMappingSchema = z.record(
  z.string(),
  z.array(ProviderVariableSchema),
);
export type ProviderVariableMapping = z.infer<
  typeof ProviderVariableMappingSchema
>;

// ---------------------------------------------------------------------------
// Route: GET /models/enabled_providers
// Function: get_enabled_providers
// Response: { enabled_providers: list[str], provider_status: dict[str, bool] }
// ---------------------------------------------------------------------------
registerSchema("api.models.get_enabled_providers", "permissive");

export const EnabledProvidersResponseSchema = z.looseObject({
  enabled_providers: z.array(z.string()).optional(),
  provider_status: z.record(z.string(), z.boolean()).optional(),
});

export type EnabledProvidersResponse = z.infer<
  typeof EnabledProvidersResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: POST /models/validate-provider
// Function: validate_provider
// Response: ValidateProviderResponse  → { valid: bool, error: str | null }
// ---------------------------------------------------------------------------
registerSchema("api.models.validate_provider", "permissive");

export const ValidateProviderResponseSchema = z.looseObject({
  valid: z.boolean(),
  error: z.string().nullable().optional(),
});

export type ValidateProviderResponse = z.infer<
  typeof ValidateProviderResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: GET /models/enabled_models
// Function: get_enabled_models
// Response: { enabled_models: dict[str, dict[str, bool]] }
//
// NOTE (soft-spot-3): z.looseObject() is intentional here. The consumer
// (ModelSelection.tsx) accesses enabled_models[providerName]?.[modelName] via
// dynamic keys — fully covered by z.record(z.string(), z.record(z.string(), z.boolean())). The outer
// z.looseObject() lets future runtime-injected fields survive without schema
// failures. Tightening further is low-value: the inner record already enforces
// the boolean values the UI reads.
// ---------------------------------------------------------------------------
registerSchema("api.models.get_enabled_models", "permissive");

export const EnabledModelsResponseSchema = z.looseObject({
  enabled_models: z.record(z.string(), z.record(z.string(), z.boolean())).optional(),
});

export type EnabledModelsResponse = z.infer<typeof EnabledModelsResponseSchema>;

// ---------------------------------------------------------------------------
// Route: POST /models/enabled_models
// Function: update_enabled_models
// Request body: list[ModelStatusUpdate]
// Response: { disabled_models: list[str], enabled_models: list[str] }
// ---------------------------------------------------------------------------
registerSchema("api.models.update_enabled_models", "permissive");

export const ModelStatusUpdateSchema = z.looseObject({
  provider: z.string(),
  model_id: z.string(),
  enabled: z.boolean(),
});

export const UpdateEnabledModelsResponseSchema = z.looseObject({
  disabled_models: z.array(z.string()).optional(),
  enabled_models: z.array(z.string()).optional(),
});

export type UpdateEnabledModelsResponse = z.infer<
  typeof UpdateEnabledModelsResponseSchema
>;

// ---------------------------------------------------------------------------
// Default model shape (stored as JSON in a user variable)
// ---------------------------------------------------------------------------
export const DefaultModelDataSchema = z.looseObject({
  model_name: z.string().optional(),
  provider: z.string().optional(),
  model_type: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Route: GET /models/default_model
// Function: get_default_model
// Response: { default_model: DefaultModelData | null }
// ---------------------------------------------------------------------------
registerSchema("api.models.get_default_model", "permissive");

export const GetDefaultModelResponseSchema = z.looseObject({
  default_model: DefaultModelDataSchema.nullable().optional(),
});

export type GetDefaultModelResponse = z.infer<
  typeof GetDefaultModelResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: POST /models/default_model
// Function: set_default_model
// Request body: DefaultModelRequest  → { model_name, provider, model_type }
// Response: { default_model: DefaultModelData }
// ---------------------------------------------------------------------------
registerSchema("api.models.set_default_model", "permissive");

export const SetDefaultModelResponseSchema = z.looseObject({
  default_model: DefaultModelDataSchema.optional(),
});

export type SetDefaultModelResponse = z.infer<
  typeof SetDefaultModelResponseSchema
>;

// ---------------------------------------------------------------------------
// Route: DELETE /models/default_model
// Function: clear_default_model
// Response: { default_model: null }
// ---------------------------------------------------------------------------
registerSchema("api.models.clear_default_model", "permissive");

export const ClearDefaultModelResponseSchema = z.looseObject({
  default_model: z.null().optional(),
});

export type ClearDefaultModelResponse = z.infer<
  typeof ClearDefaultModelResponseSchema
>;

// ---------------------------------------------------------------------------
// Convenience re-exports
// ---------------------------------------------------------------------------
export type ModelStatusUpdate = z.infer<typeof ModelStatusUpdateSchema>;
export type DefaultModelData = z.infer<typeof DefaultModelDataSchema>;
export type ProviderModelsDict = z.infer<typeof ProviderModelsDictSchema>;
