# Deploying Langflow (ADP fork)

Production-style deployment of the `platform-multi-tenant` fork via Docker Compose. The stack adds distributed flow execution (Taskiq + Redis), a singleton scheduler process for cron jobs and delayed-enqueue draining, and multi-worker scale-out on top of the upstream single-container image.

## Stack at a glance

```
            ┌────────────┐
            │  Traefik   │  :80/:443   (TLS + routing)
            └──────┬─────┘
                   │
       ┌───────────┼───────────────┐
       │                           │
┌──────▼───────┐          ┌────────▼────────┐
│   Frontend   │          │   Backend API   │  :7860
│  (Vite SPA)  │          │    (FastAPI)    │
└──────────────┘          └──┬──────────┬───┘
                             │          │
                    ┌────────▼──┐   ┌───▼──────────────┐
                    │ Postgres  │   │  Redis (broker   │  :6379
                    │   :5432   │   │  + cache + sigs) │
                    └────┬──────┘   └────┬─────────────┘
                         │               │
              ┌──────────┼───────────────┼──────────┬──────────────┐
              │          │               │          │              │
        ┌─────▼────┐ ┌───▼────┐   ┌──────▼─────┐  ┌─▼─────────┐  ┌─▼──────────┐
        │ worker   │ │ worker │   │   worker   │  │  worker   │  │ scheduler  │
        │ default  │ │  high  │   │  webhooks  │  │   low     │  │ (singleton)│
        │ (8/proc) │ │(4/proc)│   │ (16/proc)  │  │ (optional)│  │            │
        └──────────┘ └────────┘   └────────────┘  └───────────┘  └────────────┘
```

The backend enqueues webhook/schedule/MCP-triggered flow runs to Taskiq; workers pick them up and write results back to Postgres. A separate **scheduler** process fires cron jobs and drains delayed-enqueue ZSETs (auto-retry, webhook backoff). Without distributed execution, runs stay in-process on the API pod.

## Dependent technologies

| Tech | Required? | Purpose | How it's wired |
|---|---|---|---|
| **Postgres 15+** | Required (SQLite works for local only) | Primary DB: users, flows, orgs, memberships, templates, categories, flow_runs, variables, api_keys | `LANGFLOW_DATABASE_URL` |
| **Redis 6+** | Required when `LANGFLOW_DISTRIBUTED_EXECUTION=true` (always, for the worker path). Also used when `LANGFLOW_CACHE_TYPE=redis` | Taskiq broker, delayed-enqueue ZSETs, Langflow cache backend, concurrency/cancel signals between API and workers | `LANGFLOW_REDIS_URL` (workers + scheduler), `LANGFLOW_REDIS_HOST/PORT/DB` (cache) |
| **Traefik** | Optional | TLS termination + routing in the bundled compose | Labels on each service |
| **Prometheus + Grafana** | Optional | Metrics and dashboards | Metrics exposed on `:9090` under `/metrics` |
| **pgAdmin** | Optional | DB admin UI | `pgadmin.${DOMAIN}` |

## Quickstart (Docker Compose)

```shell
cd deploy
cp .env.example .env
$EDITOR .env            # fill in DOMAIN, SUPERUSER creds, DB password, etc.
docker compose pull
docker compose up -d
```

Defaults expose the stack at `http://localhost` (Traefik on `:80/:443`). For a port-mapped dev variant (no Traefik) see `docker/dev.docker-compose.yml`.

## Ports and URLs

| Service | Container port | Exposed how | URL/binding |
|---|---|---|---|
| Traefik | `80`, `443` | Host | `http://${DOMAIN}`, `https://${DOMAIN}` |
| Backend | `7860` | Behind Traefik | Paths: `/api/v1`, `/api/v2`, `/docs`, `/health` |
| Frontend | `80` | Behind Traefik | Path: `/` |
| Redis | `6379` | Mapped to host in compose | `redis://result_backend:6379/0` (inside network) |
| Postgres | `5432` | Internal only | `postgresql://db:5432/langflow` (inside network) |
| pgAdmin | `5050` | Behind Traefik | `https://pgadmin.${DOMAIN}` |
| Prometheus | `9090` | Behind Traefik | Path: `/metrics` |
| Grafana | `3000` | Behind Traefik | Path: `/grafana` |

