# Observability & Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-22-observability-and-cost-design.md`
**Prior plan this depends on:** `docs/superpowers/plans/2026-04-22-metering-notifier-alerting.md` (defines `OrgUsageDaily`, `record_run_completion_and_eval`, service-factory pattern, admin tabs location).

**Goal:** Ship the per-org run history dashboard, per-flow cost visibility (LLM tokens + compute), and the pre-run cost estimator for flows with AI/agent/embedding components — driven off the same run-completion hook used by Plan 3.

**Architecture:**
- **Schema extensions:** add `flow_run_id` to `TraceTable` (fixes the missing run↔trace link), add `cost_cents` + `model_usage` to `FlowRun`, extend `OrgUsageDaily.cost_cents`, and create new `FlowUsageDaily` for per-flow-per-day rollups.
- **Pricing service:** `PricingService` wraps `litellm.model_cost` with a JSON override table; refreshed daily via arq cron.
- **Cost pipeline:** extend `record_run_completion_and_eval` (from Plan 3) to load spans for the completed run, compute per-model cost via `PricingService`, store totals on `FlowRun` + roll up into `FlowUsageDaily` and `OrgUsageDaily`.
- **Estimator:** `POST /flows/:id/estimate-cost` walks `flow.data["nodes"]`, classifies by `trace_type`/class name, applies configurable heuristics + pricing, returns `{estimate, per_component, confidence}`.
- **Dashboard API:** four new endpoints under `/api/v1/orgs/:id/usage` + `/api/v1/flows/:id/cost-summary`. Org-scoped for members; super admins can switch via `X-Acting-Org-Id`.
- **Frontend:** recharts-powered usage tab on the existing org-detail page, cost section on the flow-builder side panel, and a `CostEstimateBadge` next to the Playground button.

**Tech Stack:** SQLModel + Alembic, FastAPI, arq, litellm, React + recharts + react-query + Radix + Tailwind.

---

## File Structure

**Backend — create:**
- `src/backend/base/langflow/alembic/versions/<new-rev>_add_cost_and_flow_usage.py`
- `src/backend/base/langflow/services/database/models/flow_usage_daily/{__init__.py,model.py}`
- `src/backend/base/langflow/services/pricing/__init__.py`
- `src/backend/base/langflow/services/pricing/service.py` — `PricingService` + `ModelPrice`.
- `src/backend/base/langflow/services/pricing/factory.py`
- `src/backend/base/langflow/services/cost/__init__.py`
- `src/backend/base/langflow/services/cost/compute.py` — per-run cost computation from spans.
- `src/backend/base/langflow/services/cost/estimator.py` — pre-run estimator (node classification + pricing).
- `src/backend/base/langflow/api/v1/admin/usage_dashboard.py` — KPI / charts / per-flow endpoints.
- `src/backend/base/langflow/api/v1/flows_cost.py` — per-flow cost-summary + estimate endpoints.
- `src/backend/base/langflow/worker_app/pricing_refresh.py` — daily arq cron.
- `src/backend/tests/unit/services/pricing/test_service.py`
- `src/backend/tests/unit/services/cost/test_compute.py`
- `src/backend/tests/unit/services/cost/test_estimator.py`
- `src/backend/tests/unit/api/v1/admin/test_usage_dashboard.py`
- `src/backend/tests/unit/api/v1/test_flows_cost.py`

**Backend — modify:**
- `src/backend/base/langflow/services/database/models/flow_run/model.py` — add `cost_cents`, `model_usage`.
- `src/backend/base/langflow/services/database/models/traces/model.py` — add `flow_run_id`.
- `src/backend/base/langflow/services/database/models/org_usage_daily/model.py` — add `cost_cents`.
- `src/backend/base/langflow/services/database/models/__init__.py` — re-export `FlowUsageDaily`.
- `src/backend/base/langflow/services/schema.py` — add `PRICING_SERVICE`.
- `src/backend/base/langflow/services/deps.py` — `get_pricing_service`.
- `src/backend/base/langflow/services/utils.py` — register the factory.
- `src/backend/base/langflow/services/metering/service.py` — extend `record_run_completion_and_eval` with cost block.
- `src/backend/base/langflow/services/tracing/service.py` + `services/tracing/native.py` — thread `run_id` through to `TraceTable.flow_run_id`.
- `src/backend/base/langflow/api/v1/admin/__init__.py` — include `usage_dashboard` router.
- `src/backend/base/langflow/api/router.py` — include `flows_cost` router (non-admin).
- `src/backend/base/langflow/worker_app/settings.py` — register the pricing refresh cron.
- `src/backend/base/pyproject.toml` — promote `litellm` from `[litellm]` extra to direct dependency.
- `src/lfx/src/lfx/services/settings/base.py` — add `cost_tracking_enabled`, `cost_estimate_*`, `pricing_overrides_json`.

**Frontend — create:**
- `src/frontend/src/controllers/API/queries/usage/use-get-org-usage.ts`
- `src/frontend/src/controllers/API/queries/usage/use-get-org-usage-charts.ts`
- `src/frontend/src/controllers/API/queries/usage/use-get-org-usage-flows.ts`
- `src/frontend/src/controllers/API/queries/usage/use-get-flow-cost-summary.ts`
- `src/frontend/src/controllers/API/queries/usage/use-estimate-flow-cost.ts`
- `src/frontend/src/pages/AdminPage/organizations/OrganizationUsageTab.tsx`
- `src/frontend/src/pages/AdminPage/organizations/components/UsageKpiCards.tsx`
- `src/frontend/src/pages/AdminPage/organizations/components/UsageChart.tsx`
- `src/frontend/src/pages/AdminPage/organizations/components/PerFlowTable.tsx`
- `src/frontend/src/components/core/flowToolbarComponent/components/cost-estimate-badge.tsx`
- `src/frontend/src/pages/FlowPage/components/CostSummarySection.tsx`

**Frontend — modify:**
- `src/frontend/package.json` / `package-lock.json` — add `recharts`.
- `src/frontend/src/pages/AdminPage/organizations/OrganizationDetailPage.tsx:53-64` — add `"Usage & Alerts"` tab.
- `src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx:19` — mount `<CostEstimateBadge />`.
- `src/frontend/src/pages/FlowPage` — mount `<CostSummarySection />` in the builder side panel (exact file in the FlowPage tree).
- `src/frontend/src/controllers/API/helpers/constants.ts` — register the 5 new URL keys.

---

## Phase A — Schema additions

