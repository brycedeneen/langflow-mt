# Dependency updates: tiered refresh of backend + frontend packages

## Problem

A full audit (`uv pip list --outdated` + `npm outdated`, cross-referenced against declared deps only) shows:

| Bucket | Count |
|---|---|
| Python — core infrastructure, non-breaking | 17 |
| Python — core infrastructure, breaking | 20 |
| Python — integration (provider SDKs, vector stores, monitoring), non-breaking | 60 |
| Python — integration, breaking | 64 |
| Frontend — non-breaking | 30 |
| Frontend — breaking | 33 |

The codebase has drifted substantially off latest. Some hard-pinned libraries (`bcrypt==4.0.1`, `pandas==2.2.3`, `orjson==3.10.15`) carry known security or performance improvements in later versions. Other majors represent genuinely large migrations (LangChain 1.0, Pandas 3, Tailwind 4) that deserve their own project rather than being bundled into a mass bump.

The goal is a tiered refresh that captures the easy wins and the right set of breaking bumps while deferring the truly large migrations to standalone projects.

## Decision

Three phases, each split into reviewable sub-phases. Commits are granular; phases merge back to `platform-multi-tenant` after validating as a whole.

**Tiering rule:**
- **Non-breaking anywhere** → bump.
- **Breaking on the frontend** → bump (scope: all frontend breakers except Tailwind 4).
- **Breaking on the backend** → bump only for core infrastructure (web framework, data/validation, security, observability, core utilities, MCP). Skip breaking bumps in the long tail of provider SDKs, vector stores, and monitoring integrations.

**Deferred to their own specs (listed in Follow-ups below):**
- LangChain 0.3 → 1.x ecosystem
- Pandas 2 → 3
- Tailwind CSS 3 → 4 (+ `tailwind-merge` 2 → 3) — **prioritized as the next project immediately after Phase 2 validates**

## Scope

### In scope

**Phase 1 — non-breaking bumps** (all 107 items)

*Backend, core (17):*
`asyncer`, `fastmcp`, `filelock`, `mcp`, `opentelemetry-api`, `opentelemetry-exporter-otlp`, `opentelemetry-sdk`, `orjson`, `platformdirs`, `pydantic`, `pyjwt`, `pypdf`, `python-multipart`, `sentry-sdk`, `sqlalchemy`, `sqlmodel`, `tomli`.

*Backend, integration (60):*
`ag-ui-protocol`, `astra-assistants`, `astrapy`, `beautifulsoup4`, `boto3`, `chromadb`, `couchbase`, `coverage`, `cuga`, `ddgs`, `docling`, `docling-core`, `duckdb`, `faiss-cpu`, `faker`, `fastapi-pagination`, `fastavro`, `gitpython`, `google-api-python-client`, `greenlet`, `hypothesis`, `ibm-watsonx-ai`, `jaraco-context`, `langchain-sambanova`, `langchain-unstructured`, `langsmith`, `lark`, `litellm`, `locust`, `lxml`, `markdown`, `markupsafe`, `mcp-server-fetch`, `mlx`, `multiprocess`, `mypy`, `nltk`, `numexpr`, `onnxruntime`, `openinference-instrumentation-langchain`, `pymongo`, `pytest-cov`, `qdrant-client`, `requests`, `scrapegraph-py`, `sentence-transformers`, `spider-client`, `sseclient-py`, `supabase`, `torch`, all `types-*` stubs, `vulture`, `weaviate-client`.

*Frontend (30):*
`@biomejs/biome`, `@headlessui/react`, `@jest/types`, `@playwright/test`, all `@storybook/*`, `@swc/core`, `@tabler/icons-react`, `@tanstack/react-query`, `@types/lodash`, `@vitejs/plugin-react-swc`, `@xyflow/react`, `autoprefixer`, `axios`, `dompurify`, `fuse.js`, `jest`, `jest-environment-jsdom`, `lodash`, `nanoid`, `playwright`, `postcss`, `react`, `react-dom`, `react-hook-form`, `react-icons`, `storybook`, `ts-jest`.

**Phase 2 — frontend breaking bumps** (31 items; Tailwind + `tailwind-merge` excluded)

- 2a. Build toolchain: `vite` 7→8, `esbuild` 0.25→0.28, `@swc/cli` 0.5→0.8, `vite-plugin-svgr` 4→5
- 2b. Type definitions: `@types/node` 20→25, `@types/jest` 29→30, `@types/uuid` 9→10, `@types/axios` 0.14→0.9
- 2c. `typescript` 5 → 6 (isolated)
- 2d. Routing/state/forms: `react-router-dom` 6→7, `zustand` 4→5, `@hookform/resolvers` 3→5
- 2e. `zod` 3 → 4 (isolated)
- 2f. UI libs: `ag-grid-community` + `ag-grid-react` 32→35, `framer-motion` 11→12, `lucide-react` 0.5→1, `react-markdown` 9→10, `react-pdf` 9→10, `vanilla-jsoneditor` 2→3
- 2g. Utility libs: `uuid` 10→14, `dotenv` 16→17, `web-vitals` 4→5, `ua-parser-js` 1→2, `moment-timezone` 0.5→0.6, `react-cookie` 7→8, `react-error-boundary` 4→6, `react-hotkeys-hook` 4→5, `p-debounce` 4→5, `elkjs` 0.9→0.11, `openseadragon` 4→6