## Workers (task runner)

Workers run the `langflow worker` CLI (Taskiq under the hood). The compose file ships three worker services, one per production queue:

| Queue | Purpose | Default concurrency | What lands here |
|---|---|---|---|
| `runs:default` | Normal flow runs | `8` | Most MCP/schedule jobs |
| `runs:high` | Latency-sensitive runs | `4` | Flows marked high priority |
| `runs:low` | Best-effort / bulk runs | `8` (not in default compose) | Retention sweeps, backfills |
| `webhooks` | Inbound webhook deliveries | `16` | Webhook trigger + per-flow dispatch |

### Starting a worker

```shell
uv run langflow worker --queue runs:default --concurrency 8
```

Each process polls **one** queue. To serve multiple queues, run multiple processes — or replicate the service in compose:

```yaml
langflow-worker-default:
  image: langflowai/langflow-backend:latest
  command: ["langflow", "worker", "--queue", "runs:default", "--concurrency", "8"]
  env_file: [.env]
  environment:
    - LANGFLOW_DISTRIBUTED_EXECUTION=true
    - LANGFLOW_REDIS_URL=redis://result_backend:6379/0
  deploy:
    replicas: 3    # scale horizontally
```

Workers must share `LANGFLOW_DATABASE_URL` and `LANGFLOW_REDIS_URL` with the backend. They run their own Alembic state check on startup; run migrations from the backend (`alembic upgrade head`) before rolling workers.

## Scheduler (singleton)

A single **scheduler** process complements the API + workers. It runs the `langflow scheduler` CLI and is responsible for:

- **Cron jobs**: run reaper, retention sweep, audit-log cleanup, pricing/cost refresh.
- **Delayed-enqueue draining**: moving messages from the `delay:*` Redis ZSETs onto their target queues when their scheduled time arrives. Producers of delayed work include auto-retry (failed runs), webhook delivery backoff, and any future scheduled enqueues.

### Singleton constraint

The scheduler **must** run with `replicas: 1`. Two scheduler processes will fire every cron job twice and double-drain delayed messages. If you're on Kubernetes, do not configure HPA/KEDA for the scheduler Deployment.

```shell
uv run langflow scheduler
```

```yaml
langflow-scheduler:
  image: langflowai/langflow-backend:latest
  command: ["langflow", "scheduler"]
  env_file: [.env]
  environment:
    - LANGFLOW_DISTRIBUTED_EXECUTION=true
    - LANGFLOW_REDIS_URL=redis://result_backend:6379/0
  deploy:
    replicas: 1    # never scale up
```

### Failure mode

If the scheduler is down:

- Cron jobs **stop firing** until it returns (no reaper, no retention deletes, no pricing refresh).
- Delayed retries that producers enqueue (auto-retry, webhook backoff) **accumulate** in the `delay:*` Redis ZSETs. They are not lost — the next time the scheduler comes up it drains the backlog and any due messages are dispatched.
- The API and workers keep serving real-time work; only deferred and scheduled work pauses.

Restart promptness matters more than redundancy here: keep the pod's restart policy aggressive and alert on extended downtime.

## Environment variables

Only the vars that actually affect deployment are listed. All backend/worker vars use the `LANGFLOW_` prefix via pydantic-settings.

### Core backend

| Var | Required | Default | Description |
|---|---|---|---|
| `LANGFLOW_DATABASE_URL` | Yes (prod) | `sqlite:///./langflow.db` | Postgres DSN, e.g. `postgresql+psycopg://user:pass@db:5432/langflow`. SQLite is fine for solo dev only. |
| `LANGFLOW_CONFIG_DIR` | No | `~/.langflow` | Where logs, file storage, secret key, and RSA keys are persisted |
| `LANGFLOW_HOST` | No | `localhost` | Bind host for uvicorn |
| `LANGFLOW_PORT` | No | `7860` | Bind port |
| `LANGFLOW_WORKERS` | No | `1` | Uvicorn worker processes (unrelated to Taskiq workers) |
| `LANGFLOW_LOG_LEVEL` | No | `info` | `debug` / `info` / `warning` / `error` / `critical` |
| `LANGFLOW_FRONTEND_PATH` | No | bundled | Override to serve a custom frontend build |
| `LANGFLOW_DATABASE_CONNECTION_RETRY` | No | `false` | Retry DB connect on startup failure |

