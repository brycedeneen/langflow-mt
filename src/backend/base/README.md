# langflow-base

The `langflow-base` package — FastAPI app, REST API, database models/migrations, CLI (`langflow run`, `langflow worker`, `langflow superuser`, `langflow set-platform-admin`), services wiring, and distributed worker code.

This is what the `langflowai/langflow-backend` Docker image ships.

## Running in dev

From the **repo root** (not this directory):

```shell
make backend env=.env
```

What it does:
- Re-installs backend deps (`uv sync --frozen --extra postgresql`)
- Kills any process on `:7860`
- Starts uvicorn against `langflow.main:create_app` using the `.env` file you pass
- Reloads on code change (`--reload` unless `workers>1`)

Overridable make vars:

| Var | Default | Effect |
|---|---|---|
| `env` | `.env` | Path to env file |
| `host` | `0.0.0.0` | Bind host |
| `port` | `7860` | Bind port |
| `workers` | `1` | Uvicorn worker count (disables `--reload` when >1) |
| `login` | unset | If set to `true`/`false`, forces `LANGFLOW_AUTO_LOGIN` for this run |

Example:
```shell
make backend env=.env port=8080 workers=4
```

### Dependencies

- Python **>=3.11** (the pandas-3.0 bump raised the floor on 2026-04-20)
- [uv](https://docs.astral.sh/uv/)
- **Postgres** (prod) via `LANGFLOW_DATABASE_URL` — or SQLite for solo dev
- **Redis** if `LANGFLOW_DISTRIBUTED_EXECUTION=true` or `LANGFLOW_CACHE_TYPE=redis`

### Environment variables

The backend reads all config from env vars with the `LANGFLOW_` prefix. Full table lives in [`deploy/README.md`](../../../deploy/README.md#environment-variables). The variables you're most likely to set locally:

```dotenv
# Database
LANGFLOW_DATABASE_URL=postgresql+psycopg://langflow:langflow@localhost:5432/langflow

# Distributed execution (required when running a worker)
LANGFLOW_DISTRIBUTED_EXECUTION=true
LANGFLOW_REDIS_URL=redis://localhost:6379/0

# Auth — fine as-is for solo dev; lock down in prod
LANGFLOW_AUTO_LOGIN=true
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=admin

# Logging
LANGFLOW_LOG_LEVEL=debug

# Optional: serve a prebuilt frontend
# LANGFLOW_FRONTEND_PATH=/abs/path/to/src/frontend/build
```

## Running the distributed worker

The `langflow worker` CLI is defined in this package (`langflow/cli/worker_cmd.py`) and runs an Arq worker bound to `WorkerSettings` (`langflow/worker_app/settings.py`). See the root [README](../../../README.md#3-worker-task-runner) and [`deploy/README.md`](../../../deploy/README.md#workers-task-runner) for queue topology.

```shell
uv run langflow worker --queue runs:default --concurrency 8
```

## Database migrations (Alembic)

Alembic config lives at `langflow/alembic/`. Run from repo root:

```shell
make alembic-upgrade                                   # upgrade to head
make alembic-revision message="short description"     # autogenerate a new migration
make alembic-current                                   # current revision
make alembic-history                                   # full history
make alembic-downgrade                                 # -1 step (dev only)
```

Migrations are authoritative: the backend does not run `create_all` in prod. Ship schema changes via Alembic and roll the backend first, then workers.

## Building

```shell
make build main=1     # builds langflow (top-level) + langflow-base
make build base=1     # builds langflow-base only
```

Wheels land in `dist/` and `src/backend/base/dist/`.

## Tests

From the repo root:

```shell
make unit_tests                    # backend unit tests
make integration_tests             # integration (needs DB, Redis)
make integration_tests_no_api_keys # integration excluding API-key-dependent tests
make template_tests                # starter-project template tests
```

## Package layout

| Path | What it does |
|---|---|
| `langflow/main.py` | `create_app()` — the FastAPI factory used by uvicorn |
| `langflow/cli/` | Typer commands exposed on `langflow ...` |
| `langflow/api/v1/`, `api/v2/` | REST routes |
| `langflow/services/` | DI container: DB, auth, settings, storage, runs, etc. |
| `langflow/worker_app/` | Arq worker bootstrap, execute/reaper/retention/webhook jobs |
| `langflow/alembic/` | Migrations + `alembic.ini` |
| `langflow/initial_setup/` | Seed data (starter projects, etc.) |
| `langflow/components/` | Built-in components exposed in the UI |

## Related docs

- [`deploy/README.md`](../../../deploy/README.md) — production deployment, full env var table
- [`src/lfx/README.md`](../../lfx/README.md) — graph engine and `lfx` CLI
- [`src/frontend/README.md`](../../frontend/README.md) — UI