**Phase 3 — backend core-infra breaking bumps** (14 items; LangChain + Pandas excluded)

- 3a. Web framework: `fastapi` 0.135→0.136, `uvicorn` 0.41→0.44, `gunicorn` 22→25, `typer` 0.19→0.24, `rich` 13→15
- 3b. Security/auth: `bcrypt` 4→5, `cryptography` 43→46 (isolated)
- 3c. `pillow` 11 → 12 (isolated)
- 3d. Misc: `aiofiles` 24→25, `chardet` 5→7, `docstring-parser` 0.17→0.18, `json-repair` 0.30→0.59, `prometheus-client` 0.24→0.25, `validators` 0.34→0.35

### Out of scope

- **Deferred to own specs:** LangChain 0.3→1.x (`langchain`, `langchain-core`, `langchain-community`, `langchain-experimental`, `langchain-mcp-adapters`), Pandas 2→3, Tailwind 3→4 (+ `tailwind-merge` 2→3).
- **Not bumped this project:** 64 integration breaking bumps — provider SDKs (`openai` 1→2, `langchain-anthropic`, `langchain-openai`, all other `langchain-<provider>`), vector stores (`redis` 5→7, `opensearch-py` 2→3, `elasticsearch` 8→9, `pgvector`, `upstash-vector`, `yfinance`), monitoring SDKs (`langfuse` 2→4, `langwatch`, `opik` 1→2, `traceloop-sdk`, `openlayer`), agent frameworks (`ag2`, `dspy-ai` 2→3, `composio`, `codeflash`), data/test libs (`datasets` 3→4, `fastparquet`, `pyarrow` 19→23, `kubernetes` 31→35, `pytest` 8→9, `ruff` 0.13→0.15, `respx`, `setuptools`, `packaging`, `pip`, `pydantic-ai` 0.4→1.84, `twelvelabs`, `vlmrun`, `atlassian-python-api`, `arq`, `assemblyai`, `clickhouse-connect`, `firecrawl-py` 1→4, `huggingface-hub` 0→1, `jigsawstack`, `jsonquerylang`, `mem0ai`, `mlx-vlm`, `qianfan`, `torchvision`). Upgrade individually when actively used.
- **Internal workspace packages:** `langflow-base`, `lfx`, `langflow` version spec lines are not touched. These are managed via `make patch v=...`.

## Implementation

### Branching

- Create git worktree at `.worktrees/deps-upgrade-2026-04/` branched from `platform-multi-tenant`.
- Land all 13 sub-phase commits onto that branch.
- Merge back to `platform-multi-tenant` **per phase** (after Phase 1 validates, after Phase 2 validates, after Phase 3 validates) — not per sub-phase.
- No upstream push.
- No commit without explicit approval per sub-phase.

### Commit structure

One commit per sub-phase. Commit message format:

```
chore(deps): bump <group> — phase <N><letter>

<multi-line list of old→new versions>
<notes on any code changes required>
```

Each commit includes:
- Edits to `pyproject.toml` / `src/backend/base/pyproject.toml` / `src/lfx/pyproject.toml` or `src/frontend/package.json`
- Updated lockfile (`uv.lock` or `src/frontend/package-lock.json`)
- Any code migrations required by the bump (e.g., Zod 4 schema API, React Router 7 data router)

### Per-sub-phase workflow

1. Read the library's changelog for the crossed version range. Note migration steps in commit message.
2. Edit the version spec(s) in the pyproject/package.json.
3. Regenerate lockfile (`uv lock --upgrade-package <name>` or `npm install`).
4. If code changes are required, make them minimal and in the same commit.
5. Run the phase's verification gates (§ Verification below).
6. If gates pass, present diff + test results. Wait for approval. Commit.
7. If gates fail within the stop-the-line threshold (~30 min of fix-ups), fix and re-run. If not, split the sub-phase into its own follow-up spec and downgrade the bump.

### Verification gates

**Shared gates (every commit):**
1. Install succeeds — `uv sync` or `npm install` completes without resolver errors.
2. Lint/types pass — `make lint` (backend) and/or `npm run type-check` (frontend) for touched surfaces.
3. Unit tests pass — `make unit_tests` (backend) and/or `npm test` (frontend).
4. Build succeeds — `make run_clic` (backend-touching) and/or `npm run build` (frontend-touching).

**Phase-1 gates (non-breaking):** shared gates only.

