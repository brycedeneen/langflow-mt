// Generated zod schemas for every public-OpenAPI endpoint and registry of
// permissive/strict modes. Re-exports the generated module under a stable name.
//
// `_generated.ts` is rewritten by `make gen_frontend_schemas`. `generated.meta.ts`
// holds the strict-flag registry; per-domain flips live there. Do not import from
// `_generated.ts` indirectly — call sites can import the named schemas directly via
// `@/schemas/api/_generated` for clarity.
export * from "./api/_generated";

// Phase 1 also adds hand-written schemas for the 34 OpenAPI-hidden endpoints
// under `./app/internal/*` — landed in Phase 1.3.