### Task A1: Alembic migration

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<new-rev>_add_cost_and_flow_usage.py`

- [x] **Step 1: Generate skeleton**

Run: `cd src/backend/base && uv run alembic revision -m "add_cost_and_flow_usage"`

Record `<new-rev>` and `<prev-rev>`.

- [x] **Step 2: Fill in the migration body**

```python
"""add_cost_and_flow_usage

Revision ID: <new-rev>
Revises: <prev-rev>
Create Date: <keep generated>

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<new-rev>'
down_revision: Union[str, None] = '<prev-rev>'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. trace.flow_run_id — nullable; backfill not required
    with op.batch_alter_table('trace', schema=None) as batch_op:
        batch_op.add_column(sa.Column('flow_run_id', sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f('ix_trace_flow_run_id'), ['flow_run_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_trace_flow_run_id',
            'flow_run',
            ['flow_run_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 2. flow_run.cost_cents + model_usage
    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cost_cents', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('model_usage', sa.JSON(), nullable=True))

    # 3. org_usage_daily.cost_cents
    with op.batch_alter_table('org_usage_daily', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cost_cents', sa.BigInteger(), nullable=False, server_default='0'))

    # 4. flow_usage_daily (new)
    op.create_table(
        'flow_usage_daily',
        sa.Column('flow_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('runs', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('run_seconds', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('cost_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('flow_id', 'date'),
    )
    with op.batch_alter_table('flow_usage_daily', schema=None) as batch_op:
        batch_op.create_index('ix_flow_usage_daily_org_date', ['org_id', 'date'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('flow_usage_daily', schema=None) as batch_op:
        batch_op.drop_index('ix_flow_usage_daily_org_date')
    op.drop_table('flow_usage_daily')

    with op.batch_alter_table('org_usage_daily', schema=None) as batch_op:
        batch_op.drop_column('cost_cents')

    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.drop_column('model_usage')
        batch_op.drop_column('cost_cents')

    with op.batch_alter_table('trace', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trace_flow_run_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_trace_flow_run_id'))
        batch_op.drop_column('flow_run_id')
```

- [x] **Step 3: Round-trip**

Run: `cd src/backend/base && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`

Expected: clean.

---

### Task A2: Update models

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/traces/model.py` — add `flow_run_id`.
- Modify: `src/backend/base/langflow/services/database/models/flow_run/model.py` — add `cost_cents`, `model_usage`.
- Modify: `src/backend/base/langflow/services/database/models/org_usage_daily/model.py` — add `cost_cents`.
- Create: `src/backend/base/langflow/services/database/models/flow_usage_daily/{__init__.py,model.py}`.
- Modify: `src/backend/base/langflow/services/database/models/__init__.py` — re-export new types.

- [x] **Step 1: `TraceTable` column**

In `traces/model.py`, inside the `TraceTable` class, alongside `flow_id`:

```python
    flow_run_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("flow_run.id", ondelete="SET NULL"), nullable=True, index=True),
    )
```

- [x] **Step 2: `FlowRun` columns**

In `flow_run/model.py`, add alongside the other optional fields:

```python
    cost_cents: int | None = Field(default=None, nullable=True)
    model_usage: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
```

Import `JSON` from `sqlalchemy` if not already.

- [x] **Step 3: `OrgUsageDaily.cost_cents`**

Add:

```python
    cost_cents: int = Field(default=0, nullable=False)
```

- [x] **Step 4: Create `FlowUsageDaily`**

`src/backend/base/langflow/services/database/models/flow_usage_daily/model.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class FlowUsageDaily(SQLModel, table=True):
    __tablename__ = "flow_usage_daily"

    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    date: date = Field(primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    runs: int = Field(default=0, nullable=False)
    run_seconds: int = Field(default=0, nullable=False)
    tokens: int = Field(default=0, nullable=False)
    cost_cents: int = Field(default=0, nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

`src/backend/base/langflow/services/database/models/flow_usage_daily/__init__.py`:

```python
from langflow.services.database.models.flow_usage_daily.model import FlowUsageDaily

__all__ = ["FlowUsageDaily"]
```

Update the shared models `__init__.py` to re-export.

- [x] **Step 5: Import-check**

Run: `cd src/backend && uv run python -c "from langflow.services.database.models import FlowUsageDaily; print('ok')"`

Expected: `ok`.

---

### Task A3: Commit Phase A

```bash
git add src/backend/base/langflow/alembic/versions/<new-rev>_add_cost_and_flow_usage.py \
        src/backend/base/langflow/services/database/models/traces/model.py \
        src/backend/base/langflow/services/database/models/flow_run/model.py \
        src/backend/base/langflow/services/database/models/org_usage_daily/model.py \
        src/backend/base/langflow/services/database/models/flow_usage_daily/ \
        src/backend/base/langflow/services/database/models/__init__.py

git commit -m "feat(db): cost + FlowUsageDaily schema additions

- TraceTable.flow_run_id (nullable FK, SET NULL on delete) fixes the
  missing run↔trace link so tokens can be attributed to a specific run.
- FlowRun.cost_cents + model_usage (per-model breakdown).
- OrgUsageDaily.cost_cents (extends Plan 3's table).
- New flow_usage_daily table (per-flow per-day rollup) with (flow_id, date)
  PK and (org_id, date) index.

No backfill — historical runs stay null; dashboard renders — for pre-feature
rows.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase B — PricingService

### Task B1: Promote litellm to a direct dependency

**Files:**
- Modify: `src/backend/base/pyproject.toml`

- [x] **Step 1: Move `litellm` from `[litellm]` extra to the main `dependencies` list**

Find the existing extra at around line 276:

```toml
litellm = ["litellm>=1.60.2,<2.0.0"]
```

Move `"litellm>=1.60.2,<2.0.0"` into the main `dependencies` array (top-level of the backend package). Remove the extra entry (or leave it as a no-op alias if other install paths rely on it — check the uv.lock + other pyproject references first).

- [x] **Step 2: Refresh the lock**

Run: `cd src/backend/base && uv sync`

Expected: litellm appears in `uv.lock`, no conflicts.

- [x] **Step 3: Verify import**

Run: `cd src/backend && uv run python -c "import litellm; print(hasattr(litellm, 'model_cost'))"`

Expected: `True`.

---

### Task B2: `PricingService` with unit tests

**Files:**
- Create: `src/backend/base/langflow/services/pricing/service.py`
- Create: `src/backend/base/langflow/services/pricing/__init__.py`
- Create: `src/backend/base/langflow/services/pricing/factory.py`
- Create: `src/backend/tests/unit/services/pricing/test_service.py`
- Modify: `src/backend/base/langflow/services/schema.py`, `services/deps.py`, `services/utils.py`.

- [x] **Step 1: Write the failing test**

`src/backend/tests/unit/services/pricing/test_service.py`:

```python
from __future__ import annotations

import pytest

from langflow.services.pricing.service import ModelPrice, PricingService


def test_override_beats_litellm():
    service = PricingService(
        overrides={"custom-model": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    # Without loading litellm, overrides are still resolvable
    cents = service.compute_cost_cents("custom-model", input_tokens=1000, output_tokens=1000)
    assert cents == 20  # 5 input + 15 output


def test_unknown_model_returns_zero():
    service = PricingService(overrides={})
    cents = service.compute_cost_cents("totally-made-up/model", input_tokens=1000, output_tokens=1000)
    assert cents == 0


def test_litellm_map_is_consulted_when_no_override(monkeypatch):
    import litellm

    # Shim litellm.model_cost for deterministic test.
    monkeypatch.setattr(
        litellm,
        "model_cost",
        {"claude-opus-4-7": {"input_cost_per_token": 0.000015, "output_cost_per_token": 0.000075}},
        raising=False,
    )
    service = PricingService(overrides={})
    service.reload_from_litellm()
    # 1000 input tokens -> 0.015 USD -> 1.5 cents; rounded
    cents = service.compute_cost_cents("claude-opus-4-7", input_tokens=1000, output_tokens=1000)
    # 1.5 + 7.5 = 9 cents
    assert cents == 9
```

Run: `cd src/backend && uv run pytest tests/unit/services/pricing/test_service.py -v`

Expected: FAIL — module not found.

- [x] **Step 2: Write `service.py`**

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from lfx.log.logger import logger

from langflow.services.base import Service


@dataclass(frozen=True)
class ModelPrice:
    input_cents_per_1k: float
    output_cents_per_1k: float


class PricingService(Service):
    name = "pricing_service"

    def __init__(self, overrides: dict[str, ModelPrice] | None = None) -> None:
        self._overrides: dict[str, ModelPrice] = dict(overrides or {})
        self._litellm_prices: dict[str, ModelPrice] = {}
        self._unknown_logged: set[str] = set()

    @classmethod
    def from_settings(cls, settings) -> "PricingService":
        raw = getattr(settings, "pricing_overrides_json", None) or os.environ.get(
            "PRICING_OVERRIDES_JSON", ""
        )
        overrides: dict[str, ModelPrice] = {}
        if raw:
            try:
                data = json.loads(raw)
                for model, v in data.items():
                    overrides[model] = ModelPrice(
                        input_cents_per_1k=float(v["input_cents_per_1k"]),
                        output_cents_per_1k=float(v["output_cents_per_1k"]),
                    )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                logger.warning("pricing_overrides_json parse failed: %s", exc)
        service = cls(overrides=overrides)
        service.reload_from_litellm()
        return service

    def reload_from_litellm(self) -> None:
        """Pull the current litellm model-cost map into memory."""
        try:
            import litellm
        except ImportError:
            logger.warning("litellm not installed; pricing will only use overrides")
            return

        prices: dict[str, ModelPrice] = {}
        for model, cfg in getattr(litellm, "model_cost", {}).items():
            try:
                in_per_tok = float(cfg.get("input_cost_per_token", 0.0) or 0.0)
                out_per_tok = float(cfg.get("output_cost_per_token", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            # $/token -> cents/1k tokens
            prices[model] = ModelPrice(
                input_cents_per_1k=in_per_tok * 1000.0 * 100.0,
                output_cents_per_1k=out_per_tok * 1000.0 * 100.0,
            )
        self._litellm_prices = prices
        logger.info("PricingService refreshed: %d litellm models", len(prices))

    def get_price(self, model: str) -> ModelPrice | None:
        if not model:
            return None
        if model in self._overrides:
            return self._overrides[model]
        if model in self._litellm_prices:
            return self._litellm_prices[model]
        # Try litellm's provider-prefixed matches (e.g., "anthropic/claude-opus-4-7").
        for m, price in self._litellm_prices.items():
            if m == model or m.endswith(f"/{model}") or model.endswith(f"/{m}"):
                return price
        return None

    def compute_cost_cents(self, model: str, *, input_tokens: int, output_tokens: int) -> int:
        price = self.get_price(model)
        if price is None:
            if model not in self._unknown_logged:
                logger.warning("unknown model for pricing: %s", model)
                self._unknown_logged.add(model)
            return 0
        cents = (
            (input_tokens / 1000.0) * price.input_cents_per_1k
            + (output_tokens / 1000.0) * price.output_cents_per_1k
        )
        return int(round(cents))
```

- [x] **Step 3: Factory + registration**

`src/backend/base/langflow/services/pricing/factory.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.pricing.service import PricingService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class PricingServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(PricingService)

    @override
    def create(self, settings_service: "SettingsService") -> PricingService:
        return PricingService.from_settings(settings_service.settings)
```

`__init__.py`: re-export `PricingService`, `ModelPrice`.

Add `PRICING_SERVICE = "pricing_service"` to `ServiceType`.

Append `get_pricing_service` to `services/deps.py`:

```python
def get_pricing_service():
    from langflow.services.pricing.factory import PricingServiceFactory
    return get_service(ServiceType.PRICING_SERVICE, PricingServiceFactory())
```

Register the factory in `services/utils.py` near the others.

- [x] **Step 4: Settings**

In `src/lfx/src/lfx/services/settings/base.py`, add:

```python
    cost_tracking_enabled: bool = True
    """Kill switch for the cost-computation path in record_run_completion_and_eval."""

    cost_estimate_llm_input_tokens: int = 800
    cost_estimate_llm_output_tokens: int = 400
    cost_estimate_embed_input_tokens: int = 512
    cost_estimate_agent_multiplier: int = 4
    """Heuristics for the pre-run cost estimator (Phase D)."""

    pricing_overrides_json: str = ""
    """JSON map of model-name -> {input_cents_per_1k, output_cents_per_1k}."""
```

- [x] **Step 5: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/pricing/test_service.py -v`

Expected: 3 PASS.

---

### Task B3: Daily pricing refresh cron

**Files:**
- Create: `src/backend/base/langflow/worker_app/pricing_refresh.py`
- Modify: `src/backend/base/langflow/worker_app/settings.py`

- [x] **Step 1: Write the cron body**

```python
# src/backend/base/langflow/worker_app/pricing_refresh.py
from __future__ import annotations

from lfx.log.logger import logger


async def refresh_pricing_cache(ctx) -> None:
    """Daily: reload litellm's model_cost map into PricingService."""
    try:
        from langflow.services.deps import get_pricing_service
        service = get_pricing_service()
        service.reload_from_litellm()
    except Exception as exc:  # noqa: BLE001
        logger.exception("refresh_pricing_cache failed: %s", exc)
