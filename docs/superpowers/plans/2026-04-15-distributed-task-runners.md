# Distributed Task Runners Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** ✅ 151/156 checkboxes ticked. The remaining 5 unchecked items are all under Task 30 (Helm chart) which is **deferred cross-repo** — the worker-deployment + KEDA ScaledObject YAML belongs in the separate Helm repo, and starter templates sit at `deploy/helm/worker-starter/` in-tree as a handoff. Task 32 E2E smoke shipped at `src/backend/tests/integration/e2e/test_runs_e2e.py`. No further work in this repo.

**Goal:** Execute non-interactive flow runs out-of-process on an Arq-based worker fleet with per-org concurrency caps, priority queues, durable run state, polling API, and signed webhooks.

**Architecture:** Single Docker image, two entrypoints (`langflow run` for API, `langflow worker` for the Arq worker + internal crons). API enqueues `flow_runs` rows into one of three Redis priority queues; workers dequeue, check per-org concurrency via a Redis Lua script, execute the graph via the existing `run_graph_internal`, write terminal state, and emit signed webhooks. Editor/playground traffic (`/api/v1/run`) continues in-process unchanged.

**Tech Stack:** SQLModel, FastAPI, Typer, Alembic, asyncio, Arq (Redis-backed async queue), Redis, Postgres, httpx (webhook delivery), prometheus-client (metrics), KEDA (autoscaling).

**Spec:** `docs/superpowers/specs/2026-04-15-distributed-task-runners-design.md`

**Terminology note:** The spec uses "tenant". The code uses `organization` (from the multi-tenant foundation merged 2026-04-15). This plan uses `organization_id` / `org` throughout to match the schema. "Tenant" in the spec = "organization" here.

---

## Phase 1 — Foundations: Dependencies, Settings, Schema

### Task 1: Swap `celery` for `arq` in pyproject + add `prometheus-client` + `httpx`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/backend/base/pyproject.toml` (if the base package has its own)

- [x] **Step 1: Inspect current dependency section**

Run: Read `pyproject.toml` and find the `[project]` or `[tool.poetry.dependencies]` section listing `celery`.

- [x] **Step 2: Replace celery with arq; add prometheus-client; ensure httpx present**

In `pyproject.toml` dependencies list:
- Remove: `celery[redis] = "..."` (or equivalent pin)
- Add: `arq = "^0.26"`
- Add: `prometheus-client = "^0.20"`
- Ensure: `httpx` is already present (Langflow uses it; add if missing as `"^0.27"`)

Do the same edit in `src/backend/base/pyproject.toml` if that file also lists celery.

- [x] **Step 3: Regenerate the lockfile**

Run: `uv lock` (or `poetry lock --no-update` if the project uses Poetry — check the lockfile extension first).
Expected: Lockfile updates, no resolution errors.

- [x] **Step 4: Verify install**

Run: `uv sync` (or `poetry install`).
Expected: `arq`, `prometheus-client`, `httpx` installed; `celery` gone.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml src/backend/base/pyproject.toml uv.lock
git commit -m "build(runs): swap celery for arq; add prometheus-client"
```

---

### Task 2: Add settings for distributed execution

**Files:**
- Modify: `src/lfx/src/lfx/services/settings/base.py`

- [x] **Step 1: Write a failing test for the new settings fields**

Create `src/backend/tests/unit/test_settings_runs.py`:

```python
from lfx.services.settings.base import Settings

def test_runs_settings_defaults():
    s = Settings(_env_file=None)
    assert s.distributed_execution is False
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.arq_default_queue == "runs:default"
    assert s.arq_high_queue == "runs:high"
    assert s.arq_low_queue == "runs:low"
    assert s.arq_webhooks_queue == "webhooks"
    assert s.worker_concurrency == 8
    assert s.run_retention_hours == 24
    assert s.run_payload_inline_max_bytes == 1 * 1024 * 1024
    assert s.run_logs_max_bytes == 10 * 1024 * 1024
    assert s.run_default_timeout_seconds == 600
    assert s.org_default_max_concurrent_runs == 5
```

- [x] **Step 2: Run the test — must fail**

Run: `pytest src/backend/tests/unit/test_settings_runs.py -v`
Expected: FAIL (`AttributeError` on first missing attribute).

- [x] **Step 3: Add the settings fields**

In `src/lfx/src/lfx/services/settings/base.py`, inside the `Settings` class:

```python
# Distributed flow execution (Arq)
distributed_execution: bool = False
"""Enable dispatching webhook/schedule/MCP-triggered flow runs to Arq workers. When False, the legacy in-process path is used."""

redis_url: str = "redis://localhost:6379/0"
"""Redis connection URL used by Arq (broker) and concurrency/cancel signals."""

arq_high_queue: str = "runs:high"
arq_default_queue: str = "runs:default"
arq_low_queue: str = "runs:low"
arq_webhooks_queue: str = "webhooks"

worker_concurrency: int = 8
"""Max in-flight flow runs per worker process."""

run_default_timeout_seconds: int = 600
"""Default per-run timeout when a flow does not specify one."""

run_retention_hours: int = 24
"""Hours to retain finished flow_runs rows before the retention job deletes them."""

run_payload_inline_max_bytes: int = 1 * 1024 * 1024
"""Inputs/result larger than this are offloaded to object storage."""

run_logs_max_bytes: int = 10 * 1024 * 1024
"""Per-run cap on captured execution logs (bytes)."""

org_default_max_concurrent_runs: int = 5
"""Default per-organization concurrent run cap when not overridden."""
```

- [x] **Step 4: Run the test — must pass**

Run: `pytest src/backend/tests/unit/test_settings_runs.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/services/settings/base.py src/backend/tests/unit/test_settings_runs.py
git commit -m "feat(runs): add settings for distributed execution"
```

---

### Task 3: Add per-organization concurrency/priority columns

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/organization/model.py` (verify exact path — created in `6d926936ec2d_multi_tenant_foundation.py`)
- Create: `src/backend/base/langflow/alembic/versions/{newrev}_organization_runs_limits.py`

- [x] **Step 1: Confirm the organization model path**

Run: `ls src/backend/base/langflow/services/database/models/organization/`
Expected: a `model.py` (or similar) containing `Organization`.

- [x] **Step 2: Write a failing model test**

Create `src/backend/tests/unit/models/test_organization_runs_fields.py`:

```python
from langflow.services.database.models.organization.model import Organization

def test_organization_runs_fields_exist():
    fields = Organization.model_fields
    assert "runs_max_concurrent" in fields
    assert "runs_priority_tier" in fields
```

- [x] **Step 3: Run the test — must fail**

Run: `pytest src/backend/tests/unit/models/test_organization_runs_fields.py -v`
Expected: FAIL.

- [x] **Step 4: Add fields to the Organization model**

In the `Organization` class (the `table=True` one):

```python
from sqlmodel import Field
import sqlalchemy as sa

runs_max_concurrent: int = Field(default=5, sa_column_kwargs={"server_default": "5"})
runs_priority_tier: str = Field(default="default", sa_column_kwargs={"server_default": "default"})
```

If the codebase uses an enum elsewhere, define:

```python
class RunsPriorityTier(str, Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"
```

And type the field `runs_priority_tier: RunsPriorityTier = Field(default=RunsPriorityTier.DEFAULT, ...)`.

- [x] **Step 5: Generate Alembic migration**

Run: `cd src/backend/base && alembic revision -m "organization runs limits"`
Expected: A new file in `langflow/alembic/versions/` with `revision` set.

Edit it:

```python
def upgrade() -> None:
    with op.batch_alter_table("organization") as batch_op:
        batch_op.add_column(sa.Column("runs_max_concurrent", sa.Integer(), nullable=False, server_default="5"))
        batch_op.add_column(sa.Column("runs_priority_tier", sa.String(length=16), nullable=False, server_default="default"))

def downgrade() -> None:
    with op.batch_alter_table("organization") as batch_op:
        batch_op.drop_column("runs_priority_tier")
        batch_op.drop_column("runs_max_concurrent")
```

- [x] **Step 6: Apply migration locally**

Run: `cd src/backend/base && alembic upgrade head`
Expected: Migration applies without error.

- [x] **Step 7: Run model + migration tests**