### Authentication

| Var | Required | Default | Description |
|---|---|---|---|
| `LANGFLOW_SECRET_KEY` | Recommended (prod) | auto-generated and persisted to `CONFIG_DIR/secret_key` | HS256 signing key for JWTs. Provide explicitly so it's stable across restarts. |
| `LANGFLOW_ALGORITHM` | No | `HS256` | `HS256`, `RS256`, or `RS512`. RS* auto-manages RSA keys in `CONFIG_DIR`. |
| `LANGFLOW_PRIVATE_KEY` / `LANGFLOW_PUBLIC_KEY` | No | auto-generated | PEM-encoded RSA keys for RS256/RS512 |
| `LANGFLOW_SUPERUSER` | **Yes** | — | Bootstrap admin username. The application fails to start without this. |
| `LANGFLOW_SUPERUSER_PASSWORD` | **Yes** | — | Bootstrap admin password. The application fails to start without this. |
| `LANGFLOW_NEW_USER_IS_ACTIVE` | No | `false` | Whether self-registered users start active |
| `LANGFLOW_ENABLE_SUPERUSER_CLI` | No | `true` | **Set to `false` in production.** Gates the `langflow superuser` CLI. |
| `LANGFLOW_API_KEY_SOURCE` | No | `db` | `db` validates against the api_keys table; `env` validates against `LANGFLOW_API_KEY` |
| `LANGFLOW_API_KEY` | Only if `API_KEY_SOURCE=env` | — | Static API key (for Kubernetes Secrets / CI) |
| `LANGFLOW_WEBHOOK_AUTH_ENABLE` | No | `false` | Require API-key on webhook endpoints |
| `LANGFLOW_SSO_ENABLED` | No | `false` | Toggle SSO (JWT/OIDC/SAML/LDAP) |
| `LANGFLOW_SSO_PROVIDER` | No | `jwt` | `jwt`, `oidc`, `saml`, `ldap` |
| `LANGFLOW_SSO_CONFIG_FILE` | If SSO on | — | Path to SSO YAML config inside the container |

### Distributed execution (Taskiq + Redis)

| Var | Required | Default | Description |
|---|---|---|---|
| `LANGFLOW_DISTRIBUTED_EXECUTION` | Yes for worker path | `false` | Must be `true` on **all** of backend, worker, and scheduler services. When false, runs stay in-process. |
| `LANGFLOW_REDIS_URL` | Yes for worker path | `redis://localhost:6379/0` | Taskiq broker DSN. Use the same value across API, all worker services, and the scheduler. |
| `LANGFLOW_WORKER_CONCURRENCY` | No | `8` | Max in-flight jobs per worker process (override with `--concurrency`) |
| `LANGFLOW_QUEUE_DEFAULT` | No | `runs:default` | Rename the default queue |
| `LANGFLOW_QUEUE_HIGH` | No | `runs:high` | Rename the high-priority queue |
| `LANGFLOW_QUEUE_LOW` | No | `runs:low` | Rename the low-priority queue |
| `LANGFLOW_QUEUE_WEBHOOKS` | No | `webhooks` | Rename the webhook queue |
| `LANGFLOW_RUN_DEFAULT_TIMEOUT_SECONDS` | No | `600` | Per-run timeout fallback |
| `LANGFLOW_RUN_RETENTION_HOURS` | No | `24` | How long `flow_runs` rows are kept before the retention cron deletes them |

The Taskiq broker uses Redis lists named directly after the queue (e.g., `runs:default`, `runs:high`, `webhooks`). Inspect with `redis-cli LLEN runs:default`. Delayed/scheduled messages live in companion ZSETs at `delay:<queue_name>` (e.g., `delay:webhooks`); the scheduler drains them as they come due.

### Cache (orthogonal to Taskiq)