```

- [x] **Step 2: Register the cron**

Edit `src/backend/base/langflow/worker_app/settings.py`:

```python
from langflow.worker_app.pricing_refresh import refresh_pricing_cache
# ...
cron_jobs = [
    cron(reap_lost_runs, name="reap_lost_runs", second={0, 30}),
    cron(retention_sweep, name="retention_sweep", minute=0),
    cron(audit_cleanup, name="audit_cleanup", hour=3, minute=0),  # from Plan 2
    cron(refresh_pricing_cache, name="refresh_pricing_cache", hour=0, minute=0),
]
```

- [x] **Step 3: Commit Phase B**

```bash
git add src/backend/base/langflow/services/pricing/ \
        src/backend/base/langflow/services/schema.py \
        src/backend/base/langflow/services/deps.py \
        src/backend/base/langflow/services/utils.py \
        src/backend/base/langflow/worker_app/pricing_refresh.py \
        src/backend/base/langflow/worker_app/settings.py \
        src/backend/base/pyproject.toml \
        src/backend/base/uv.lock \
        src/lfx/src/lfx/services/settings/base.py \
        src/backend/tests/unit/services/pricing/

git commit -m "feat(pricing): litellm-backed PricingService + daily refresh

PricingService wraps litellm.model_cost with a JSON-configurable
override table (via PRICING_OVERRIDES_JSON env or settings). Registered
via service-factory pattern. Daily arq cron at 00:00 UTC reloads the
litellm map. Promote litellm from optional extra to direct dependency.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase C — Cost computation + trace linkage

### Task C1: Thread `flow_run_id` into the tracer

**Files:**
- Modify: `src/backend/base/langflow/services/tracing/service.py:264-296`
- Modify: `src/backend/base/langflow/services/tracing/native.py`
- Modify: `src/backend/base/langflow/services/tracing/schemas.py` (if `TraceContext` is there; otherwise inline in service.py).

- [x] **Step 1: Extend `TraceContext` to carry `run_id`**

Locate the `TraceContext` dataclass (grep `class TraceContext`). Add:

```python
run_id: UUID | None = None
```

- [x] **Step 2: Pass `run_id` into `start_tracers`**

In `services/tracing/service.py:264`, find:

```python
async def start_tracers(
    self,
    *,
    run_id: UUID,
    run_name: str,
    user_id: str | None,
    session_id: str,
    project_name: str,
    flow_id: UUID,
) -> None:
```

Inside the body where `TraceContext(...)` is constructed (line ~283), add `run_id=run_id` to the constructor.

Then in `_initialize_native_tracer(trace_context)` (line ~292) propagate `run_id` into `NativeTracer(...)`.

- [x] **Step 3: `NativeTracer` accepts + stores `run_id`**

In `services/tracing/native.py:58-110`, add `run_id: UUID | None = None` to `__init__`. Store `self.run_id = run_id`.

In the `TraceTable(...)` instantiation site (inside `end()` or equivalent), include:

```python
flow_run_id=self.run_id,
```

- [x] **Step 4: Verify call-sites in the worker pass `run_id`**

Find the call to `start_tracers` (grep for `start_tracers(`). Ensure the arq worker passes `run_id=run.id`.

If not already, wire it at the call site in `worker_app/execute.py` or in `Graph.initialize_run` (depending on who calls `start_tracers`).

- [x] **Step 5: Smoke**

Run: `cd src/backend && uv run pytest tests/unit/services/tracing -v`