Run: `pytest src/backend/tests/unit/models/test_organization_runs_fields.py -v`
Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add src/backend/base/langflow/services/database/models/organization/model.py \
        src/backend/base/langflow/alembic/versions/*organization_runs_limits*.py \
        src/backend/tests/unit/models/test_organization_runs_fields.py
git commit -m "feat(runs): org-level concurrency and priority tier"
```

---

### Task 4: Add per-flow run-config columns

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py`
- Create: `src/backend/base/langflow/alembic/versions/{newrev}_flow_run_config.py`

- [x] **Step 1: Write a failing model test**

Create `src/backend/tests/unit/models/test_flow_run_config.py`:

```python
from langflow.services.database.models.flow.model import Flow

def test_flow_run_config_fields():
    fields = Flow.model_fields
    for name in ("webhook_url", "webhook_secret", "auto_retry", "max_retries", "timeout_seconds"):
        assert name in fields, f"missing {name}"
```

- [x] **Step 2: Run the test — must fail**

Run: `pytest src/backend/tests/unit/models/test_flow_run_config.py -v`
Expected: FAIL.

- [x] **Step 3: Add fields on `FlowBase`**

In `flow/model.py`, add to `FlowBase`:

```python
webhook_url: str | None = Field(default=None, description="URL to POST webhook events to")
webhook_secret: str | None = Field(default=None, description="HMAC secret; auto-generated when webhook_url first set")
auto_retry: bool = Field(default=False, sa_column_kwargs={"server_default": sa.false()})
max_retries: int = Field(default=3, sa_column_kwargs={"server_default": "3"})
timeout_seconds: int = Field(default=600, sa_column_kwargs={"server_default": "600"})
```

- [x] **Step 4: Generate migration**

Run: `cd src/backend/base && alembic revision -m "flow run config"`

Edit:

```python
def upgrade() -> None:
    with op.batch_alter_table("flow") as batch_op:
        batch_op.add_column(sa.Column("webhook_url", sa.String(length=2048), nullable=True))
        batch_op.add_column(sa.Column("webhook_secret", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("auto_retry", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="600"))

def downgrade() -> None:
    with op.batch_alter_table("flow") as batch_op:
        for col in ("timeout_seconds", "max_retries", "auto_retry", "webhook_secret", "webhook_url"):
            batch_op.drop_column(col)
```

- [x] **Step 5: Apply, run tests**

Run: `cd src/backend/base && alembic upgrade head && cd - && pytest src/backend/tests/unit/models/test_flow_run_config.py -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/database/models/flow/model.py \
        src/backend/base/langflow/alembic/versions/*flow_run_config*.py \
        src/backend/tests/unit/models/test_flow_run_config.py
git commit -m "feat(runs): per-flow run config (webhook, retries, timeout)"
```

---

### Task 5: Create `FlowRun` model + table

**Files:**
- Create: `src/backend/base/langflow/services/database/models/flow_run/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/flow_run/model.py`
- Create: `src/backend/base/langflow/alembic/versions/{newrev}_create_flow_runs.py`
- Create: `src/backend/tests/unit/models/test_flow_run.py`

- [x] **Step 1: Write failing model test**

In `test_flow_run.py`:

```python
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy

def test_flow_run_status_enum():
    assert {s.value for s in RunStatus} == {
        "queued", "running", "succeeded", "failed", "cancelled", "timed_out",
    }

def test_flow_run_triggered_by_enum():
    assert {t.value for t in TriggeredBy} == {"api", "webhook", "schedule", "mcp"}

def test_flow_run_fields():
    required = {
        "id", "organization_id", "flow_id", "triggered_by", "actor_id",
        "status", "priority", "inputs", "inputs_ref", "result", "result_ref",
        "error", "auto_retry", "max_retries", "attempt", "cancel_requested",
        "timeout_seconds", "worker_id", "heartbeat_at", "queued_at",
        "started_at", "finished_at", "webhook_delivery_state",
    }
    assert required.issubset(FlowRun.model_fields)
```

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/models/test_flow_run.py -v`
Expected: `ImportError`.

- [x] **Step 3: Implement `FlowRun` model**

`src/backend/base/langflow/services/database/models/flow_run/model.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Column, JSON


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TriggeredBy(str, Enum):
    API = "api"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MCP = "mcp"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FlowRunBase(SQLModel):
    organization_id: UUID = Field(foreign_key="organization.id", index=True)
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    triggered_by: TriggeredBy = Field(sa_column=Column(sa.String(length=16), nullable=False))
    actor_id: UUID | None = Field(default=None)
    status: RunStatus = Field(default=RunStatus.QUEUED, sa_column=Column(sa.String(length=16), nullable=False, index=True))
    priority: int = Field(default=5)
    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    inputs_ref: str | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result_ref: str | None = Field(default=None)
    error: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    auto_retry: bool = Field(default=False)
    max_retries: int = Field(default=3)
    attempt: int = Field(default=0)
    cancel_requested: bool = Field(default=False)
    timeout_seconds: int = Field(default=600)
    worker_id: str | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)
    queued_at: datetime = Field(default_factory=_utcnow, nullable=False)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    webhook_delivery_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, server_default="{}"))


class FlowRun(FlowRunBase, table=True):
    __tablename__ = "flow_run"
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class FlowRunCreate(FlowRunBase):
    pass


class FlowRunRead(FlowRunBase):
    id: UUID
```

Also create `__init__.py` re-exporting `FlowRun, RunStatus, TriggeredBy, FlowRunRead, FlowRunCreate`.

- [x] **Step 4: Register the model for Alembic**

If the codebase has a central models import (e.g., `services/database/models/__init__.py`), add `from .flow_run.model import FlowRun`. Check existing pattern via `grep "from .flow" src/backend/base/langflow/services/database/models/__init__.py`.

- [x] **Step 5: Generate the migration**

Run: `cd src/backend/base && alembic revision --autogenerate -m "create flow_run"`

Verify the generated migration has `op.create_table("flow_run", ...)`. Add/confirm these indexes manually in `upgrade`:

```python
op.create_index("ix_flow_run_org_status_queued_at", "flow_run", ["organization_id", "status", "queued_at"])
op.create_index("ix_flow_run_flow_queued_at_desc", "flow_run", ["flow_id", sa.text("queued_at DESC")])
op.create_index("ix_flow_run_status_heartbeat", "flow_run", ["status", "heartbeat_at"])
op.create_index("ix_flow_run_status_finished", "flow_run", ["status", "finished_at"])
```

`downgrade` drops the indexes then the table.

- [x] **Step 6: Apply and run tests**

Run: `cd src/backend/base && alembic upgrade head && cd - && pytest src/backend/tests/unit/models/test_flow_run.py -v`
Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add src/backend/base/langflow/services/database/models/flow_run/ \
        src/backend/base/langflow/alembic/versions/*create_flow_run*.py \
        src/backend/tests/unit/models/test_flow_run.py \
        src/backend/base/langflow/services/database/models/__init__.py
git commit -m "feat(runs): flow_run model and migration"
```

---

### Task 6: Create `FlowRunLog` model + table

**Files:**
- Create: `src/backend/base/langflow/services/database/models/flow_run_log/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/flow_run_log/model.py`
- Create: `src/backend/base/langflow/alembic/versions/{newrev}_create_flow_run_log.py`
- Create: `src/backend/tests/unit/models/test_flow_run_log.py`

- [x] **Step 1: Failing test**

```python
from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel

def test_log_level_enum():
    assert {l.value for l in LogLevel} == {"debug", "info", "warn", "error"}

def test_flow_run_log_fields():
    required = {"id", "run_id", "ts", "level", "node_id", "message", "extra"}
    assert required.issubset(FlowRunLog.model_fields)
```

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/models/test_flow_run_log.py -v`

- [x] **Step 3: Implement**

`model.py`:

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Column, JSON


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class FlowRunLog(SQLModel, table=True):
    __tablename__ = "flow_run_log"
    id: int | None = Field(default=None, primary_key=True)
    run_id: UUID = Field(foreign_key="flow_run.id", index=True, nullable=False)
    ts: datetime = Field(nullable=False)
    level: LogLevel = Field(sa_column=Column(sa.String(length=8), nullable=False))
    node_id: str | None = Field(default=None)
    message: str = Field(nullable=False)
    extra: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
```

- [x] **Step 4: Migration**

Run: `cd src/backend/base && alembic revision --autogenerate -m "create flow_run_log"`

Verify the generated migration adds `run_id` FK with `ON DELETE CASCADE`. If autogenerate didn't set cascade, edit:

```python
sa.ForeignKeyConstraint(["run_id"], ["flow_run.id"], ondelete="CASCADE"),
```

Add: `op.create_index("ix_flow_run_log_run_ts", "flow_run_log", ["run_id", "ts"])`.

- [x] **Step 5: Apply, test, commit**

```bash
cd src/backend/base && alembic upgrade head && cd -
pytest src/backend/tests/unit/models/test_flow_run_log.py -v
git add src/backend/base/langflow/services/database/models/flow_run_log/ \
        src/backend/base/langflow/alembic/versions/*create_flow_run_log*.py \
        src/backend/tests/unit/models/test_flow_run_log.py \
        src/backend/base/langflow/services/database/models/__init__.py
git commit -m "feat(runs): flow_run_log model and migration"
```

---

## Phase 2 — Core Infra: Redis, Concurrency, Payload Offload

### Task 7: Add a Redis client service

**Files:**
- Create: `src/backend/base/langflow/services/redis/__init__.py`
- Create: `src/backend/base/langflow/services/redis/service.py`
- Create: `src/backend/base/langflow/services/redis/factory.py`
- Modify: `src/backend/base/langflow/services/schema.py` (or wherever `ServiceType` enum lives — check via `grep -r "class ServiceType" src/backend/base/langflow/services/`)
- Modify: `src/backend/base/langflow/services/manager.py` (or wherever services are registered)
- Create: `src/backend/tests/unit/services/test_redis_service.py`

- [x] **Step 1: Failing test**

```python
import pytest
from langflow.services.redis.service import RedisService

@pytest.mark.asyncio
async def test_redis_service_roundtrip(redis_service: RedisService):
    await redis_service.client.set("k", "v")
    assert (await redis_service.client.get("k")) == b"v"
```

Add fixture in `src/backend/tests/conftest.py`:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def redis_service():
    from langflow.services.redis.service import RedisService
    svc = RedisService(url="redis://localhost:6379/15")
    await svc.start()
    yield svc
    await svc.client.flushdb()
    await svc.stop()
```

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/services/test_redis_service.py -v`

- [x] **Step 3: Implement**

`service.py`:

```python
from __future__ import annotations
from redis.asyncio import Redis
from langflow.services.base import Service


class RedisService(Service):
    name = "redis_service"

    def __init__(self, url: str):
        self.url = url
        self.client: Redis | None = None

    async def start(self) -> None:
        self.client = Redis.from_url(self.url, decode_responses=False)
        await self.client.ping()

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def teardown(self) -> None:
        await self.stop()
```

`factory.py`:

```python
from langflow.services.factory import ServiceFactory
from langflow.services.deps import get_settings_service
from .service import RedisService


class RedisServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(RedisService)

    def create(self):
        settings = get_settings_service().settings
        return RedisService(url=settings.redis_url)
```

Register: add `REDIS_SERVICE = "redis_service"` to `ServiceType`, add `RedisServiceFactory` to the service factory list (follow the pattern used by `storage_service` or `task_service` — grep for `StorageServiceFactory` to find the registration site).

Add helper in `services/deps.py`:

```python
def get_redis_service() -> "RedisService":
    from langflow.services.schema import ServiceType
    return get_service(ServiceType.REDIS_SERVICE)
```

- [x] **Step 4: Ensure Redis is running for the test**

If no Redis in CI yet, document that `redis-server` on `6379` is required. Follow existing pattern — search `docker-compose.test.yml` or check if tests already assume Redis. Add Redis to `deploy/docker-compose.yml`'s test profile if needed.

- [x] **Step 5: Run — must pass**

Run: `pytest src/backend/tests/unit/services/test_redis_service.py -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/redis/ \
        src/backend/base/langflow/services/schema.py \
        src/backend/base/langflow/services/manager.py \
        src/backend/base/langflow/services/deps.py \
        src/backend/tests/conftest.py \
        src/backend/tests/unit/services/test_redis_service.py
git commit -m "feat(runs): redis service"
```

---

### Task 8: Per-org concurrency acquire/release (Lua script)

**Files:**
- Create: `src/backend/base/langflow/services/runs/__init__.py`
- Create: `src/backend/base/langflow/services/runs/concurrency.py`
- Create: `src/backend/tests/unit/services/runs/test_concurrency.py`

- [x] **Step 1: Failing test**

```python
import pytest
from uuid import uuid4
from langflow.services.runs.concurrency import OrgConcurrency

@pytest.mark.asyncio
async def test_acquire_respects_limit(redis_service):
    conc = OrgConcurrency(redis_service.client)
    org_id = uuid4()
    assert await conc.try_acquire(org_id, limit=2) is True
    assert await conc.try_acquire(org_id, limit=2) is True
    assert await conc.try_acquire(org_id, limit=2) is False
    await conc.release(org_id)
    assert await conc.try_acquire(org_id, limit=2) is True

@pytest.mark.asyncio
async def test_release_never_goes_negative(redis_service):
    conc = OrgConcurrency(redis_service.client)
    org_id = uuid4()
    await conc.release(org_id)
    assert await conc.try_acquire(org_id, limit=1) is True
```

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/services/runs/test_concurrency.py -v`

- [x] **Step 3: Implement**

`concurrency.py`:

```python
from __future__ import annotations
from uuid import UUID
from redis.asyncio import Redis

_ACQUIRE_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or '0')
if current < limit then
  redis.call('INCR', key)
  return 1
else
  return 0
end
"""

_RELEASE_LUA = """
local key = KEYS[1]
local current = tonumber(redis.call('GET', key) or '0')
if current > 0 then
  redis.call('DECR', key)
end
return 1
"""


class OrgConcurrency:
    def __init__(self, client: Redis):
        self.client = client
        self._acq = self.client.register_script(_ACQUIRE_LUA)
        self._rel = self.client.register_script(_RELEASE_LUA)

    @staticmethod
    def key(org_id: UUID) -> str:
        return f"org:{org_id}:running"

    async def try_acquire(self, org_id: UUID, *, limit: int) -> bool:
        result = await self._acq(keys=[self.key(org_id)], args=[limit])
        return int(result) == 1

    async def release(self, org_id: UUID) -> None:
        await self._rel(keys=[self.key(org_id)], args=[])

    async def current(self, org_id: UUID) -> int:
        v = await self.client.get(self.key(org_id))
        return int(v) if v else 0
```

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/unit/services/runs/test_concurrency.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/ \
        src/backend/tests/unit/services/runs/
git commit -m "feat(runs): per-org concurrency via redis lua"
```

---

### Task 9: Payload offload helper

**Files:**
- Create: `src/backend/base/langflow/services/runs/payload.py`
- Create: `src/backend/tests/unit/services/runs/test_payload.py`

- [x] **Step 1: Failing test**

```python
import json, pytest
from uuid import uuid4
from langflow.services.runs.payload import PayloadOffloader

@pytest.mark.asyncio
async def test_small_payload_inlines(storage_service):
    off = PayloadOffloader(storage_service, inline_max_bytes=1024)
    run_id = uuid4()
    inline, ref = await off.store(run_id, "inputs", {"a": 1})
    assert inline == {"a": 1}
    assert ref is None

@pytest.mark.asyncio
async def test_large_payload_offloads(storage_service):
    off = PayloadOffloader(storage_service, inline_max_bytes=10)
    run_id = uuid4()
    big = {"a": "x" * 1000}
    inline, ref = await off.store(run_id, "result", big)
    assert inline is None
    assert ref is not None
    loaded = await off.load(ref)
    assert loaded == big
```

`storage_service` fixture: use the existing `StorageService` with a local tmpdir backend.

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/services/runs/test_payload.py -v`

- [x] **Step 3: Implement**

`payload.py`:

```python
from __future__ import annotations
import json
from typing import Any
from uuid import UUID

from langflow.services.storage.service import StorageService

_FLOW_NS = "flow_runs"  # reuse storage namespace; the real storage layer uses flow_id, we pass str(run_id)


class PayloadOffloader:
    def __init__(self, storage: StorageService, *, inline_max_bytes: int):
        self.storage = storage
        self.inline_max_bytes = inline_max_bytes

    async def store(self, run_id: UUID, kind: str, payload: Any) -> tuple[Any | None, str | None]:
        data = json.dumps(payload).encode("utf-8")
        if len(data) <= self.inline_max_bytes:
            return payload, None
        file_name = f"{kind}.json"
        await self.storage.save_file(flow_id=str(run_id), file_name=file_name, data=data)
        ref = self.storage.build_full_path(str(run_id), file_name)
        return None, ref

    async def load(self, ref: str) -> Any:
        # ref is the storage "full path"; split into (flow_id, file_name) by the storage service's convention.
        run_id_str, file_name = ref.rsplit("/", 1)
        run_id_str = run_id_str.rsplit("/", 1)[-1]
        data = await self.storage.get_file(flow_id=run_id_str, file_name=file_name)
        return json.loads(data.decode("utf-8"))
```

Note: `build_full_path` and `save_file` signatures are from `storage/service.py`. If the storage service's `flow_id` param is strictly a real flow id (e.g., validated elsewhere), introduce a dedicated "bucket" argument or use a separate subdirectory convention by prefixing `file_name` with `run_{run_id}/`. Check the `local.py` and `s3.py` implementations and adapt accordingly.

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/unit/services/runs/test_payload.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/payload.py \
        src/backend/tests/unit/services/runs/test_payload.py
git commit -m "feat(runs): payload offload helper"
```

---

## Phase 3 — Enqueue + API Surface

### Task 10: Enqueue service (persist row + Arq job)

**Files:**
- Create: `src/backend/base/langflow/services/runs/enqueue.py`
- Create: `src/backend/tests/unit/services/runs/test_enqueue.py`

- [x] **Step 1: Failing test**

```python
import pytest
from uuid import uuid4

from langflow.services.runs.enqueue import RunEnqueuer
from langflow.services.database.models.flow_run.model import TriggeredBy, RunStatus

@pytest.mark.asyncio
async def test_enqueue_persists_row_and_dispatches(db_session, redis_service, org_and_flow):
    org, flow = org_and_flow
    enq = RunEnqueuer(db=db_session, redis=redis_service.client)
    run = await enq.enqueue(
        org_id=org.id, flow_id=flow.id, triggered_by=TriggeredBy.API,
        actor_id=None, inputs={"q": "hi"},
    )
    assert run.status == RunStatus.QUEUED
    # Arq pushes to a list; check length on the mapped priority queue
    queue_name = await redis_service.client.llen(b"arq:queue:runs:default")
    assert queue_name >= 1
```

Use existing `db_session` fixture (check conftest.py for actual name). `org_and_flow` creates an Organization with default tier and a Flow.

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/unit/services/runs/test_enqueue.py -v`

- [x] **Step 3: Implement**

`enqueue.py`:

```python
from __future__ import annotations
from uuid import UUID
from typing import Any

from arq.connections import ArqRedis
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from lfx.services.settings.base import Settings


_TIER_TO_QUEUE = {
    "high": "arq_high_queue",
    "default": "arq_default_queue",
    "low": "arq_low_queue",
}


class RunEnqueuer:
    def __init__(self, *, db: AsyncSession, redis: ArqRedis, settings: Settings):
        self.db = db
        self.redis = redis
        self.settings = settings

    async def enqueue(
        self,
        *,
        org_id: UUID,
        flow_id: UUID,
        triggered_by: TriggeredBy,
        actor_id: UUID | None,
        inputs: dict[str, Any] | None,
    ) -> FlowRun:
        org = await self.db.get(Organization, org_id)
        flow = await self.db.get(Flow, flow_id)
        if org is None or flow is None or flow.organization_id != org_id:
            raise ValueError("org/flow mismatch")

        run = FlowRun(
            organization_id=org_id,
            flow_id=flow_id,
            triggered_by=triggered_by,
            actor_id=actor_id,
            status=RunStatus.QUEUED,
            priority={"high": 1, "default": 5, "low": 9}[org.runs_priority_tier],
            inputs=inputs,
            auto_retry=flow.auto_retry,
            max_retries=flow.max_retries,
            timeout_seconds=flow.timeout_seconds,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        queue_attr = _TIER_TO_QUEUE[org.runs_priority_tier]
        queue_name = getattr(self.settings, queue_attr)
        await self.redis.enqueue_job("execute_run", str(run.id), _queue_name=queue_name)
        return run
```

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/unit/services/runs/test_enqueue.py -v`
Expected: PASS. (If Arq list-name differs, adjust assertion to match `arq:queue:<name>`.)

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/enqueue.py \
        src/backend/tests/unit/services/runs/test_enqueue.py
git commit -m "feat(runs): enqueue service persists row and dispatches arq job"
```

---

### Task 11: `POST /api/v2/runs` endpoint

**Files:**
- Create: `src/backend/base/langflow/api/v2/runs.py`
- Modify: `src/backend/base/langflow/api/v2/__init__.py` (or wherever v2 routers are registered — grep for existing v2 router includes)
- Create: `src/backend/tests/api/v2/test_runs_enqueue.py`

- [x] **Step 1: Failing API test**

```python
import pytest

@pytest.mark.asyncio
async def test_post_runs_returns_queued(client, api_key_headers, seeded_flow):
    body = {"flow_id": str(seeded_flow.id), "inputs": {"q": "hi"}}
    resp = await client.post("/api/v2/runs", json=body, headers=api_key_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "queued"
    assert "run_id" in data and "queued_at" in data
```

- [x] **Step 2: Run — must fail (404)**

Run: `pytest src/backend/tests/api/v2/test_runs_enqueue.py -v`

- [x] **Step 3: Implement**

`runs.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.auth import api_key_security  # match existing util path; grep for api_key_security
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_settings_service, get_session
from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy
from langflow.services.runs.enqueue import RunEnqueuer
from langflow.services.runs.deps import get_arq_pool, get_current_org

router = APIRouter(prefix="/runs", tags=["Runs"])


class EnqueueRunRequest(BaseModel):
    flow_id: UUID
    inputs: dict[str, Any] | None = None


class EnqueueRunResponse(BaseModel):
    run_id: UUID
    status: str
    queued_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EnqueueRunResponse)
async def enqueue_run(
    body: EnqueueRunRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[UserRead, Depends(api_key_security)],
    org=Depends(get_current_org),
    arq=Depends(get_arq_pool),
):
    settings = get_settings_service().settings
    if not settings.distributed_execution:
        raise HTTPException(503, "Distributed execution is disabled")
    enq = RunEnqueuer(db=session, redis=arq, settings=settings)
    try:
        run = await enq.enqueue(
            org_id=org.id, flow_id=body.flow_id, triggered_by=TriggeredBy.API,
            actor_id=user.id, inputs=body.inputs,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return EnqueueRunResponse(run_id=run.id, status=run.status.value, queued_at=run.queued_at)
```

Create `services/runs/deps.py` with:

```python
from functools import lru_cache
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from langflow.services.deps import get_settings_service


_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings_service().settings
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def get_current_org():
    # Delegate to whatever the multi-tenant foundation provides; grep for existing "current_organization"
    # helper. If one doesn't yet exist, implement by reading an org_id from the user's default membership.
    from langflow.services.auth.organization import get_current_organization  # placeholder path
    return await get_current_organization()
```

**Note for implementer:** the exact `get_current_organization` path depends on what the multi-tenant work from `6d926936ec2d_multi_tenant_foundation.py` added. Grep for `organization_id` dependency injection in existing endpoints. If none exists yet, the minimum is: fetch the user's memberships and use the first (or a configured-default) organization.

Register the router: add to the v2 router aggregation (follow the pattern in `src/backend/base/langflow/api/v2/__init__.py` where other v2 routers are `include_router`ed).

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/api/v2/test_runs_enqueue.py -v`
Expected: PASS with `LANGFLOW_DISTRIBUTED_EXECUTION=true` in the test env or monkeypatched settings.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v2/runs.py \
        src/backend/base/langflow/api/v2/__init__.py \
        src/backend/base/langflow/services/runs/deps.py \
        src/backend/tests/api/v2/test_runs_enqueue.py
git commit -m "feat(runs): POST /api/v2/runs enqueues jobs"
```

---

### Task 12: `GET /api/v2/runs/{run_id}` and list endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v2/runs.py`
- Create: `src/backend/tests/api/v2/test_runs_read.py`

- [x] **Step 1: Failing tests**

```python
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_get_run_scoped_to_org(client, api_key_headers, enqueued_run):
    resp = await client.get(f"/api/v2/runs/{enqueued_run.id}", headers=api_key_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

@pytest.mark.asyncio
async def test_get_run_404_for_other_org(client, api_key_headers_other_org, enqueued_run):
    resp = await client.get(f"/api/v2/runs/{enqueued_run.id}", headers=api_key_headers_other_org)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_list_runs_filters_by_flow(client, api_key_headers, seeded_flow, enqueued_run):
    resp = await client.get(f"/api/v2/runs?flow_id={seeded_flow.id}", headers=api_key_headers)
    assert resp.status_code == 200
    assert any(r["id"] == str(enqueued_run.id) for r in resp.json()["items"])
```

- [x] **Step 2: Run — must fail**

Run: `pytest src/backend/tests/api/v2/test_runs_read.py -v`

- [x] **Step 3: Implement**

Append to `runs.py`:

```python
from sqlmodel import select
from langflow.services.database.models.flow_run.model import FlowRunRead, RunStatus


class RunsListResponse(BaseModel):
    items: list[dict]
    next_cursor: str | None = None


@router.get("/{run_id}", response_model=dict)
async def get_run(run_id: UUID, session=Depends(get_session), org=Depends(get_current_org)):
    run = await session.get(FlowRun, run_id)
    if run is None or run.organization_id != org.id:
        raise HTTPException(404, "Not found")
    return _serialize(run)


@router.get("", response_model=RunsListResponse)
async def list_runs(
    flow_id: UUID | None = None,
    status_filter: RunStatus | None = None,
    limit: int = 50,
    cursor: str | None = None,
    session=Depends(get_session),
    org=Depends(get_current_org),
):
    limit = max(1, min(limit, 200))
    stmt = select(FlowRun).where(FlowRun.organization_id == org.id)
    if flow_id:
        stmt = stmt.where(FlowRun.flow_id == flow_id)
    if status_filter:
        stmt = stmt.where(FlowRun.status == status_filter)
    if cursor:
        stmt = stmt.where(FlowRun.queued_at < datetime.fromisoformat(cursor))
    stmt = stmt.order_by(FlowRun.queued_at.desc()).limit(limit + 1)
    rows = (await session.exec(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].queued_at.isoformat() if has_more and rows else None
    return RunsListResponse(items=[_serialize(r) for r in rows], next_cursor=next_cursor)


def _serialize(r: FlowRun) -> dict:
    return {
        "id": str(r.id),
        "organization_id": str(r.organization_id),
        "flow_id": str(r.flow_id),
        "status": r.status.value,
        "triggered_by": r.triggered_by.value if r.triggered_by else None,
        "attempt": r.attempt,
        "cancel_requested": r.cancel_requested,
        "queued_at": r.queued_at.isoformat(),
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "result": r.result,
        "result_ref": r.result_ref,
        "error": r.error,
    }
```

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/api/v2/test_runs_read.py -v`

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v2/runs.py src/backend/tests/api/v2/test_runs_read.py
git commit -m "feat(runs): read and list endpoints"
```

---

### Task 13: `POST /api/v2/runs/{run_id}/cancel` + cancel signal in Redis

**Files:**
- Modify: `src/backend/base/langflow/api/v2/runs.py`
- Modify: `src/backend/base/langflow/services/runs/concurrency.py` (add cancel helper — or create `cancel.py`)
- Create: `src/backend/tests/api/v2/test_runs_cancel.py`

- [x] **Step 1: Failing test**

```python
import pytest

@pytest.mark.asyncio
async def test_cancel_sets_flag_and_redis(client, api_key_headers, enqueued_run, redis_service):
    resp = await client.post(f"/api/v2/runs/{enqueued_run.id}/cancel", headers=api_key_headers)
    assert resp.status_code == 200
    assert await redis_service.client.get(f"run:cancel:{enqueued_run.id}") == b"1"
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

Create `src/backend/base/langflow/services/runs/cancel.py`:

```python
from uuid import UUID
from redis.asyncio import Redis


def _key(run_id: UUID) -> str:
    return f"run:cancel:{run_id}"


async def request_cancel(redis: Redis, run_id: UUID, *, ttl_seconds: int = 3600) -> None:
    await redis.set(_key(run_id), b"1", ex=ttl_seconds)


async def is_cancel_requested(redis: Redis, run_id: UUID) -> bool:
    return bool(await redis.get(_key(run_id)))
```

Add the endpoint:

```python
from langflow.services.runs.cancel import request_cancel
from langflow.services.deps import get_redis_service

@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    session=Depends(get_session),
    org=Depends(get_current_org),
    redis=Depends(get_redis_service),
):
    run = await session.get(FlowRun, run_id)
    if run is None or run.organization_id != org.id:
        raise HTTPException(404, "Not found")
    if run.status.value in {"succeeded", "failed", "cancelled", "timed_out"}:
        return {"status": run.status.value}
    run.cancel_requested = True
    await session.commit()
    await request_cancel(redis.client, run_id)
    return {"status": run.status.value}
```

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/api/v2/test_runs_cancel.py -v`

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/cancel.py \
        src/backend/base/langflow/api/v2/runs.py \
        src/backend/tests/api/v2/test_runs_cancel.py
git commit -m "feat(runs): cancel endpoint + redis cancel signal"
```

---

### Task 14: `GET /api/v2/runs/{run_id}/logs`

**Files:**
- Modify: `src/backend/base/langflow/api/v2/runs.py`
- Create: `src/backend/tests/api/v2/test_runs_logs.py`

- [x] **Step 1: Failing test**

```python
import pytest

@pytest.mark.asyncio
async def test_logs_paginated(client, api_key_headers, run_with_logs):
    resp = await client.get(f"/api/v2/runs/{run_with_logs.id}/logs?limit=2", headers=api_key_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert "next_cursor" in data
```

`run_with_logs` fixture inserts ~5 `FlowRunLog` rows for an existing run.

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from langflow.services.database.models.flow_run_log.model import FlowRunLog

@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: UUID, limit: int = 100, cursor: int | None = None,
    session=Depends(get_session), org=Depends(get_current_org),
):
    run = await session.get(FlowRun, run_id)
    if run is None or run.organization_id != org.id:
        raise HTTPException(404, "Not found")
    limit = max(1, min(limit, 500))
    stmt = select(FlowRunLog).where(FlowRunLog.run_id == run_id)
    if cursor is not None:
        stmt = stmt.where(FlowRunLog.id > cursor)
    stmt = stmt.order_by(FlowRunLog.id.asc()).limit(limit + 1)
    rows = (await session.exec(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {"id": r.id, "ts": r.ts.isoformat(), "level": r.level.value,
             "node_id": r.node_id, "message": r.message, "extra": r.extra}
            for r in rows
        ],
        "next_cursor": rows[-1].id if has_more and rows else None,
    }
```

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v2/runs.py src/backend/tests/api/v2/test_runs_logs.py
git commit -m "feat(runs): logs endpoint"
```

---

## Phase 4 — Worker

### Task 15: Worker settings (Arq `WorkerSettings` class)

**Files:**
- Create: `src/backend/base/langflow/worker_app/__init__.py`
- Create: `src/backend/base/langflow/worker_app/settings.py`
- Create: `src/backend/tests/unit/worker/test_worker_settings.py`

- [x] **Step 1: Failing test**

```python
from langflow.worker_app.settings import WorkerSettings

def test_worker_settings_registers_tasks():
    names = {f.__name__ if not isinstance(f, str) else f for f in WorkerSettings.functions}
    assert "execute_run" in names
    assert "deliver_webhook" in names
    assert any(cron.name == "reap_lost_runs" for cron in WorkerSettings.cron_jobs)
    assert any(cron.name == "retention_sweep" for cron in WorkerSettings.cron_jobs)
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement (stubs; real bodies come in later tasks)**

`settings.py`:

```python
from __future__ import annotations
from arq import cron
from arq.connections import RedisSettings

from lfx.services.settings.base import Settings

_settings = Settings(_env_file=None)


async def execute_run(ctx, run_id: str) -> None:
    # Implemented in Task 17
    raise NotImplementedError


async def deliver_webhook(ctx, run_id: str, event: str, attempt: int = 0) -> None:
    # Implemented in Task 24
    raise NotImplementedError


async def reap_lost_runs(ctx) -> None:
    # Implemented in Task 22
    raise NotImplementedError


async def retention_sweep(ctx) -> None:
    # Implemented in Task 23
    raise NotImplementedError


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    functions = [execute_run, deliver_webhook]
    cron_jobs = [
        cron(reap_lost_runs, name="reap_lost_runs", second={0, 30}),
        cron(retention_sweep, name="retention_sweep", minute=0),
    ]
    queue_name = _settings.arq_default_queue  # default; worker can override via CLI
    max_jobs = _settings.worker_concurrency
```

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/unit/worker/test_worker_settings.py -v`

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/ \
        src/backend/tests/unit/worker/test_worker_settings.py
git commit -m "feat(runs): worker settings skeleton"
```

---

### Task 16: Log handler that writes to `flow_run_log` in batches

**Files:**
- Create: `src/backend/base/langflow/worker_app/log_sink.py`
- Create: `src/backend/tests/unit/worker/test_log_sink.py`

- [x] **Step 1: Failing test**

```python
import asyncio, pytest, logging
from uuid import uuid4

@pytest.mark.asyncio
async def test_log_sink_flushes(db_session, flow_run):
    from langflow.worker_app.log_sink import RunLogSink
    sink = RunLogSink(session_factory=lambda: db_session, run_id=flow_run.id, flush_interval=0.05, max_buffer=10)
    await sink.start()
    for i in range(5):
        sink.emit(level="info", message=f"hi {i}", node_id=None, extra=None)
    await asyncio.sleep(0.2)
    await sink.stop()
    from langflow.services.database.models.flow_run_log.model import FlowRunLog
    from sqlmodel import select
    rows = (await db_session.exec(select(FlowRunLog).where(FlowRunLog.run_id == flow_run.id))).all()
    assert len(rows) == 5
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel


class RunLogSink:
    def __init__(
        self,
        *,
        session_factory: Callable,
        run_id: UUID,
        flush_interval: float = 0.5,
        max_buffer: int = 100,
        max_total_bytes: int = 10 * 1024 * 1024,
    ):
        self._session_factory = session_factory
        self._run_id = run_id
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._max_total_bytes = max_total_bytes
        self._buffer: list[FlowRunLog] = []
        self._bytes_written = 0
        self._truncated = False
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._flush_interval)
                except asyncio.TimeoutError:
                    pass
                await self._flush()
        finally:
            await self._flush()

    def emit(self, *, level: str, message: str, node_id: str | None, extra: dict[str, Any] | None) -> None:
        if self._bytes_written >= self._max_total_bytes:
            if not self._truncated:
                self._truncated = True
                self._buffer.append(FlowRunLog(
                    run_id=self._run_id, ts=datetime.now(timezone.utc),
                    level=LogLevel.WARN, node_id=None,
                    message="log capture truncated: max size reached", extra=None,
                ))
            return
        size = len(message.encode("utf-8"))
        self._bytes_written += size
        self._buffer.append(FlowRunLog(
            run_id=self._run_id, ts=datetime.now(timezone.utc),
            level=LogLevel(level), node_id=node_id, message=message, extra=extra,
        ))

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch, self._buffer = self._buffer, []
        async with self._session_factory() as session:
            session.add_all(batch)
            await session.commit()

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
```

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/log_sink.py \
        src/backend/tests/unit/worker/test_log_sink.py
git commit -m "feat(runs): batched run-log sink"
```

---

### Task 17: `execute_run` worker function

**Files:**
- Create: `src/backend/base/langflow/worker_app/execute.py`
- Modify: `src/backend/base/langflow/worker_app/settings.py` (replace stub)
- Create: `src/backend/tests/integration/worker/test_execute_run.py`

- [x] **Step 1: Failing integration test**

```python
import pytest, asyncio
from uuid import uuid4

@pytest.mark.asyncio
async def test_execute_run_happy_path(db_session, redis_service, arq_worker_ctx, enqueued_run):
    from langflow.worker_app.execute import execute_run
    await execute_run(arq_worker_ctx, str(enqueued_run.id))
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, enqueued_run.id)
    assert row.status == RunStatus.SUCCEEDED
    assert row.result is not None
    assert row.started_at is not None and row.finished_at is not None
```

`arq_worker_ctx` fixture builds a minimal `ctx` dict: `{"redis": redis_service.client, "db_sessionmaker": ...}`.

`enqueued_run` fixture seeds a queued `FlowRun` pointing at a trivial flow that returns a deterministic payload. Use an existing test-flow fixture if one exists (check `src/backend/tests/` for flow fixtures — `starter_projects` JSON or similar).

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

`execute.py`:

```python
from __future__ import annotations
import asyncio
import os
import socket
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.processing.process import run_graph_internal
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.database.models.organization.model import Organization
from langflow.services.runs.concurrency import OrgConcurrency
from langflow.services.runs.cancel import is_cancel_requested
from langflow.services.runs.payload import PayloadOffloader
from langflow.worker_app.log_sink import RunLogSink
from lfx.graph.graph.base import Graph


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
HEARTBEAT_INTERVAL = 15.0
CANCEL_POLL_INTERVAL = 2.0
REQUEUE_DELAY = 5.0


async def execute_run(ctx: dict[str, Any], run_id: str) -> None:
    run_uuid = UUID(run_id)
    redis = ctx["redis"]
    session_factory = ctx["db_sessionmaker"]
    storage = ctx["storage"]
    settings = ctx["settings"]
    offloader = PayloadOffloader(storage, inline_max_bytes=settings.run_payload_inline_max_bytes)
    concurrency = OrgConcurrency(redis)

    async with session_factory() as session:
        run = await session.get(FlowRun, run_uuid)
        if run is None or run.status != RunStatus.QUEUED:
            return
        org = await session.get(Organization, run.organization_id)
        flow = await session.get(Flow, run.flow_id)
        if org is None or flow is None:
            return

        acquired = await concurrency.try_acquire(org.id, limit=org.runs_max_concurrent)
        if not acquired:
            # re-enqueue to back of its queue
            from langflow.services.runs.enqueue import _TIER_TO_QUEUE
            queue = getattr(settings, _TIER_TO_QUEUE[org.runs_priority_tier])
            await ctx["arq"].enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=REQUEUE_DELAY)
            return

        run.status = RunStatus.RUNNING
        run.worker_id = WORKER_ID
        run.started_at = datetime.now(timezone.utc)
        run.heartbeat_at = run.started_at
        await session.commit()

    emit_started = asyncio.create_task(_emit_webhook(ctx, run_uuid, "run.started"))

    sink = RunLogSink(session_factory=session_factory, run_id=run_uuid)
    await sink.start()

    stop_event = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat(session_factory, run_uuid, stop_event))
    cancel_event = asyncio.Event()
    cancel_task = asyncio.create_task(_cancel_watcher(redis, run_uuid, cancel_event, stop_event))

    result_payload: Any = None
    error_payload: dict | None = None
    terminal: RunStatus = RunStatus.FAILED

    try:
        async with session_factory() as s:
            run = await s.get(FlowRun, run_uuid)
            flow = await s.get(Flow, run.flow_id)
            inputs = run.inputs
            if run.inputs_ref:
                inputs = await offloader.load(run.inputs_ref)
            timeout_s = run.timeout_seconds

        graph = Graph.from_payload(flow.data)  # adapt to current Graph constructor; grep for existing usage
        execution = asyncio.create_task(_do_run(graph, flow, inputs))

        done, pending = await asyncio.wait(
            {execution, cancel_event.wait()},
            timeout=timeout_s,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if cancel_event.is_set():
            execution.cancel()
            try:
                await execution
            except BaseException:
                pass
            terminal = RunStatus.CANCELLED
        elif execution in done:
            result_payload = execution.result()
            terminal = RunStatus.SUCCEEDED
        else:
            execution.cancel()
            try:
                await execution
            except BaseException:
                pass
            terminal = RunStatus.TIMED_OUT
            error_payload = {"type": "timeout", "message": f"exceeded {timeout_s}s"}

    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        terminal = RunStatus.FAILED
        error_payload = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=20),
        }
    finally:
        stop_event.set()
        for t in (hb_task, cancel_task):
            try:
                await t
            except BaseException:
                pass
        await sink.stop()

    async with session_factory() as session:
        run = await session.get(FlowRun, run_uuid)
        run.status = terminal
        run.finished_at = datetime.now(timezone.utc)
        if result_payload is not None:
            inline, ref = await offloader.store(run_uuid, "result", _jsonable(result_payload))
            run.result = inline
            run.result_ref = ref
        if error_payload is not None:
            run.error = error_payload
        await session.commit()
    await concurrency.release(run.organization_id)

    event_map = {
        RunStatus.SUCCEEDED: "run.succeeded",
        RunStatus.FAILED: "run.failed",
        RunStatus.CANCELLED: "run.cancelled",
        RunStatus.TIMED_OUT: "run.timed_out",
    }
    await _emit_webhook(ctx, run_uuid, event_map[terminal])
    await emit_started  # make sure started webhook was handed off

    # Auto-retry
    if terminal in {RunStatus.FAILED, RunStatus.TIMED_OUT}:
        async with session_factory() as session:
            run = await session.get(FlowRun, run_uuid)
            if run.auto_retry and run.attempt < run.max_retries:
                run.attempt += 1
                run.status = RunStatus.QUEUED
                run.started_at = None
                run.finished_at = None
                run.error = None
                run.result = None
                run.result_ref = None
                run.worker_id = None
                await session.commit()
                backoff = min(30 * (2 ** (run.attempt - 1)), 1800)
                from langflow.services.runs.enqueue import _TIER_TO_QUEUE
                org = await session.get(Organization, run.organization_id)
                queue = getattr(settings, _TIER_TO_QUEUE[org.runs_priority_tier])
                await ctx["arq"].enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=backoff)


async def _do_run(graph, flow, inputs):
    results, _session_id = await run_graph_internal(
        graph=graph, flow_id=str(flow.id), stream=False,
        session_id=None, inputs=inputs or [], outputs=None, event_manager=None,
    )
    return results


def _jsonable(obj: Any) -> Any:
    # Existing project likely has a serializer; grep for "jsonable_encoder" usage in the codebase.
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(obj)


async def _heartbeat(session_factory, run_id: UUID, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            pass
        async with session_factory() as s:
            run = await s.get(FlowRun, run_id)
            if run is None or run.status != RunStatus.RUNNING:
                return
            run.heartbeat_at = datetime.now(timezone.utc)
            await s.commit()


async def _cancel_watcher(redis, run_id: UUID, cancel_event: asyncio.Event, stop: asyncio.Event) -> None:
    while not stop.is_set():
        if await is_cancel_requested(redis, run_id):
            cancel_event.set()
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=CANCEL_POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def _emit_webhook(ctx, run_id: UUID, event: str) -> None:
    await ctx["arq"].enqueue_job("deliver_webhook", str(run_id), event, _queue_name=ctx["settings"].arq_webhooks_queue)
```

Wire the real function into `WorkerSettings.functions` in `worker_app/settings.py`: replace the stub import and register `execute_run`.

**Note to implementer:** `Graph.from_payload` is illustrative. The current code in `api/v1/endpoints.py` at `_run_flow_internal` shows the real graph construction path; copy that pattern (likely `Graph.from_payload(flow.data)` or similar). If there is a helper already that builds a Graph from a `Flow`, reuse it.

- [x] **Step 4: Run — must pass**

Run: `pytest src/backend/tests/integration/worker/test_execute_run.py -v`

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/execute.py \
        src/backend/base/langflow/worker_app/settings.py \
        src/backend/tests/integration/worker/test_execute_run.py
git commit -m "feat(runs): execute_run worker task"
```

---

### Task 18: Test — cancellation path

**Files:**
- Create: `src/backend/tests/integration/worker/test_execute_run_cancel.py`

- [x] **Step 1: Write test**

```python
import asyncio, pytest
from langflow.services.runs.cancel import request_cancel

@pytest.mark.asyncio
async def test_execute_run_honors_cancel(db_session, redis_service, arq_worker_ctx, slow_enqueued_run):
    from langflow.worker_app.execute import execute_run
    async def _cancel():
        await asyncio.sleep(0.3)
        await request_cancel(redis_service.client, slow_enqueued_run.id)
    task = asyncio.create_task(execute_run(arq_worker_ctx, str(slow_enqueued_run.id)))
    await asyncio.gather(task, _cancel())
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, slow_enqueued_run.id)
    assert row.status == RunStatus.CANCELLED
```

`slow_enqueued_run` wraps a flow that awaits e.g. 5s (a Python component with `asyncio.sleep(5)`).

- [x] **Step 2: Run — must pass** (if not, debug the cancel_watcher / executor cancel path)

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/integration/worker/test_execute_run_cancel.py
git commit -m "test(runs): cancellation path"
```

---

### Task 19: Test — timeout path

**Files:**
- Create: `src/backend/tests/integration/worker/test_execute_run_timeout.py`

- [x] **Step 1: Write test**

```python
import pytest

@pytest.mark.asyncio
async def test_execute_run_times_out(db_session, redis_service, arq_worker_ctx, enqueued_run_with_short_timeout):
    from langflow.worker_app.execute import execute_run
    await execute_run(arq_worker_ctx, str(enqueued_run_with_short_timeout.id))
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, enqueued_run_with_short_timeout.id)
    assert row.status == RunStatus.TIMED_OUT
    assert row.error["type"] == "timeout"
```

Fixture `enqueued_run_with_short_timeout`: flow with `timeout_seconds=1` and a 5s sleep component.

- [x] **Step 2: Run — must pass**

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/integration/worker/test_execute_run_timeout.py
git commit -m "test(runs): timeout path"
```

---

### Task 20: Test — per-org concurrency cap causes re-enqueue

**Files:**
- Create: `src/backend/tests/integration/worker/test_execute_run_concurrency.py`

- [x] **Step 1: Write test**

```python
import pytest
from uuid import UUID

@pytest.mark.asyncio
async def test_over_cap_requeues(db_session, redis_service, arq_worker_ctx, enqueued_run, settings_override):
    from langflow.services.runs.concurrency import OrgConcurrency
    conc = OrgConcurrency(redis_service.client)
    # Fill the slot externally
    await conc.try_acquire(enqueued_run.organization_id, limit=1)
    # Force org cap=1 for the test via fixture
    from langflow.worker_app.execute import execute_run
    await execute_run(arq_worker_ctx, str(enqueued_run.id))
    # Row still queued
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, enqueued_run.id)
    assert row.status == RunStatus.QUEUED
    # Job re-enqueued
    assert await redis_service.client.zcard(b"arq:queue:runs:default:deferred") >= 1 \
        or await redis_service.client.llen(b"arq:queue:runs:default") >= 1
```

- [x] **Step 2: Run — must pass**

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/integration/worker/test_execute_run_concurrency.py
git commit -m "test(runs): cap-exceeded re-enqueue"
```

---

### Task 21: Test — auto-retry

**Files:**
- Create: `src/backend/tests/integration/worker/test_execute_run_retry.py`

- [x] **Step 1: Write test**

```python
import pytest

@pytest.mark.asyncio
async def test_auto_retry_reenqueues(db_session, redis_service, arq_worker_ctx, failing_run_with_retry):
    from langflow.worker_app.execute import execute_run
    await execute_run(arq_worker_ctx, str(failing_run_with_retry.id))
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, failing_run_with_retry.id)
    assert row.status == RunStatus.QUEUED
    assert row.attempt == 1
```

`failing_run_with_retry`: flow that raises and has `auto_retry=True, max_retries=3`.

- [x] **Step 2: Run — must pass**

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/integration/worker/test_execute_run_retry.py
git commit -m "test(runs): auto-retry re-enqueue"
```

---

### Task 22: Reaper — mark lost runs failed

**Files:**
- Create: `src/backend/base/langflow/worker_app/reaper.py`
- Modify: `src/backend/base/langflow/worker_app/settings.py`
- Create: `src/backend/tests/integration/worker/test_reaper.py`

- [x] **Step 1: Failing test**

```python
import pytest
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_reaper_marks_stale_running_failed(db_session, arq_worker_ctx, running_run_with_stale_heartbeat):
    from langflow.worker_app.reaper import reap_lost_runs
    await reap_lost_runs(arq_worker_ctx)
    from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
    row = await db_session.get(FlowRun, running_run_with_stale_heartbeat.id)
    assert row.status == RunStatus.FAILED
    assert row.error["type"] == "worker_lost"
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

`reaper.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlmodel import select

from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.runs.concurrency import OrgConcurrency

STALE_AFTER_SECONDS = 60


async def reap_lost_runs(ctx) -> None:
    session_factory = ctx["db_sessionmaker"]
    redis = ctx["redis"]
    concurrency = OrgConcurrency(redis)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)

    async with session_factory() as session:
        stmt = select(FlowRun).where(FlowRun.status == RunStatus.RUNNING, FlowRun.heartbeat_at < cutoff)
        rows = (await session.exec(stmt)).all()
        for row in rows:
            row.status = RunStatus.FAILED
            row.finished_at = datetime.now(timezone.utc)
            row.error = {"type": "worker_lost", "message": "no heartbeat within 60s"}
            await concurrency.release(row.organization_id)
        await session.commit()

    for row in rows:
        await ctx["arq"].enqueue_job(
            "deliver_webhook", str(row.id), "run.failed",
            _queue_name=ctx["settings"].arq_webhooks_queue,
        )
```

Replace the stub in `worker_app/settings.py` with `from .reaper import reap_lost_runs`.

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/reaper.py \
        src/backend/base/langflow/worker_app/settings.py \
        src/backend/tests/integration/worker/test_reaper.py
git commit -m "feat(runs): reaper marks lost runs failed"
```

---

### Task 23: Retention sweep

**Files:**
- Create: `src/backend/base/langflow/worker_app/retention.py`
- Modify: `src/backend/base/langflow/worker_app/settings.py`
- Create: `src/backend/tests/integration/worker/test_retention.py`

- [x] **Step 1: Failing test**

```python
import pytest
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_retention_deletes_old_runs(db_session, arq_worker_ctx, very_old_finished_run):
    from langflow.worker_app.retention import retention_sweep
    await retention_sweep(arq_worker_ctx)
    from langflow.services.database.models.flow_run.model import FlowRun
    row = await db_session.get(FlowRun, very_old_finished_run.id)
    assert row is None
```

`very_old_finished_run` fixture: creates a `succeeded` run with `finished_at` set 48h ago.

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlmodel import delete

from langflow.services.database.models.flow_run.model import FlowRun


async def retention_sweep(ctx) -> None:
    settings = ctx["settings"]
    session_factory = ctx["db_sessionmaker"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.run_retention_hours)
    async with session_factory() as session:
        await session.exec(
            delete(FlowRun).where(FlowRun.finished_at.is_not(None), FlowRun.finished_at < cutoff)
        )
        await session.commit()
    # flow_run_log cascades via FK; object-storage cleanup is best-effort and deferred.
```

Wire into `WorkerSettings`.

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/retention.py \
        src/backend/base/langflow/worker_app/settings.py \
        src/backend/tests/integration/worker/test_retention.py
git commit -m "feat(runs): retention sweep"
```

---

## Phase 5 — Webhooks

### Task 24: HMAC signing utility

**Files:**
- Create: `src/backend/base/langflow/services/runs/webhook_sign.py`
- Create: `src/backend/tests/unit/services/runs/test_webhook_sign.py`

- [x] **Step 1: Failing test**

```python
from langflow.services.runs.webhook_sign import sign_body, verify_body

def test_sign_and_verify_roundtrip():
    body = b'{"event":"run.started"}'
    secret = "s3cret"
    sig = sign_body(body, secret)
    assert sig.startswith("sha256=")
    assert verify_body(body, secret, sig)
    assert not verify_body(body, secret, "sha256=deadbeef")
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from __future__ import annotations
import hmac
import hashlib


def sign_body(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_body(body: bytes, secret: str, signature: str) -> bool:
    expected = sign_body(body, secret)
    return hmac.compare_digest(expected, signature)
```

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/webhook_sign.py \
        src/backend/tests/unit/services/runs/test_webhook_sign.py
git commit -m "feat(runs): webhook HMAC signing"
```

---

### Task 25: `deliver_webhook` worker task + per-run delivery state

**Files:**
- Create: `src/backend/base/langflow/worker_app/webhook.py`
- Modify: `src/backend/base/langflow/worker_app/settings.py`
- Create: `src/backend/tests/integration/worker/test_deliver_webhook.py`

- [x] **Step 1: Failing test**

```python
import pytest, json, respx, httpx
from uuid import uuid4

@pytest.mark.asyncio
async def test_deliver_webhook_success_records_state(db_session, arq_worker_ctx, succeeded_run_with_webhook):
    from langflow.worker_app.webhook import deliver_webhook
    with respx.mock:
        route = respx.post("https://hook.test/endpoint").mock(return_value=httpx.Response(200))
        await deliver_webhook(arq_worker_ctx, str(succeeded_run_with_webhook.id), "run.succeeded")
    from langflow.services.database.models.flow_run.model import FlowRun
    row = await db_session.get(FlowRun, succeeded_run_with_webhook.id)
    assert row.webhook_delivery_state["run.succeeded"]["status"] == "delivered"
    assert route.called

@pytest.mark.asyncio
async def test_deliver_webhook_failure_schedules_retry(db_session, redis_service, arq_worker_ctx, succeeded_run_with_webhook):
    from langflow.worker_app.webhook import deliver_webhook
    with respx.mock:
        respx.post("https://hook.test/endpoint").mock(return_value=httpx.Response(500))
        await deliver_webhook(arq_worker_ctx, str(succeeded_run_with_webhook.id), "run.succeeded", 0)
    from langflow.services.database.models.flow_run.model import FlowRun
    row = await db_session.get(FlowRun, succeeded_run_with_webhook.id)
    assert row.webhook_delivery_state["run.succeeded"]["status"] == "retrying"
    # A deferred webhooks job exists
    assert await redis_service.client.zcard(b"arq:queue:webhooks:deferred") >= 1
```

`succeeded_run_with_webhook`: seeded `FlowRun` where its flow has `webhook_url="https://hook.test/endpoint"` and a secret.

Add `respx` to dev dependencies (httpx mocking) if not present.

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.runs.webhook_sign import sign_body


_BACKOFF_SCHEDULE_SEC = [10, 30, 120, 600, 1800, 3600]  # 6 attempts
_HTTP_TIMEOUT = httpx.Timeout(10.0)


def _build_payload(run: FlowRun, event: str) -> dict[str, Any]:
    return {
        "event": event,
        "run_id": str(run.id),
        "flow_id": str(run.flow_id),
        "organization_id": str(run.organization_id),
        "status": run.status.value,
        "inputs": run.inputs,
        "inputs_ref": run.inputs_ref,
        "result": run.result,
        "result_ref": run.result_ref,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "attempt": run.attempt,
    }


async def deliver_webhook(ctx, run_id: str, event: str, attempt: int = 0) -> None:
    session_factory = ctx["db_sessionmaker"]
    async with session_factory() as session:
        run = await session.get(FlowRun, UUID(run_id))
        if run is None:
            return
        flow = await session.get(Flow, run.flow_id)
        if flow is None or not flow.webhook_url or not flow.webhook_secret:
            return
        payload = _build_payload(run, event)

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Langflow-Event": event,
        "X-Langflow-Delivery": str(uuid4()),
        "X-Langflow-Timestamp": datetime.now(timezone.utc).isoformat(),
        "X-Langflow-Signature": sign_body(body, flow.webhook_secret),
    }

    status: str
    last_response: dict[str, Any] | None = None
    should_retry = False
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(flow.webhook_url, content=body, headers=headers)
        last_response = {"status_code": resp.status_code, "body": resp.text[:500]}
        if 200 <= resp.status_code < 300:
            status = "delivered"
        elif resp.status_code == 429 or 500 <= resp.status_code < 600:
            status = "retrying"
            should_retry = True
        else:
            status = "failed"
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        last_response = {"error": str(exc)[:500]}
        status = "retrying"
        should_retry = True

    if should_retry and attempt + 1 >= len(_BACKOFF_SCHEDULE_SEC):
        status = "failed"
        should_retry = False

    async with session_factory() as session:
        run = await session.get(FlowRun, UUID(run_id))
        if run is None:
            return
        state = dict(run.webhook_delivery_state or {})
        state[event] = {
            "status": status,
            "attempts": attempt + 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            "last_response": last_response,
        }
        run.webhook_delivery_state = state
        await session.commit()

    if should_retry:
        delay = _BACKOFF_SCHEDULE_SEC[attempt]
        await ctx["arq"].enqueue_job(
            "deliver_webhook", run_id, event, attempt + 1,
            _queue_name=ctx["settings"].arq_webhooks_queue, _defer_by=delay,
        )
```

Wire into `WorkerSettings.functions`.

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/worker_app/webhook.py \
        src/backend/base/langflow/worker_app/settings.py \
        src/backend/tests/integration/worker/test_deliver_webhook.py \
        pyproject.toml uv.lock
git commit -m "feat(runs): webhook delivery with retry + delivery state"
```

---

## Phase 6 — Triggers, Metrics, CLI

### Task 26: Prometheus metrics

**Files:**
- Create: `src/backend/base/langflow/services/runs/metrics.py`
- Modify: `src/backend/base/langflow/main.py` (or wherever FastAPI is assembled — grep for `FastAPI(`) to expose `/metrics`
- Modify: `src/backend/base/langflow/worker_app/execute.py` to increment counters/histograms
- Create: `src/backend/tests/unit/services/runs/test_metrics.py`

- [x] **Step 1: Failing test**

```python
from langflow.services.runs.metrics import RUNS_TOTAL, RUN_DURATION, QUEUE_DEPTH, ACTIVE_RUNS, WEBHOOK_DELIVERY_TOTAL

def test_metrics_registered():
    for m in (RUNS_TOTAL, RUN_DURATION, QUEUE_DEPTH, ACTIVE_RUNS, WEBHOOK_DELIVERY_TOTAL):
        assert m is not None
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

```python
from prometheus_client import Counter, Histogram, Gauge

RUNS_TOTAL = Counter("langflow_runs_total", "Total runs", ["status", "flow_id"])
RUN_DURATION = Histogram("langflow_run_duration_seconds", "Run duration", ["status", "flow_id"])
QUEUE_DEPTH = Gauge("langflow_queue_depth", "Queue depth", ["queue"])
ACTIVE_RUNS = Gauge("langflow_active_runs", "Active runs", ["organization_id"])
WEBHOOK_DELIVERY_TOTAL = Counter("langflow_webhook_delivery_total", "Webhook deliveries", ["event", "status"])
```

In `execute.py` at the terminal-state write site, increment `RUNS_TOTAL.labels(status=terminal.value, flow_id=str(flow.id)).inc()` and observe duration (`(finished - started).total_seconds()`). In `webhook.py` increment `WEBHOOK_DELIVERY_TOTAL`.

Expose `/metrics` on API: in the FastAPI app setup:

```python
from prometheus_client import make_asgi_app
app.mount("/metrics", make_asgi_app())
```

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/runs/metrics.py \
        src/backend/base/langflow/main.py \
        src/backend/base/langflow/worker_app/execute.py \
        src/backend/base/langflow/worker_app/webhook.py \
        src/backend/tests/unit/services/runs/test_metrics.py
git commit -m "feat(runs): prometheus metrics on API and worker"
```

---

### Task 27: Wire webhook / schedule / MCP trigger paths behind the flag

**Files:**
- Modify: `src/backend/base/langflow/api/v1/endpoints.py` (webhook trigger endpoint)
- Modify: `src/backend/base/langflow/api/v2/mcp.py` (MCP execution path — grep for `run_graph_internal` usage)
- Modify: scheduled-trigger dispatch site (grep for `schedule` or `cron` trigger-handler references)
- Create: `src/backend/tests/integration/triggers/test_trigger_dispatch.py`

- [x] **Step 1: Write integration tests**

```python
import pytest

@pytest.mark.asyncio
async def test_webhook_trigger_uses_queue_when_flag_on(client, settings_override_distributed_on, seeded_webhook_trigger):
    resp = await client.post(f"/api/v1/run/{seeded_webhook_trigger.flow.endpoint_name}", json={"inputs": {"q": "hi"}})
    # New shape: returns a queued run id
    assert resp.status_code == 202
    assert "run_id" in resp.json()

@pytest.mark.asyncio
async def test_webhook_trigger_in_process_when_flag_off(client, settings_override_distributed_off, seeded_webhook_trigger):
    resp = await client.post(f"/api/v1/run/{seeded_webhook_trigger.flow.endpoint_name}", json={"inputs": {"q": "hi"}})
    assert resp.status_code == 200  # existing synchronous behavior
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

In each trigger handler (webhook, schedule, MCP), add a branch at the top that checks `settings.distributed_execution`. When true, call `RunEnqueuer.enqueue(triggered_by=...)` and return a 202 `{run_id}`. When false, fall through to existing `run_graph_internal` path.

Example for the webhook endpoint in `api/v1/endpoints.py`:

```python
settings = get_settings_service().settings
if settings.distributed_execution:
    enq = RunEnqueuer(db=session, redis=await get_arq_pool(), settings=settings)
    run = await enq.enqueue(
        org_id=flow.organization_id, flow_id=flow.id,
        triggered_by=TriggeredBy.WEBHOOK, actor_id=None,
        inputs=request_body.inputs,
    )
    return JSONResponse({"run_id": str(run.id), "status": "queued"}, status_code=202)
# existing in-process path continues unchanged
```

Same branch inserted in the schedule dispatcher and MCP tool execution path.

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/endpoints.py \
        src/backend/base/langflow/api/v2/mcp.py \
        <schedule-dispatcher-file> \
        src/backend/tests/integration/triggers/test_trigger_dispatch.py
git commit -m "feat(runs): route webhook/schedule/MCP through queue when flag is on"
```

---

### Task 28: `langflow worker` CLI subcommand

**Files:**
- Modify: `src/backend/base/langflow/__main__.py`
- Create: `src/backend/base/langflow/cli/worker_cmd.py`
- Create: `src/backend/tests/unit/cli/test_worker_cmd.py`

- [x] **Step 1: Failing test**

```python
from typer.testing import CliRunner
from langflow.__main__ import app

def test_worker_help_lists_subcommand():
    result = CliRunner().invoke(app, ["worker", "--help"])
    assert result.exit_code == 0
    assert "queue" in result.output
```

- [x] **Step 2: Run — must fail**

- [x] **Step 3: Implement**

`cli/worker_cmd.py`:

```python
from __future__ import annotations
import asyncio
import typer
from arq.worker import Worker

from langflow.worker_app.settings import WorkerSettings


def worker_cmd(
    queue: list[str] = typer.Option(None, "--queue", "-q", help="Queues to poll; repeat the flag for multiple."),
    concurrency: int | None = typer.Option(None, "--concurrency"),
):
    """Run a distributed flow-execution worker."""
    settings = WorkerSettings
    if queue:
        settings.queue_name = queue[0]  # arq single-queue per worker; run multiple processes for multiple queues
    if concurrency is not None:
        settings.max_jobs = concurrency
    asyncio.run(Worker(settings_cls=settings).async_run())
```

In `__main__.py`:

```python
from langflow.cli.worker_cmd import worker_cmd
app.command(name="worker", help="Run a distributed flow-execution worker")(worker_cmd)
```

- [x] **Step 4: Run — must pass**

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/__main__.py \
        src/backend/base/langflow/cli/ \
        src/backend/tests/unit/cli/
git commit -m "feat(runs): langflow worker CLI subcommand"
```

---

## Phase 7 — Deployment + Cleanup

### Task 29: Update `deploy/docker-compose.yml`

**Files:**
- Modify: `deploy/docker-compose.yml`

- [x] **Step 1: Read the current file**

Run: `cat deploy/docker-compose.yml` and note the existing `langflow`, `celeryworker`, `rabbitmq`, `flower`, `postgres`, `redis`, `minio` services (if present).

- [x] **Step 2: Edit**

Remove: `celeryworker`, `rabbitmq`, `flower` services and any `depends_on` references to them.

Add:

```yaml
  langflow-worker:
    image: langflowai/langflow:latest
    command: ["langflow", "worker", "--queue", "runs:default", "--concurrency", "8"]
    env_file: .env
    environment:
      - LANGFLOW_DISTRIBUTED_EXECUTION=true
      - LANGFLOW_REDIS_URL=redis://redis:6379/0
      - LANGFLOW_DATABASE_URL=${LANGFLOW_DATABASE_URL}
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  langflow-worker-high:
    image: langflowai/langflow:latest
    command: ["langflow", "worker", "--queue", "runs:high", "--concurrency", "4"]
    env_file: .env
    environment:
      - LANGFLOW_DISTRIBUTED_EXECUTION=true
      - LANGFLOW_REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  langflow-worker-webhooks:
    image: langflowai/langflow:latest
    command: ["langflow", "worker", "--queue", "webhooks", "--concurrency", "16"]
    env_file: .env
    environment:
      - LANGFLOW_DISTRIBUTED_EXECUTION=true
      - LANGFLOW_REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
```

Ensure `redis` is present; ensure `minio` is present (for payload offload in self-hosted mode).

- [x] **Step 3: Sanity check**

Run: `docker compose -f deploy/docker-compose.yml config` — must parse without errors.

- [x] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "chore(runs): docker-compose workers; remove celery/rabbitmq/flower"
```

---

### Task 30: Helm chart + KEDA `ScaledObject`

> **DEFERRED — cross-repo handoff.** The Helm chart lives in a separate repo (not `langflow-ai/langflow`). A concrete starter with the three templates this plan spec'd out now lives in-tree at `deploy/helm/worker-starter/` (see that directory's README). Whoever owns the external Helm repo can lift those files; none of it is applied here.

**Files (in the Helm repo, not this one):**
- Modify or create: `deploy/helm/langflow/templates/worker-deployment.yaml`
- Create: `deploy/helm/langflow/templates/worker-scaledobject.yaml`
- Modify: `deploy/helm/langflow/values.yaml`

- [ ] **Step 1: values.yaml additions**

```yaml
worker:
  enabled: true
  replicas: 1
  concurrency: 8
  queues: ["runs:default", "runs:high", "webhooks"]
  resources: {}
  autoscaling:
    enabled: true
    minReplicas: 1
    maxReplicas: 10
    redis:
      address: redis:6379
      queueName: runs:default
      listLength: "100"
```

- [ ] **Step 2: `worker-deployment.yaml`**

Use the existing API Deployment as a template; change:
- `.metadata.name` to `{{ include "langflow.fullname" . }}-worker`
- `.spec.template.spec.containers[0].command` to `["langflow", "worker", "--queue", "runs:default", "--concurrency", "{{ .Values.worker.concurrency }}"]`
- Set `LANGFLOW_DISTRIBUTED_EXECUTION=true` and `LANGFLOW_REDIS_URL` via env.
- Reuse the same `image`, `envFrom`, `volumeMounts` as the API.

For multiple queues, either run multiple Deployments (one per queue) or pass `--queue` once per process. Worker processes poll one queue; run separate Deployments per queue in production.

- [ ] **Step 3: `worker-scaledobject.yaml`**

```yaml
{{- if .Values.worker.autoscaling.enabled }}
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: {{ include "langflow.fullname" . }}-worker
spec:
  scaleTargetRef:
    name: {{ include "langflow.fullname" . }}-worker
  minReplicaCount: {{ .Values.worker.autoscaling.minReplicas }}
  maxReplicaCount: {{ .Values.worker.autoscaling.maxReplicas }}
  triggers:
    - type: redis
      metadata:
        address: {{ .Values.worker.autoscaling.redis.address }}
        listName: "arq:queue:{{ .Values.worker.autoscaling.redis.queueName }}"
        listLength: "{{ .Values.worker.autoscaling.redis.listLength }}"
{{- end }}
```

- [ ] **Step 4: Lint**

Run: `helm lint deploy/helm/langflow`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add deploy/helm/langflow/
git commit -m "chore(runs): helm worker deployment + KEDA ScaledObject"
```

---

### Task 31: Remove the Celery scaffold

**Files:**
- Delete: `src/backend/base/langflow/worker.py`
- Delete: `src/backend/base/langflow/core/celery_app.py`
- Delete: `src/backend/base/langflow/core/celeryconfig.py`
- Modify: `src/backend/base/langflow/services/task/service.py` (remove `CeleryBackend`, keep `AnyIOBackend`, or inline if abstraction no longer earns its keep)
- Modify: `src/backend/base/langflow/services/task/backends/` — remove celery backend file
- Modify: `src/lfx/src/lfx/services/settings/base.py` — remove `celery_enabled` setting

- [x] **Step 1: Grep for remaining references**

Run: `grep -r "celery" src/backend src/lfx --include="*.py"`
Expected: zero hits after deletions.

Run: `grep -r "from langflow.worker" src/backend --include="*.py"`
Expected: zero hits (the Arq worker lives in `worker_app`).

- [x] **Step 2: Delete files and update imports**

Remove the files listed above. Update any `__init__.py` that imported them.

For `task/service.py`: keep `TaskService` as a thin wrapper over `AnyIOBackend` only, or remove the abstraction and inline `anyio.create_task_group` at the single remaining call site. Decide based on how many callers exist (`grep -r "TaskService" src/backend --include="*.py"`).

- [x] **Step 3: Remove `celery_enabled` setting**

```python
# delete from Settings:
# celery_enabled: bool = False
```

- [x] **Step 4: Run the full test suite**

Run: `pytest src/backend/tests -x`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add -u
git commit -m "chore(runs): remove legacy celery scaffold"
```

---

## Phase 8 — Final Integration Smoke

### Task 32: End-to-end smoke test

> **COMPLETE.** Implementation lives at `src/backend/tests/integration/e2e/test_runs_e2e.py` (placed under `tests/integration/e2e/` rather than `tests/e2e/` so it can override the parent integration conftest's autouse `_start_app` fixture). Covers enqueue → `execute_run` → poll → logs (one extra step beyond the original sketch).

**Files:**
- Create: `src/backend/tests/integration/e2e/test_runs_e2e.py`

- [x] **Step 1: Write test**

```python
import pytest, asyncio

@pytest.mark.asyncio
async def test_full_roundtrip(client, api_key_headers, seeded_flow, redis_service, arq_worker_ctx):
    # 1. Enqueue via API
    body = {"flow_id": str(seeded_flow.id), "inputs": {"q": "hi"}}
    resp = await client.post("/api/v2/runs", json=body, headers=api_key_headers)
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    # 2. Process job via worker function directly (instead of spinning a worker process)
    from langflow.worker_app.execute import execute_run
    await execute_run(arq_worker_ctx, run_id)

    # 3. Poll
    resp = await client.get(f"/api/v2/runs/{run_id}", headers=api_key_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"
```

- [x] **Step 2: Run — must pass**

Run: `pytest src/backend/tests/integration/e2e/test_runs_e2e.py -v`
Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/integration/e2e/test_runs_e2e.py
git commit -m "test(runs): end-to-end roundtrip"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Tasks |
|---|---|
| Settings (`distributed_execution`, redis_url, queue names, concurrency, retention, payload, logs) | Task 2 |
| `organization.runs_max_concurrent` / `runs_priority_tier` | Task 3 |
| `flow.webhook_url` / `webhook_secret` / `auto_retry` / `max_retries` / `timeout_seconds` | Task 4 |
| `flow_runs` table + indexes + enums | Task 5 |
| `flow_run_logs` table + cascade | Task 6 |
| Redis client | Task 7 |
| Per-org Lua concurrency | Task 8 |
| Payload offload (≤1 MB inline, else object storage) | Task 9 |
| Enqueue service (priority-tier queue selection) | Task 10 |
| `POST /api/v2/runs` | Task 11 |
| `GET /api/v2/runs/{id}` + list + pagination | Task 12 |
| `POST /api/v2/runs/{id}/cancel` + Redis cancel signal | Task 13 |
| `GET /api/v2/runs/{id}/logs` | Task 14 |
| Worker settings (Arq functions + crons) | Task 15 |
| Log sink (batch-insert, truncation cap) | Task 16 |
| `execute_run` (status transitions, timeout, cancel, auto-retry, concurrency) | Tasks 17–21 |
| Reaper (stale heartbeat → failed) | Task 22 |
| Retention sweep | Task 23 |
| Webhook HMAC signing | Task 24 |
| `deliver_webhook` task + retry schedule + delivery state | Task 25 |
| Prometheus metrics | Task 26 |
| Trigger wiring (webhook/schedule/MCP) behind flag | Task 27 |
| `langflow worker` CLI | Task 28 |
| docker-compose | Task 29 |
| Helm + KEDA | Task 30 _(deferred — separate Helm repo)_ |
| Celery scaffold removal | Task 31 |
| E2E smoke | Task 32 _(complete — `tests/integration/e2e/test_runs_e2e.py`)_ |

All spec sections are covered.

**Placeholder scan:** No "TBD" / "TODO" / "fill in later" in code blocks. Two implementer-note callouts exist (`Graph.from_payload` construction path; `get_current_organization` path), both flagged with explicit grep guidance because exact resolution depends on code the plan writer hasn't seen. These are acceptable because each names a concrete discovery step, not a design decision to revisit.

**Type consistency:** `RunStatus`, `TriggeredBy`, `LogLevel`, `FlowRun`, `FlowRunLog`, `OrgConcurrency.try_acquire/release`, `PayloadOffloader.store/load`, `RunEnqueuer.enqueue`, `request_cancel`, `sign_body` — each name appears identically across every task that references it.

**Scope:** 32 tasks, all within one subsystem (distributed flow execution). Single plan is appropriate.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-15-distributed-task-runners.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