**Phase-2 gates (frontend breaking):** shared gates + boot via `make backend` + `make frontend` and smoke the affected surface:
- 2a: dev server starts, HMR fires, prod build loads in browser
- 2b: `tsc --noEmit` clean (no runtime surface)
- 2c: full `tsc --noEmit` across project — budget for new errors
- 2d: login → flow list → flow editor → settings navigation; forms submit
- 2e: frontend tests + API error-path rendering (Zod validates inbound shapes)
- 2f: ag-grid tables render; framer-motion animations (sheets, dialogs); lucide icons visible; markdown/PDF render in chat/assist; JSON editor opens
- 2g: per-lib spot checks (hotkeys fire, cookies persist, error boundary catches, uuid-generated IDs don't collide)

**Phase-3 gates (backend breaking):** shared gates + boot API via `make backend` and exercise affected routes:
- 3a: `/health` 200; login; run a flow; streaming endpoint emits chunks
- 3b: login with an existing user (bcrypt 5 must verify hashes produced by bcrypt 4 — if not, add a rehash-on-login path in the same commit); JWT sign/verify; webhook API-key flow
- 3c: open a flow using an image component; upload image; render chat image
- 3d: shared gates sufficient (narrow surfaces)

## Risks

- **bcrypt 5 hash compatibility (3b):** v5 changed internals. If existing database password hashes fail to verify, Phase 3b must include a rehash-on-login path. Test explicitly with a pre-existing user account.
- **TypeScript 6 cascade (2c):** compiler majors surface previously-ignored errors. Budget for fix-ups across many files. Enforce stop-the-line rule if too invasive.
- **Zod 4 schema API (2e):** every `z.object(...)` call site needs audit. Concentrated in request/response validation.
- **ag-grid 32 → 35 (2f):** 3 major versions; column API and theme system shifted. May need config changes.
- **React Router 6 → 7 (2d):** data router API consolidated; `@react-router/dev migrate` tool available.
- **cryptography 43 → 46 (3b):** three majors; deprecated algorithms may have been removed.
- **Lockfile churn:** sequential commits on a single branch keep lockfile conflicts unlikely. If they arise mid-phase, rebase rather than regenerate.

## Rollback

- Per-sub-phase commits are small and self-contained → `git revert <sha>` is the default rollback.
- If a phase has already merged to `platform-multi-tenant` and downstream problems surface, revert the merge commit.
- The worktree can be discarded at any time without affecting `platform-multi-tenant`.

## Follow-ups

These three migrations are **not** part of this project. Each gets its own design + plan when prioritized. They are named here so they are not forgotten.

| Migration | Priority | Planned spec path |
|---|---|---|
| Tailwind CSS 3 → 4 (+ `tailwind-merge` 2 → 3) | **Next** — begin immediately after Phase 2 validates | `docs/superpowers/specs/YYYY-MM-DD-tailwind-4-migration-design.md` |
| Frontend TypeScript cleanup | Queued — after dep-upgrade project wraps (post-Phase 3 merge). 267 errors across 90 files in the baseline (pre-existing as of Phase 2c). Scope includes re-evaluating deprecated `target: es5` and `baseUrl` now deferred via `ignoreDeprecations: "6.0"` (TS 7.0 will remove them). Start with a classification spike to decide single-spec vs. multi-spec. | `docs/superpowers/specs/YYYY-MM-DD-frontend-typescript-cleanup-design.md` |
| bcrypt 4 → 5 (blocked on passlib) | Discovered during Phase 3b. `passlib==1.7.4` (last release 2020) is incompatible with bcrypt 5: it reads the removed `bcrypt.__about__.__version__` attribute and its `detect_wrap_bug` initialization probe triggers bcrypt 5's new 72-byte password-length check. Unblocking requires replacing passlib with either direct `bcrypt` calls or `pwdlib` (modern drop-in). Auth-refactor project, not a dep bump. | `docs/superpowers/specs/YYYY-MM-DD-auth-passlib-replacement-design.md` |
| pillow 11 → 12 (blocked on docling/mcp cascade) | Discovered during Phase 3c. pillow 12 requires docling ≥ 2.74, which in turn pulls constraints on mcp, astra-assistants, and httpx that cascade into an unresolvable graph on this workspace (the `langflow-base` mcp≥1.17 floor conflicts with astra-assistants httpx constraints on the docling-2.74+ path). Unblocking needs a coordinated bump of docling + docling-core + astra-assistants + possibly langchain-docling, potentially also easing the `<3.0.0` caps. | `docs/superpowers/specs/YYYY-MM-DD-docling-ecosystem-bump-design.md` |
| LangChain 0.3 → 1.x ecosystem | When prioritized | `docs/superpowers/specs/YYYY-MM-DD-langchain-1-migration-design.md` |
| Pandas 2 → 3 | When prioritized | `docs/superpowers/specs/YYYY-MM-DD-pandas-3-migration-design.md` |

For Tailwind 4 specifically: run `npx @tailwindcss/upgrade` as a spike first to assess real scope. The current configuration is 543 lines of `tailwind.config.mjs` + 357 `@apply`/`@layer` uses in `src/style/applies.css` — non-trivial translation to CSS-first `@theme`.