If no tracing tests exist, just run the backend app bootstrapping to confirm no regressions: `uv run python -c "from langflow.main import create_app; create_app(); print('ok')"`.

Expected: `ok`.

---

### Task C2: Per-run cost computation

**Files:**
- Create: `src/backend/base/langflow/services/cost/compute.py`
- Create: `src/backend/base/langflow/services/cost/__init__.py`
- Create: `src/backend/tests/unit/services/cost/test_compute.py`

- [x] **Step 1: Write the failing test**

`src/backend/tests/unit/services/cost/test_compute.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.cost.compute import compute_cost_for_run
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.pricing.service import ModelPrice, PricingService


@pytest.mark.asyncio
async def test_cost_sums_llm_span_tokens(session_factory):
    pricing = PricingService(
        overrides={"gpt-4o": ModelPrice(input_cents_per_1k=0.5, output_cents_per_1k=1.5)}
    )
    flow_id = uuid4()
    run_id = uuid4()

    async with session_factory() as session:
        trace = TraceTable(
            id=uuid4(),
            name="t",
            flow_id=flow_id,
            flow_run_id=run_id,
            status="OK",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            total_latency_ms=100,
            total_tokens=1000,
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)

        span_a = SpanTable(
            id=uuid4(),
            trace_id=trace.id,
            name="llm-call-1",
            trace_type="llm",
            input={"model": "gpt-4o"},
            output={},
            attributes={"prompt_tokens": 800, "completion_tokens": 400, "model_name": "gpt-4o"},
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        session.add(span_a)
        await session.commit()

        total_cents, model_usage = await compute_cost_for_run(
            session, flow_run_id=run_id, pricing=pricing
        )
    # 800/1000 * 0.5 + 400/1000 * 1.5 = 0.4 + 0.6 = 1 cent
    assert total_cents == 1
    assert "gpt-4o" in model_usage
    assert model_usage["gpt-4o"]["input_tokens"] == 800
    assert model_usage["gpt-4o"]["output_tokens"] == 400


@pytest.mark.asyncio
async def test_cost_is_zero_when_no_llm_spans(session_factory):
    pricing = PricingService(overrides={})
    total_cents, usage = await compute_cost_for_run(
        session_factory_none=None,  # not used when run has no trace
        flow_run_id=uuid4(),
        pricing=pricing,
    ) if False else (0, {})

    # Actually call the function against an empty run id.
    async with session_factory() as session:
        total, usage = await compute_cost_for_run(session, flow_run_id=uuid4(), pricing=pricing)
    assert total == 0
    assert usage == {}
```

Run: `cd src/backend && uv run pytest tests/unit/services/cost/test_compute.py -v`

Expected: FAIL.

- [x] **Step 2: Write `compute.py`**

```python
# src/backend/base/langflow/services/cost/compute.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlmodel import select

from langflow.services.database.models.traces.model import SpanTable, TraceTable

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.pricing.service import PricingService


async def compute_cost_for_run(
    session: "AsyncSession",
    *,
    flow_run_id: UUID,
    pricing: "PricingService",
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Sum cost across LLM spans for a run.

    Returns (total_cents, model_usage) where model_usage is
    {model: {input_tokens, output_tokens, cost_cents}}.
    """
    traces = (
        await session.exec(
            select(TraceTable).where(TraceTable.flow_run_id == flow_run_id)
        )
    ).all()
    if not traces:
        return 0, {}

    trace_ids = [t.id for t in traces]
    spans = (
        await session.exec(
            select(SpanTable).where(SpanTable.trace_id.in_(trace_ids))
        )
    ).all()

    per_model: dict[str, dict[str, int]] = {}
    for span in spans:
        if (getattr(span, "trace_type", None) or "").lower() not in {"llm", "embedding"}:
            continue
        attrs = span.attributes or {}
        model = str(
            attrs.get("model_name") or attrs.get("model") or ""
        ).strip()
        if not model:
            continue
        prompt = int(attrs.get("prompt_tokens") or attrs.get("input_tokens") or 0)
        completion = int(attrs.get("completion_tokens") or attrs.get("output_tokens") or 0)
        bucket = per_model.setdefault(
            model, {"input_tokens": 0, "output_tokens": 0, "cost_cents": 0}
        )
        bucket["input_tokens"] += prompt
        bucket["output_tokens"] += completion

    total_cents = 0
    for model, bucket in per_model.items():
        cents = pricing.compute_cost_cents(
            model, input_tokens=bucket["input_tokens"], output_tokens=bucket["output_tokens"]
        )
        bucket["cost_cents"] = cents
        total_cents += cents

    return total_cents, per_model
```

`__init__.py`: `from langflow.services.cost.compute import compute_cost_for_run`.

- [x] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/cost/test_compute.py -v`

Expected: PASS.

---

### Task C3: Extend `record_run_completion_and_eval` with cost + FlowUsageDaily rollup

**Files:**
- Modify: `src/backend/base/langflow/services/metering/service.py`

- [x] **Step 1: Add an upsert helper for `FlowUsageDaily`**

Append to `metering/service.py`:

```python
from langflow.services.database.models.flow_usage_daily import FlowUsageDaily


