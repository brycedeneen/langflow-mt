<!-- markdownlint-disable MD030 -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/static/img/langflow-logo-color-blue-bg.svg">
  <img src="./docs/static/img/langflow-logo-color-black-solid.svg" alt="Langflow logo">
</picture>

ADP fork of [Langflow](https://github.com/langflow-ai/langflow) — adds multi-tenant orgs, template management, Data Mapper, ADP Assist, and a distributed (Arq + Redis) flow-execution runtime. The effective main branch is `platform-multi-tenant`.

This README covers how to run and deploy this fork. For feature docs, see the spec tree under `docs/superpowers/specs/`.

## Services in this fork

| Service | What it is | Default port | Depends on |
|---|---|---|---|
| Backend API (`langflow run` / `make backend`) | FastAPI app, flow runtime, REST API | `7860` | Postgres, Redis (if distributed execution is on) |
| Frontend (`make frontend`) | Vite/React UI | `3000` (dev) | Backend |
| Worker (`uv run langflow worker`) | Arq consumer for webhook/schedule/MCP flow runs | n/a | Redis, Postgres |
| Redis | Arq broker + cache + concurrency signals | `6379` | — |
| Postgres | Primary database (SQLite fallback for local) | `5432` | — |

See [`deploy/README.md`](./deploy/README.md) for the full deployment reference (env vars, docker-compose, queue topology).

## Running locally

Three terminals, one command each. This is the exact flow used in development.

### 0. Prerequisites

- Python 3.11+ (floor was raised from 3.10 for the pandas 3.0 bump) and [uv](https://docs.astral.sh/uv/)
- Node.js 18+ and npm
- A running Redis (`brew services start redis` or `docker run -p 6379:6379 redis:7`)
- A running Postgres (optional; SQLite is the default fallback)
- A `.env` file at the repo root — copy `.env.example` and fill in at least `LANGFLOW_DATABASE_URL`, `LANGFLOW_REDIS_URL`, and `LANGFLOW_DISTRIBUTED_EXECUTION=true`

First-time only:
```shell
make init
```

### 1. Backend (`:7860`)

```shell
make backend env=.env
```

Runs uvicorn against `langflow.main:create_app`. Reads the `.env` file passed in, so all `LANGFLOW_*` vars apply. Override port with `port=8080`, workers with `workers=4`, etc. See the [backend README](./src/backend/base/README.md).

### 2. Frontend (`:3000`)

```shell
make frontend
```

Installs deps and runs `npm start`. Proxies API calls to the backend via `BACKEND_URL` (default `http://localhost:7860`). See the [frontend README](./src/frontend/README.md).

### 3. Worker (task runner)

```shell
uv run langflow worker --queue runs:default --concurrency 8
```

Arq worker that executes webhook/schedule/MCP-triggered flow runs out-of-process. **Requires Redis** (via `LANGFLOW_REDIS_URL`) and the same Postgres the backend uses. Run one process per queue — see [`deploy/README.md`](./deploy/README.md#workers-task-runner) for the full queue list and horizontal-scaling notes.

## Deploying

The canonical deployment is `deploy/docker-compose.yml` (Traefik + backend + frontend + Postgres + Redis + 3 workers + optional pgadmin/prometheus/grafana). Start there:

```shell
cd deploy
cp .env.example .env   # edit values first
docker compose up
```

Full env-var table, port map, and horizontal-scaling guidance live in [`deploy/README.md`](./deploy/README.md).

## Project layout

| Path | Purpose |
|---|---|
| `src/backend/base/` | `langflow-base` package — FastAPI app, services, CLI, workers, Alembic migrations |
| `src/lfx/` | `lfx` package — graph engine, components, `lfx serve/run` CLI, worker settings |
| `src/frontend/` | React UI (Vite, Tailwind v4) |
| `src/sdk/` | Python SDK for calling deployed flows |
| `deploy/` | Production docker-compose stack |
| `docker/` | Dockerfiles + dev compose variants |
| `docker_example/` | Minimal single-container example |
| `docs/` | Docusaurus site + spec tree |

## Further reading

- [`AGENTS.md`](./AGENTS.md) — contributor/AI-agent context (authoritative)
- [`DEVELOPMENT.md`](./DEVELOPMENT.md) — upstream dev notes
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — upstream contribution flow (note: this fork does not PR upstream)
- [`deploy/README.md`](./deploy/README.md) — deployment reference
- [`src/backend/base/README.md`](./src/backend/base/README.md) — backend dev/deploy
- [`src/frontend/README.md`](./src/frontend/README.md) — frontend dev/deploy
- [`src/lfx/README.md`](./src/lfx/README.md) — `lfx` CLI + worker