| Var | Required | Default | Description |
|---|---|---|---|
| `LANGFLOW_CACHE_TYPE` | No | `memory` | `memory`, `async`, or `redis` |
| `LANGFLOW_REDIS_HOST` | If `CACHE_TYPE=redis` | `localhost` | |
| `LANGFLOW_REDIS_PORT` | If `CACHE_TYPE=redis` | `6379` | |
| `LANGFLOW_REDIS_DB` | No | `0` | |
| `LANGFLOW_REDIS_CACHE_EXPIRE` | No | `3600` | TTL in seconds |
| `LANGFLOW_REDIS_PASSWORD` | No | — | |

### Frontend (build- or runtime-injected)

| Var | Required | Default | Description |
|---|---|---|---|
| `BACKEND_URL` | Yes | — | URL the frontend container uses to reach the API, e.g. `http://backend:7860` inside compose, or the public API host in prod |

### Compose-level (for `deploy/docker-compose.yml`)

| Var | Required | Default | Description |
|---|---|---|---|
| `DOMAIN` | Yes | `localhost` | Base host for Traefik rules |
| `STACK_NAME` | Yes | `langflow-stack` | Traefik label prefix |
| `TRAEFIK_PUBLIC_NETWORK` | Yes | `traefik-public` | External Docker network for Traefik |
| `TRAEFIK_TAG` / `TRAEFIK_PUBLIC_TAG` | Yes | `langflow-traefik` / `traefik-public` | Constraint labels |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Yes | `langflow` / `langflow` / `langflow` | Postgres bootstrap |
| `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` | If running pgAdmin | `admin@admin.com` / `admin` | pgAdmin login |

See `deploy/.env.example` for the full canonical list with defaults.

## Rolling out changes

1. Run `alembic upgrade head` from the backend image (or from a one-shot job) before deploying new backend/worker/scheduler images — schema is shared.
2. Deploy the backend image first; it's the authoritative migrator.
3. Roll worker replicas after the backend is healthy. Workers that see a schema newer than they know will fail fast; that's intentional.
4. Restart the scheduler after the workers are up so cron jobs and delayed-enqueue draining resume against the new image.
5. Frontend is static and can be deployed in any order relative to the backend, as long as the API contract is stable.

## Migration from arq (Taskiq cutover)

The fork moved from arq to Taskiq for the distributed-execution layer. The cutover is in-place — the queue names and Redis DSN are unchanged, but the on-wire message format and the Redis key layout are different, so a clean cutover order matters.

### Deployment order

1. **Build a new image** containing the Taskiq codebase (worker entrypoint + scheduler).
2. **Deploy the scheduler first** (`replicas: 1`). It registers cron jobs and starts draining the new `delay:*` ZSETs immediately so backlog from the previous image doesn't pile up.
3. **Upgrade the worker Deployment(s)** next, one queue at a time. Each new-image worker reads from `<queue_name>` lists; pre-cutover messages still in `arq:queue:*` are not consumed.
4. **Upgrade the API Deployment** last. After this rollout, all newly produced messages target the Taskiq layout.
5. **Drain leftover arq keys.** Once the API is on the new image and you've verified workers are processing fresh runs, delete the abandoned arq keys:

   ```shell
   redis-cli DEL \
     arq:queue:runs:high \
     arq:queue:runs:default \
     arq:queue:runs:low \
     arq:queue:webhooks
   ```

   (Add any custom queue names you renamed via `LANGFLOW_QUEUE_*`.)

If you need to roll back, deploy the previous image to scheduler → workers → API in the same order. Any messages enqueued during the Taskiq window will not be picked up by an arq worker and must be redelivered by the producing system (webhook source, schedule, etc.).

## Alternative dev stacks

- **Single-container demo**: `docker_example/docker-compose.yml` — backend + Postgres only, no workers or Redis. Good for UI walkthroughs.
- **Dev compose**: `docker/dev.docker-compose.yml` — hot-reload backend + frontend, mounts source. Start with `make dcdev_up`.
- **Bare-metal dev** (3 terminals, no Docker): see the root [`README.md`](../README.md#running-locally).