async def upsert_flow_usage_daily(
    session: "AsyncSession",
    *,
    flow_id: UUID,
    org_id: UUID,
    day: date_type,
    runs_delta: int,
    run_seconds_delta: int,
    tokens_delta: int,
    cost_cents_delta: int,
) -> None:
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    now = datetime.now(timezone.utc)
    stmt = insert_fn(FlowUsageDaily).values(
        flow_id=flow_id,
        date=day,
        org_id=org_id,
        runs=runs_delta,
        run_seconds=run_seconds_delta,
        tokens=tokens_delta,
        cost_cents=cost_cents_delta,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["flow_id", "date"],
        set_={
            "runs": FlowUsageDaily.runs + stmt.excluded.runs,
            "run_seconds": FlowUsageDaily.run_seconds + stmt.excluded.run_seconds,
            "tokens": FlowUsageDaily.tokens + stmt.excluded.tokens,
            "cost_cents": FlowUsageDaily.cost_cents + stmt.excluded.cost_cents,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.exec(stmt)
```

- [x] **Step 2: Also extend `upsert_org_usage_daily` to accept `cost_cents_delta`**

Modify the existing helper signature and the upsert's `set_` clause to include `cost_cents`. Default `cost_cents_delta: int = 0` for backward compatibility.

- [x] **Step 3: Extend `record_run_completion_and_eval`**

After the existing token-sum call, before the threshold eval, add:

```python
    # Cost computation (gated by settings.cost_tracking_enabled).
    cost_cents = 0
    model_usage: dict[str, Any] = {}
    try:
        from langflow.services.deps import get_pricing_service, get_settings_service
        if get_settings_service().settings.cost_tracking_enabled and run.flow_id is not None:
            from langflow.services.cost.compute import compute_cost_for_run
            pricing = get_pricing_service()
            cost_cents, model_usage = await compute_cost_for_run(
                session, flow_run_id=run.id, pricing=pricing
            )
            run.cost_cents = cost_cents
            run.model_usage = model_usage or None
            session.add(run)
    except Exception:  # noqa: BLE001
        logger.exception("cost computation failed for run %s", run.id)
        cost_cents = 0
        model_usage = {}
```

And extend the existing `upsert_org_usage_daily` call to include `cost_cents_delta=cost_cents`, plus add a parallel `upsert_flow_usage_daily` call:

```python
    if run.flow_id is not None:
        await upsert_flow_usage_daily(
            session,
            flow_id=run.flow_id,
            org_id=run.organization_id,
            day=day,
            runs_delta=1,
            run_seconds_delta=duration_s,
            tokens_delta=tokens,
            cost_cents_delta=cost_cents,
        )
```

- [x] **Step 4: Update the existing metering test**

In `tests/unit/services/metering/test_service.py`, extend `test_record_run_completion_upserts_counters_and_fires_threshold` to assert:
- `run.cost_cents is not None` (0 is fine if no spans).
- A `FlowUsageDaily` row exists for this flow.

- [x] **Step 5: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering tests/unit/services/cost -v`

Expected: PASS.

---

### Task C4: Commit Phase C

```bash
git add src/backend/base/langflow/services/tracing/service.py \
        src/backend/base/langflow/services/tracing/native.py \
        src/backend/base/langflow/services/tracing/ \
        src/backend/base/langflow/services/cost/ \
        src/backend/base/langflow/services/metering/service.py \
        src/backend/tests/unit/services/cost/ \
        src/backend/tests/unit/services/metering/

git commit -m "feat(cost): per-run cost computation + FlowUsageDaily rollup

- Thread flow_run_id through TraceContext → NativeTracer → TraceTable so
  costs can be attributed to specific runs.
- compute_cost_for_run sums prompt/completion tokens per model across a
  run's spans and returns (total_cents, model_usage).
- Extend record_run_completion_and_eval with a cost block (gated by
  settings.cost_tracking_enabled): write run.cost_cents + model_usage,
  upsert FlowUsageDaily, extend OrgUsageDaily.cost_cents.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase D — Pre-run estimator

### Task D1: Estimator service

**Files:**
- Create: `src/backend/base/langflow/services/cost/estimator.py`
- Create: `src/backend/tests/unit/services/cost/test_estimator.py`

- [x] **Step 1: Write the failing test**

`src/backend/tests/unit/services/cost/test_estimator.py`:

```python
from __future__ import annotations

import pytest

from langflow.services.cost.estimator import EstimatorConfig, estimate_flow_cost
from langflow.services.pricing.service import ModelPrice, PricingService


def _pricing_for(model: str, in_cents: float, out_cents: float) -> PricingService:
    return PricingService(
        overrides={model: ModelPrice(input_cents_per_1k=in_cents, output_cents_per_1k=out_cents)}
    )


def _llm_node(model: str) -> dict:
    return {
        "id": "n1",
        "data": {
            "type": "LanguageModel",
            "node": {"template": {"model_name": {"value": model}}},
        },
    }


def test_pure_llm_flow_rough_confidence():
    flow_data = {"nodes": [_llm_node("gpt-4o")]}
    pricing = _pricing_for("gpt-4o", in_cents=0.5, out_cents=1.5)
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)

    assert result.confidence == "rough"
    # 800/1000 * 0.5 + 400/1000 * 1.5 = 0.4 + 0.6 = 1 cent
    assert result.expected_cost_cents == 1
    assert result.per_component[0]["unknown"] is False


def test_unknown_model_forces_none_confidence():
    flow_data = {"nodes": [_llm_node("unknown-model")]}
    pricing = PricingService(overrides={})
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    assert result.confidence == "none"
    assert any(c["unknown"] for c in result.per_component)


def test_agent_node_multiplies_cost():
    flow_data = {
        "nodes": [
            {"id": "a", "data": {"type": "Agent", "node": {"template": {"model_name": {"value": "gpt-4o"}}}}}
        ]
    }
    pricing = _pricing_for("gpt-4o", in_cents=0.5, out_cents=1.5)
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    # Single call cost was 1 cent; agent multiplier 4 → 4 cents
    assert result.expected_cost_cents == 4
```

Run: `cd src/backend && uv run pytest tests/unit/services/cost/test_estimator.py -v`

Expected: FAIL.

- [x] **Step 2: Write `estimator.py`**

```python
# src/backend/base/langflow/services/cost/estimator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from langflow.services.pricing.service import PricingService


Confidence = Literal["rough", "low", "none"]


@dataclass(frozen=True)
class EstimatorConfig:
    llm_input: int
    llm_output: int
    embed_input: int
    agent_multiplier: int


@dataclass(frozen=True)
class EstimateResult:
    expected_cost_cents: int
    low_cost_cents: int
    high_cost_cents: int
    confidence: Confidence
    per_component: list[dict[str, Any]]


def _classify(node: dict) -> Literal["llm", "embedding", "agent", "other"]:
    data = node.get("data") or {}
    node_type = str(data.get("type") or "")
    if "Agent" in node_type:
        return "agent"
    if "Embedding" in node_type or node_type.endswith("Embeddings"):
        return "embedding"
    # Prefer the structured `trace_type` on the inner node template when present.
    inner = (data.get("node") or {}).get("trace_type") if isinstance(data.get("node"), dict) else None
    if inner == "llm":
        return "llm"
    if inner == "embedding":
        return "embedding"
    if node_type in {"LanguageModel", "LLM"}:
        return "llm"
    return "other"


def _get_model_name(node: dict) -> str:
    template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
    for k in ("model_name", "model"):
        if k in template:
            v = template[k]
            if isinstance(v, dict):
                val = v.get("value")
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return str(val[0].get("provider") or val[0].get("model") or "")
                return str(val or "")
            return str(v or "")
    return ""


def estimate_flow_cost(
    flow_data: dict,
    *,
    pricing: PricingService,
    config: EstimatorConfig,
) -> EstimateResult:
    nodes = (flow_data or {}).get("nodes") or []
    per_component: list[dict[str, Any]] = []
    expected = 0
    any_unknown = False

    for node in nodes:
        kind = _classify(node)
        if kind == "other":
            continue

        model = _get_model_name(node)
        in_tokens = config.llm_input if kind in {"llm", "agent"} else config.embed_input
        out_tokens = config.llm_output if kind in {"llm", "agent"} else 0
        calls = config.agent_multiplier if kind == "agent" else 1

        price = pricing.get_price(model) if model else None
        unknown = price is None
        if unknown:
            any_unknown = True
            cents = 0
        else:
            per_call = pricing.compute_cost_cents(model, input_tokens=in_tokens, output_tokens=out_tokens)
            cents = per_call * calls

        expected += cents
        per_component.append({
            "node_id": node.get("id"),
            "kind": kind,
            "model": model,
            "estimated_input_tokens": in_tokens * calls,
            "estimated_output_tokens": out_tokens * calls,
            "cost_cents": cents,
            "unknown": unknown,
        })

    # Confidence: none if any unknown; rough for fully-known defaults; low is reserved for
    # explicit max_tokens configs (not implemented here — spec says P0 can ship as rough/none).
    confidence: Confidence = "none" if any_unknown else "rough"
    # Low/high: +/-50% of expected (spec says "rough bounds"); documented in UI copy.
    low = int(round(expected * 0.5))
    high = int(round(expected * 1.75))
    return EstimateResult(
        expected_cost_cents=expected,
        low_cost_cents=low,
        high_cost_cents=high,
        confidence=confidence,
        per_component=per_component,
    )
```

- [x] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/cost/test_estimator.py -v`

Expected: PASS.

---

### Task D2: `POST /flows/:id/estimate-cost` endpoint

**Files:**
- Create: `src/backend/base/langflow/api/v1/flows_cost.py`
- Create: `src/backend/tests/unit/api/v1/test_flows_cost.py`
- Modify: `src/backend/base/langflow/api/router.py` — include `flows_cost` router.

- [x] **Step 1: Write the test first**

```python
# src/backend/tests/unit/api/v1/test_flows_cost.py
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_estimate_cost_endpoint(
    client: AsyncClient,
    logged_in_headers_super_user: dict,
    flow,  # existing fixture (creates a flow)
):
    resp = await client.post(
        f"api/v1/flows/{flow.id}/estimate-cost",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "estimate" in body
    assert set(body["estimate"].keys()) >= {
        "expected_cost_cents", "low_cost_cents", "high_cost_cents", "confidence"
    }
    assert "per_component" in body
```

- [x] **Step 2: Write the router**

```python
# src/backend/base/langflow/api/v1/flows_cost.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.cost.estimator import EstimatorConfig, estimate_flow_cost
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_pricing_service, get_settings_service

router = APIRouter(prefix="/flows", tags=["Flows · Cost"])


class EstimateResponse(BaseModel):
    estimate: dict
    per_component: list[dict]


@router.post("/{flow_id}/estimate-cost", response_model=EstimateResponse)
async def estimate_cost(
    flow_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> EstimateResponse:
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="flow not found")
    # Basic authorization: must share an org with the flow. Reuse existing helpers if present.

    settings = get_settings_service().settings
    config = EstimatorConfig(
        llm_input=settings.cost_estimate_llm_input_tokens,
        llm_output=settings.cost_estimate_llm_output_tokens,
        embed_input=settings.cost_estimate_embed_input_tokens,
        agent_multiplier=settings.cost_estimate_agent_multiplier,
    )
    result = estimate_flow_cost(flow.data or {}, pricing=get_pricing_service(), config=config)
    return EstimateResponse(
        estimate={
            "expected_cost_cents": result.expected_cost_cents,
            "low_cost_cents": result.low_cost_cents,
            "high_cost_cents": result.high_cost_cents,
            "confidence": result.confidence,
        },
        per_component=result.per_component,
    )
```

- [x] **Step 3: Register the router**

In `src/backend/base/langflow/api/router.py`, include it next to the existing flow routes:

```python
from langflow.api.v1.flows_cost import router as flows_cost_router
router_v1.include_router(flows_cost_router)
```

- [x] **Step 4: Commit Phase D**

```bash
git add src/backend/base/langflow/services/cost/estimator.py \
        src/backend/base/langflow/api/v1/flows_cost.py \
        src/backend/base/langflow/api/router.py \
        src/backend/tests/unit/services/cost/test_estimator.py \
        src/backend/tests/unit/api/v1/test_flows_cost.py

git commit -m "feat(cost): pre-run estimator + /flows/:id/estimate-cost

estimate_flow_cost walks flow.data['nodes'], classifies LLM / Embedding /
Agent via trace_type or class-name, applies configurable heuristics
(EstimatorConfig), and returns {expected, low, high, confidence} +
per-component breakdown. Unknown model → confidence='none'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase E — Dashboard API

### Task E1: Usage dashboard endpoints

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/usage_dashboard.py`
- Create: `src/backend/tests/unit/api/v1/admin/test_usage_dashboard.py`
- Modify: `src/backend/base/langflow/api/v1/admin/__init__.py` — include the router.

- [x] **Step 1: Write the test skeleton (happy-path only)**

```python
# src/backend/tests/unit/api/v1/admin/test_usage_dashboard.py
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_usage_kpi_endpoint_returns_current_period(
    client: AsyncClient,
    logged_in_headers_platform_admin: dict,
    seeded_org,
    session_factory,
):
    from langflow.services.database.models.org_usage_daily import OrgUsageDaily

    async with session_factory() as session:
        today = date.today()
        session.add(OrgUsageDaily(
            org_id=seeded_org.id,
            date=today,
            runs=5,
            run_seconds=300,
            tokens=1500,
            cost_cents=12,
        ))
        await session.commit()

    resp = await client.get(
        f"api/v1/orgs/{seeded_org.id}/usage?window=7d",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["runs"] >= 5
    assert body["run_seconds"] >= 300
    assert body["tokens"] >= 1500
    assert body["cost_cents"] >= 12
```

- [x] **Step 2: Write the router**

```python
# src/backend/base/langflow/api/v1/admin/usage_dashboard.py
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_usage_daily import FlowUsageDaily
from langflow.services.database.models.org_usage_daily import OrgUsageDaily

router = APIRouter(tags=["Orgs · Usage"])


Window = Literal["1d", "7d", "30d"]


def _window_to_days(w: str) -> int:
    return {"1d": 1, "7d": 7, "30d": 30}.get(w, 7)


class UsageKpi(BaseModel):
    runs: int
    run_seconds: int
    tokens: int
    cost_cents: int
    window_days: int


class UsageChartSeriesPoint(BaseModel):
    date: date
    value: int


class UsageChartResponse(BaseModel):
    metric: str
    series: list[UsageChartSeriesPoint]


class PerFlowRow(BaseModel):
    flow_id: UUID
    name: str
    runs: int
    run_seconds: int
    tokens: int
    cost_cents: int


class PerFlowResponse(BaseModel):
    items: list[PerFlowRow]
    total: int


@router.get("/orgs/{org_id}/usage", response_model=UsageKpi)
async def org_usage_kpi(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    window: Annotated[Window, Query()] = "7d",
) -> UsageKpi:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == org_id,
                OrgUsageDaily.date >= cutoff,
            )
        )
    ).all()
    return UsageKpi(
        runs=sum(r.runs for r in rows),
        run_seconds=sum(r.run_seconds for r in rows),
        tokens=sum(r.tokens for r in rows),
        cost_cents=sum(r.cost_cents for r in rows),
        window_days=days,
    )


@router.get("/orgs/{org_id}/usage/charts", response_model=UsageChartResponse)
async def org_usage_chart(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    metric: Annotated[Literal["runs", "run_seconds", "tokens", "cost_cents"], Query()] = "runs",
    window: Annotated[Window, Query()] = "30d",
) -> UsageChartResponse:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == org_id,
                OrgUsageDaily.date >= cutoff,
            ).order_by(OrgUsageDaily.date)
        )
    ).all()
    # Fill gaps with zeros so the chart stays uniform.
    by_date = {r.date: r for r in rows}
    series: list[UsageChartSeriesPoint] = []
    for i in range(days):
        d = cutoff + timedelta(days=i)
        r = by_date.get(d)
        val = getattr(r, metric, 0) if r else 0
        series.append(UsageChartSeriesPoint(date=d, value=val))
    return UsageChartResponse(metric=metric, series=series)


@router.get("/orgs/{org_id}/usage/flows", response_model=PerFlowResponse)
async def org_usage_per_flow(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    window: Annotated[Window, Query()] = "30d",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PerFlowResponse:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(
                FlowUsageDaily.flow_id,
                func.sum(FlowUsageDaily.runs).label("runs"),
                func.sum(FlowUsageDaily.run_seconds).label("run_seconds"),
                func.sum(FlowUsageDaily.tokens).label("tokens"),
                func.sum(FlowUsageDaily.cost_cents).label("cost_cents"),
            )
            .where(FlowUsageDaily.org_id == org_id, FlowUsageDaily.date >= cutoff)
            .group_by(FlowUsageDaily.flow_id)
            .order_by(func.sum(FlowUsageDaily.cost_cents).desc())
        )
    ).all()

    start = (page - 1) * size
    page_rows = rows[start : start + size]

    flow_ids = [r[0] for r in page_rows]
    name_map: dict[UUID, str] = {}
    if flow_ids:
        name_rows = (
            await session.exec(select(Flow.id, Flow.name).where(Flow.id.in_(flow_ids)))
        ).all()
        name_map = {fid: name for fid, name in name_rows}

    return PerFlowResponse(
        items=[
            PerFlowRow(
                flow_id=r[0],
                name=name_map.get(r[0], "(deleted)"),
                runs=int(r[1] or 0),
                run_seconds=int(r[2] or 0),
                tokens=int(r[3] or 0),
                cost_cents=int(r[4] or 0),
            )
            for r in page_rows
        ],
        total=len(rows),
    )
```

- [x] **Step 3: Register the router**

In `api/v1/admin/__init__.py`, include it; but note the routes are org-scoped (not admin-prefixed). Register separately in `api/router.py`:

```python
from langflow.api.v1.admin.usage_dashboard import router as usage_dashboard_router
router_v1.include_router(usage_dashboard_router)
```

*(Rename the file move if that's cleaner — the router uses `/orgs/:id/...` prefix, not `/admin/orgs/:id/...`.)*

- [x] **Step 4: Flow cost-summary endpoint**

Add to `api/v1/flows_cost.py`:

```python
@router.get("/{flow_id}/cost-summary")
async def flow_cost_summary(
    flow_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
):
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="flow not found")

    from langflow.services.database.models.flow_usage_daily import FlowUsageDaily
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=30)
    rows = (
        await session.exec(
            select(FlowUsageDaily).where(
                FlowUsageDaily.flow_id == flow_id,
                FlowUsageDaily.date >= cutoff,
            ).order_by(FlowUsageDaily.date)
        )
    ).all()
    total_cost = sum(r.cost_cents for r in rows)
    total_runs = sum(r.runs for r in rows)
    sparkline = [{"date": r.date.isoformat(), "cost_cents": r.cost_cents} for r in rows]

    return {
        "flow_id": str(flow_id),
        "window_days": 30,
        "total_cost_cents": total_cost,
        "total_runs": total_runs,
        "sparkline": sparkline,
    }
```

- [x] **Step 5: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_usage_dashboard.py tests/unit/api/v1/test_flows_cost.py -v`

Expected: PASS.

- [x] **Step 6: Commit Phase E**

```bash
git add src/backend/base/langflow/api/v1/admin/usage_dashboard.py \
        src/backend/base/langflow/api/v1/flows_cost.py \
        src/backend/base/langflow/api/router.py \
        src/backend/tests/unit/api/v1/admin/test_usage_dashboard.py \
        src/backend/tests/unit/api/v1/test_flows_cost.py

git commit -m "feat(api): usage dashboard + flow cost-summary endpoints

- GET /orgs/:id/usage (KPI cards)
- GET /orgs/:id/usage/charts (time series with gap-filling)
- GET /orgs/:id/usage/flows (per-flow breakdown, sorted by cost)
- GET /flows/:id/cost-summary (30d total + sparkline)

All org-scoped; any org member can read.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase F — Frontend

### Task F1: Install recharts + register URL constants

- [x] **Step 1: Install**

```bash
cd src/frontend && npm install recharts
```

Expected: recharts appears in `package.json` and `package-lock.json`.

- [x] **Step 2: Register URL keys**

In `src/frontend/src/controllers/API/helpers/constants.ts`, add:

```typescript
ORG_USAGE_KPI: `${BASE_URL_API}v1/orgs/`,        // per-org; path built at call site
ORG_USAGE_CHARTS: `${BASE_URL_API}v1/orgs/`,
ORG_USAGE_FLOWS: `${BASE_URL_API}v1/orgs/`,
FLOW_COST_SUMMARY: `${BASE_URL_API}v1/flows/`,
FLOW_ESTIMATE_COST: `${BASE_URL_API}v1/flows/`,
```

---

### Task F2: Write 5 react-query hooks

Mirror the Plan 3 pattern (`use-get-admin-notifications.ts`) for:

- `useGetOrgUsage({ orgId, window })` → GET `v1/orgs/:id/usage?window=...`
- `useGetOrgUsageCharts({ orgId, metric, window })` → GET `v1/orgs/:id/usage/charts?...`
- `useGetOrgUsageFlows({ orgId, window, page, size })` → GET `v1/orgs/:id/usage/flows?...`
- `useGetFlowCostSummary({ flowId })` → GET `v1/flows/:id/cost-summary`
- `useEstimateFlowCost({ flowId })` → POST `v1/flows/:id/estimate-cost`, mutation (or query triggered on-demand).

Files listed in "Frontend — create" above. Each hook is 15-25 lines following the existing pattern.

---

### Task F3: Usage dashboard tab

**Files:**
- Create: `src/frontend/src/pages/AdminPage/organizations/OrganizationUsageTab.tsx`
- Create: `src/frontend/src/pages/AdminPage/organizations/components/UsageKpiCards.tsx`
- Create: `src/frontend/src/pages/AdminPage/organizations/components/UsageChart.tsx`
- Create: `src/frontend/src/pages/AdminPage/organizations/components/PerFlowTable.tsx`
- Modify: `src/frontend/src/pages/AdminPage/organizations/OrganizationDetailPage.tsx:53-64` — add third tab.

- [x] **Step 1: Add "Usage & Alerts" tab wrapping both the dashboard and the Plan 3 thresholds/rules**

Wire `<OrganizationUsageTab />` under a new `<TabsTrigger value="usage">Usage & Alerts</TabsTrigger>`. The tab content lays out:

1. `<UsageKpiCards />` (window toggle: 1d / 7d / 30d).
2. `<UsageChart />` (metric switcher: runs | success_rate | p50 | p95 | cost; note success_rate/p50/p95 aren't in the API yet — ship with runs + run_seconds + tokens + cost_cents; the remaining metrics are a deferred extension flagged as "coming soon" in UI).
3. `<PerFlowTable />` (sortable by cost_cents default).
4. Plan 3's thresholds + alert rules admin UI nested below (or as sub-tabs).

- [x] **Step 2: `UsageKpiCards.tsx` (representative snippet)**

```tsx
import { useState } from "react";
import { useGetOrgUsage } from "@/controllers/API/queries/usage/use-get-org-usage";

type Props = { orgId: string };

export default function UsageKpiCards({ orgId }: Props) {
  const [window, setWindow] = useState<"1d" | "7d" | "30d">("7d");
  const { data } = useGetOrgUsage({ orgId, window });

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        {(["1d", "7d", "30d"] as const).map((w) => (
          <button
            key={w}
            onClick={() => setWindow(w)}
            className={`px-3 py-1 rounded ${window === w ? "bg-primary text-white" : "bg-muted"}`}
          >
            {w}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        <Card label="Runs" value={data?.runs ?? 0} />
        <Card label="Run-minutes" value={Math.round((data?.run_seconds ?? 0) / 60)} />
        <Card label="Tokens" value={data?.tokens ?? 0} />
        <Card label="Cost" value={formatCents(data?.cost_cents ?? 0)} />
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded border p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
```

- [x] **Step 3: `UsageChart.tsx` using recharts**

```tsx
import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useGetOrgUsageCharts } from "@/controllers/API/queries/usage/use-get-org-usage-charts";

type Metric = "runs" | "run_seconds" | "tokens" | "cost_cents";
type Props = { orgId: string };

export default function UsageChart({ orgId }: Props) {
  const [metric, setMetric] = useState<Metric>("runs");
  const { data } = useGetOrgUsageCharts({ orgId, metric, window: "30d" });
  const rows = (data?.series ?? []).map((p) => ({ date: p.date, value: p.value }));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        {(["runs", "run_seconds", "tokens", "cost_cents"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMetric(m)}
            className={`px-2 py-1 rounded text-sm ${metric === m ? "bg-primary text-white" : "bg-muted"}`}
          >
            {m}
          </button>
        ))}
      </div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <LineChart data={rows}>
            <XAxis dataKey="date" tickFormatter={(s) => s.slice(5)} />
            <YAxis />
            <Tooltip />
            <Line dataKey="value" type="monotone" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [x] **Step 4: `PerFlowTable.tsx`**

Render a simple HTML table (pattern from `AdminAuditLogsPage`) with columns: Flow, Runs, Run-minutes, Tokens, Cost. Click-through to `/flow/:id` (the builder). Paginate via existing data from `useGetOrgUsageFlows`.

- [x] **Step 5: Type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

---

### Task F4: Cost badge in the flow-builder toolbar

**Files:**
- Create: `src/frontend/src/components/core/flowToolbarComponent/components/cost-estimate-badge.tsx`
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx`

- [x] **Step 1: Write the badge**

```tsx
// cost-estimate-badge.tsx
import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useEstimateFlowCost } from "@/controllers/API/queries/usage/use-estimate-flow-cost";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

export default function CostEstimateBadge() {
  const flowId = useFlowsManagerStore((s) => s.currentFlow?.id) || "";
  const { mutate, data, isPending } = useEstimateFlowCost();
  const [open, setOpen] = useState(false);

  const onOpen = (o: boolean) => {
    setOpen(o);
    if (o && flowId && !data) mutate({ flowId });
  };

  const estimate = data?.estimate;
  const label =
    !estimate
      ? isPending ? "…" : "Estimate"
      : estimate.confidence === "none"
      ? "?"
      : `~$${(estimate.expected_cost_cents / 100).toFixed(2)}/run`;

  const pillClass =
    !estimate
      ? "border"
      : estimate.confidence === "low"
      ? "border border-dashed"
      : "border";

  return (
    <Popover open={open} onOpenChange={onOpen}>
      <PopoverTrigger asChild>
        <button
          className={`rounded px-2 py-1 text-sm ${pillClass}`}
          data-testid="cost-estimate-badge"
        >
          <IconComponent name="DollarSign" className="inline h-4 w-4 mr-1" />
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="text-xs text-muted-foreground mb-2">
          Estimate — actual cost varies based on inputs and agent loops.
        </div>
        {data?.per_component?.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {data.per_component.map((c: any, i: number) => (
              <li key={i} className="flex justify-between">
                <span>{c.kind} · {c.model || "?"}</span>
                <span>{c.unknown ? "?" : `$${(c.cost_cents / 100).toFixed(3)}`}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
```

- [x] **Step 2: Mount in `flow-toolbar-options.tsx`**

Edit the file (line ~19):

Before:
```tsx
<AssistantToggleButton />
<PlaygroundButton hasIO={hasIO} />
<PublishDropdown ... />
```

After:
```tsx
<AssistantToggleButton />
<PlaygroundButton hasIO={hasIO} />
<CostEstimateBadge />
<PublishDropdown ... />
```

Add the import.

---

### Task F5: Per-flow cost summary section (side panel or drawer)

**Files:**
- Create: `src/frontend/src/pages/FlowPage/components/CostSummarySection.tsx`
- Mount the new component wherever the FlowPage renders the side/sub-panels (existing side panel — identify exact file during task). If no side panel is a good fit, render as a bottom bar under the canvas or inside the Playground drawer.

```tsx
// CostSummarySection.tsx
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { useGetFlowCostSummary } from "@/controllers/API/queries/usage/use-get-flow-cost-summary";

type Props = { flowId: string };

export default function CostSummarySection({ flowId }: Props) {
  const { data } = useGetFlowCostSummary({ flowId });
  if (!data) return null;
  const sparkline = (data.sparkline ?? []).map((p: any) => ({
    date: p.date, cost: p.cost_cents,
  }));
  return (
    <div className="rounded border p-3 flex items-center gap-4">
      <div>
        <div className="text-xs text-muted-foreground">30d cost</div>
        <div className="text-lg font-semibold">
          ${(data.total_cost_cents / 100).toFixed(2)}
        </div>
      </div>
      <div style={{ width: 200, height: 40 }}>
        <ResponsiveContainer>
          <LineChart data={sparkline}>
            <Line dataKey="cost" type="monotone" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

---

### Task F6: Commit Phase F

```bash
git add src/frontend/package.json src/frontend/package-lock.json \
        src/frontend/src/controllers/API/queries/usage/ \
        src/frontend/src/controllers/API/helpers/constants.ts \
        src/frontend/src/pages/AdminPage/organizations/ \
        src/frontend/src/pages/FlowPage/components/CostSummarySection.tsx \
        src/frontend/src/components/core/flowToolbarComponent/components/cost-estimate-badge.tsx \
        src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx

git commit -m "feat(ui): usage dashboard + per-flow cost + pre-run estimator

- recharts installed for time-series charts + sparklines.
- 5 react-query hooks (org usage KPI / charts / per-flow, flow cost
  summary, estimate flow cost).
- OrganizationDetailPage gains a Usage & Alerts tab with KPI cards,
  a metric-switchable line chart, and a per-flow cost breakdown.
- CostSummarySection renders 30d spend + sparkline on the flow page.
- CostEstimateBadge pill next to Playground shows ~$/run with per-
  component breakdown on click; three visual states (rough, low,
  none) match the confidence values from the estimator API.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase G — Integration smoke + verification

### Task G1: End-to-end smoke

- [x] **Step 1: Start full stack**

Backend + FE dev servers.

- [x] **Step 2: Checklist**

| Step | Expected |
|---|---|
| Open a flow with a `LanguageModel` node using `gpt-4o` | CostEstimateBadge shows `~$X/run`, confidence=rough. |
| Open a flow with an `AgentComponent` | Badge shows cost × 4 (default agent_multiplier). |
| Open a flow with an unknown model name | Badge shows `?`, popover flags the unknown component. |
| Run the flow | Run completes. `FlowRun.cost_cents` gets populated. Navigate to `/admin/organizations/:id` → Usage tab → Today cost reflects the run. |
| Run several flows across 2-3 days | Chart shows daily cost bars. Per-flow table populates. |
| Navigate to FlowPage for a flow that has ≥1 run | CostSummarySection shows 30-day cost + sparkline. |
| Flip `cost_tracking_enabled = False` via env + restart | Run completes, no cost written. Dashboard cost stays at previous totals. |

- [x] **Step 3: Run full test suites**

Run: `cd src/backend && uv run pytest tests/unit/services/pricing tests/unit/services/cost tests/unit/services/metering tests/unit/api/v1 -q`

Expected: all PASS.

Run: `cd src/frontend && npm test -- --passWithNoTests && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: PASS.

---

## Self-review notes

1. **Spec coverage:**
   - `flow_run_id` on TraceTable → Task C1.
   - FlowRun cost_cents + model_usage → Task A2, Task C3.
   - FlowUsageDaily → Task A1, A2, C3.
   - PricingService with litellm + overrides + daily refresh → Tasks B1, B2, B3.
   - record_run_completion_and_eval cost extension (kill-switch `cost_tracking_enabled`) → Task C3.
   - Pre-run estimator with confidence semantics → Tasks D1, D2.
   - Dashboard: KPI + charts + per-flow → Task E1.
   - Per-flow cost summary → Task E1 Step 4.
   - Usage tab on OrganizationDetailPage → Task F3.
   - Cost-estimate badge next to Playground → Task F4.
   - CostSummarySection on FlowPage → Task F5.
   - recharts chosen; alternatives documented in spec → Task F1.

2. **Placeholder scan:** no TBDs. Two places reference "identify exact file during task" (the tracer `start_tracers` callsite in C1 Step 4, and the FlowPage side-panel mount in F5) — these are true unknowns pending in-IDE inspection; the research report points to the vicinity but the exact line depends on which variant of the worker path is in use.

3. **Type consistency:**
   - `EstimatorConfig`, `EstimateResult`, `ModelPrice` field names stable across estimator, pricing service, API response shape, and UI code.
   - `Confidence = Literal["rough", "low", "none"]` used consistently in backend + frontend `CostEstimateBadge`.
   - Endpoint response shapes match the pydantic models defined in each router and the react-query hook type parameters.

4. **Risks covered:**
   - Pricing drift → daily arq cron (Task B3).
   - Cost failure blast radius → `try/except` wrapper in Task C3 Step 3.
   - Unknown models → `compute_cost_cents` returns 0 + logs once per model; estimator marks confidence=none.
   - Trace linkage on legacy runs → nullable FK; dashboard renders 0/— for pre-feature runs.
   - recharts bundle size — documented as acceptable (~100KB gz).

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-04-22-observability-and-cost.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using the executing-plans skill, batch execution with checkpoints.

**Which approach?**
