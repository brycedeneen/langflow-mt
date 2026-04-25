# Per-domain strict-flip criteria

**Date:** 2026-04-24
**Status:** Decision — strict flips are deferred. Full criteria + recommended order documented below.

---

## Decision

I considered flipping a subset of schemas to strict mode in this session. None should land without telemetry. The right knob to turn is "Sentry says zero ValidationErrors for ≥1 week," not "Claude thinks the schema looks tight enough."

Premature strict flips have a real cost: every backend response that drifts even harmlessly throws a `ValidationError` instead of passing through and reporting. For high-traffic endpoints (`/auth/session` fires on every page load), that's a red-banner-on-every-screen failure mode if the schema is even slightly wrong.

The Sentry adapter just landed (commit `16678e6e28`). With a DSN configured, telemetry will start flowing immediately. After ~1 week of zero events for a domain's schema ids, that domain is the right candidate for flipping.

## Recommended flip order (when telemetry is ready)

In priority order — start with the smallest blast radius and tightest schemas:

1. **`api.validate.*`** (3 ids) — small surface (`/validate/code`, `/validate/prompt`), only fires from explicit user actions. Schema is tight. Lowest blast radius.

2. **`api.voice.*`** (1 id) — single endpoint, only active during voice mode. Has a `z.union([array, error])` shape that's well-defined.

3. **`api.api_key.*`** (5 ids) — admin-only surface, predictable shape. Consumer cast (`as ApiKeyType`) is the only blemish; the schema itself is clean.

4. **`api.variables.*`** (5 ids) — global-variables admin surface. `name` field nullable in schema vs. required in consumer is the only mismatch — fixing the consumer would clear the path.

5. **`api.flows.*`** (10 ids) — flows is high-traffic but the schema set is well-defined (FlowRead, FlowCreate, etc., all generated from authoritative Pydantic models). Most likely to surface real backend drift if any.

6. **`api.templates.*`** (8 ids + 1 synthetic hard-delete) — template surface is recently shipped; bake an extra week before flipping to catch any drift from the FU-1..FU-6 follow-ups noted in agent memory.

7. **`api.monitor.*`** (the messages domain — 6 ids) — chat history surface. Permissive note: `MessageRead` has frontend-derived fields that may not be in the wire shape; may need a minor retighten before flipping.

8. **`api.auth.*`** + **`api.users.*`** (10 ids combined) — high blast radius (every page load hits getSession). Defer to last, even after a successful 1-week bake on simpler domains. Want maximum confidence the schema is right before letting it gate page rendering.

## Domains to NOT flip even after a long bake

These have known schema looseness that would surface as false positives in strict mode:

- **`api.admin.*`** — many endpoints have hand-written local types in `admin/types.ts` that diverge from generated zod-inferred types (`MemberRow`, `OrgDetail`, etc). A fix is needed *before* flipping; flipping first would just spam Sentry with type-shape mismatches that are frontend-side, not backend drift.

- **`api.models.*`** — `EnabledModelsResponseSchema` correctly types the indexed access shape, but other model endpoints use `.passthrough()` because the runtime injects fields. Those passthroughs are intentional but make strict-flip noisy.

- **`api.store.*`**, **`api.folders.*`**, **`api.knowledge_bases.*`** — large surfaces, many `.passthrough()`s where the schema couldn't fully capture the response. Each needs per-endpoint tightening before flipping.

- **`api.endpoints.*`** (the OpenAPI-hidden routes inside endpoints.py) — mixed bag including SSE streams and untyped dicts; some routes will never be flippable without a backend-side response_model retrofit.

- **`stream.*` schemas** — by their nature, message types arrive incrementally. The discriminated unions are best-effort; flipping risks rejecting unrecognized event types that backend may emit during normal operation. Revisit if/when the backend stabilizes its event contract.

## How to flip (mechanical recipe)

For an `api.<domain>.<op>` id originating in the generated registry:

```diff
// src/frontend/src/schemas/api/generated.meta.ts
- ["api.validate.code", "permissive"],
+ ["api.validate.code", "strict"],
```

For a hand-written schema (`src/schemas/app/internal/<file>.ts`):

```diff
- registerSchema("api.validate.code", "permissive");
+ registerSchema("api.validate.code", "strict");
```

Either way: one line, one commit, easy to revert. Convention: `feat(types): flip <domain> schemas to strict mode` for the commit subject; body lists which ids changed and confirms the bake duration.

## Verification before each flip

1. Sentry shows zero `ValidationError` events tagged with that domain's `schema_id` for ≥1 week of real traffic.
2. The admin overlay (in any dev session that's hit those endpoints) shows zero entries.
3. The consumer-side test suite still passes after the flip (TS won't error from a flag flip, but jest should be re-run as a smoke test).
4. Manual smoke: visit a screen that exercises the domain in dev, verify no ValidationError red banner.

If any check fails, revert the flag flip, fix the underlying drift (in backend or schema), and reset the bake clock.

---

## Why this matters

The boundary-validation project trades a minor runtime cost (zod parse) for a major safety guarantee (no silent data corruption from drift). That guarantee depends on the strict flip happening **at the right time** — not too early (false positives drown the signal), not too late (real bugs ship before we catch them). Telemetry is the gate.
