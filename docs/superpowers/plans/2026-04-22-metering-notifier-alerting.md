# Metering, Pluggable Notifier & Alerting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-22-metering-notifier-alerting-design.md`

**Goal:** Ship per-org usage metering (runs, run-seconds, tokens) with configurable warning thresholds (soft only), a pluggable notifier (in-app v1, email/webhook-ready), and run-outcome alert rules (consecutive failures, error rate, per-run SLA duration). All driven from a single service function called from the existing worker run-completion hook in `worker_app/execute.py:161-190`.

**Architecture:**
- **Four new tables** in one Alembic migration: `org_usage_daily` (write-through per-org-per-day counters), `org_usage_threshold` (soft-limit config), `alert_rule` (run-outcome rule config), `admin_notification` (in-app sink).
- **Single hook point** at `execute.py:~171`. All work lives in a new service function `record_run_completion_and_eval(session, run, dispatcher)` which: upserts `OrgUsageDaily`, sums tokens from `TraceTable` for the run, evaluates thresholds + alert rules with row-level locks + cooldowns, and fires events through the `UsageAlertDispatcher`.
- **Dispatcher + notifiers** follow the `VariableServiceFactory` pattern. V1 registers only `InAppNotifier` (writes `AdminNotification` rows). Future notifiers plug in via the factory with zero changes to threshold/alert code.
- **Admin API + FE surfaces** for super admins: notification bell + center, thresholds CRUD, alert rules CRUD. React-query hooks follow the existing admin-hooks pattern.

**Tech Stack:** SQLModel + Alembic (PostgreSQL / SQLite), FastAPI, arq, React + Jest + react-query, Radix + Tailwind.

---

## File Structure

**Backend — create:**
- `src/backend/base/langflow/alembic/versions/<new-rev>_add_metering_tables.py` — single migration for all 4 tables.
- `src/backend/base/langflow/services/database/models/org_usage_daily/__init__.py` — re-exports model.
- `src/backend/base/langflow/services/database/models/org_usage_daily/model.py` — `OrgUsageDaily` SQLModel.
- `src/backend/base/langflow/services/database/models/org_usage_threshold/{__init__.py,model.py}` — `OrgUsageThreshold`.
- `src/backend/base/langflow/services/database/models/alert_rule/{__init__.py,model.py}` — `AlertRule`.
- `src/backend/base/langflow/services/database/models/admin_notification/{__init__.py,model.py}` — `AdminNotification`.
- `src/backend/base/langflow/services/metering/__init__.py` — re-exports.
- `src/backend/base/langflow/services/metering/service.py` — `MeteringService` + `record_run_completion_and_eval`.
- `src/backend/base/langflow/services/metering/factory.py` — `MeteringServiceFactory`.
- `src/backend/base/langflow/services/metering/thresholds.py` — threshold evaluator (pure logic).
- `src/backend/base/langflow/services/metering/rules.py` — alert-rule evaluator (pure logic).
- `src/backend/base/langflow/services/notifier/__init__.py` — re-exports.
- `src/backend/base/langflow/services/notifier/protocol.py` — `UsageAlertNotifier` Protocol, `UsageAlertEvent` dataclass.
- `src/backend/base/langflow/services/notifier/dispatcher.py` — `UsageAlertDispatcher` class.
- `src/backend/base/langflow/services/notifier/in_app.py` — `InAppNotifier` impl.
- `src/backend/base/langflow/services/notifier/factory.py` — `UsageAlertDispatcherFactory`.
- `src/backend/base/langflow/api/v1/admin/notifications.py` — admin notifications API.
- `src/backend/base/langflow/api/v1/admin/usage_thresholds.py` — thresholds CRUD.
- `src/backend/base/langflow/api/v1/admin/alert_rules.py` — alert-rules CRUD.
- `src/backend/tests/unit/services/metering/test_thresholds.py`
- `src/backend/tests/unit/services/metering/test_rules.py`
- `src/backend/tests/unit/services/metering/test_service.py`
- `src/backend/tests/unit/services/notifier/test_dispatcher.py`
- `src/backend/tests/unit/services/notifier/test_in_app.py`
- `src/backend/tests/unit/api/v1/admin/test_notifications.py`
- `src/backend/tests/unit/api/v1/admin/test_usage_thresholds.py`
- `src/backend/tests/unit/api/v1/admin/test_alert_rules.py`

**Backend — modify:**
- `src/backend/base/langflow/services/schema.py` — add `METERING_SERVICE`, `USAGE_ALERT_DISPATCHER`.
- `src/backend/base/langflow/services/deps.py` — add `get_metering_service()`, `get_usage_alert_dispatcher()`.
- `src/backend/base/langflow/services/utils.py` — register both new factories (around line 254).
- `src/backend/base/langflow/worker_app/execute.py:171` — insert `record_run_completion_and_eval` call.
- `src/backend/base/langflow/api/v1/admin/__init__.py` — include the three new routers.
- `src/backend/base/langflow/services/database/models/__init__.py` — re-export the four new models.

**Frontend — create:**
- `src/frontend/src/controllers/API/queries/admin/use-get-admin-notifications.ts`
- `src/frontend/src/controllers/API/queries/admin/use-get-unread-notifications-count.ts`
- `src/frontend/src/controllers/API/queries/admin/use-mark-notification-read.ts`
- `src/frontend/src/controllers/API/queries/admin/use-mark-all-notifications-read.ts`
- `src/frontend/src/controllers/API/queries/admin/use-get-usage-thresholds.ts`
- `src/frontend/src/controllers/API/queries/admin/use-create-usage-threshold.ts`
- `src/frontend/src/controllers/API/queries/admin/use-patch-usage-threshold.ts`
- `src/frontend/src/controllers/API/queries/admin/use-delete-usage-threshold.ts`
- `src/frontend/src/controllers/API/queries/admin/use-get-alert-rules.ts`
- `src/frontend/src/controllers/API/queries/admin/use-create-alert-rule.ts`
- `src/frontend/src/controllers/API/queries/admin/use-patch-alert-rule.ts`
- `src/frontend/src/controllers/API/queries/admin/use-delete-alert-rule.ts`
- `src/frontend/src/components/core/adminNotificationBell/index.tsx` — bell + dropdown in the top header.
- `src/frontend/src/pages/AdminPage/AdminNotificationsPage/index.tsx` — `/admin/notifications` page.
- `src/frontend/src/pages/AdminPage/OrgDetailPage/UsageTab.tsx` — thresholds + alert rules tabbed section under the existing org detail page.

**Frontend — modify:**
- `src/frontend/src/routes.tsx` — add the notifications and org-usage routes.
- `src/frontend/src/pages/MainPage` (or whichever file renders the main header with the user-avatar area) — mount `<AdminNotificationBell />` conditionally on `is_platform_admin`.
- `src/frontend/src/controllers/API/helpers/constants.ts` (or wherever `getURL` is configured) — register `ADMIN_NOTIFICATIONS`, `ADMIN_USAGE_THRESHOLDS`, `ADMIN_ALERT_RULES` keys.

---

## Phase A — Schema & models

### Task A1: Alembic migration for all four tables

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<new-rev>_add_metering_tables.py`

- [ ] **Step 1: Generate a skeleton migration**

Run: `cd src/backend/base && uv run alembic revision -m "add_metering_tables"`

Expected: prints the new file path under `alembic/versions/`. Record `<new-rev>` and `<prev-rev>` (printed as "Generating .../<new-rev>_add_metering_tables.py").

- [ ] **Step 2: Replace the migration body**

Edit the generated file to match this exact template (preserve the auto-generated `revision` / `down_revision` lines — don't overwrite them):

```python
"""add_metering_tables

Revision ID: <new-rev>
Revises: <prev-rev>
Create Date: <keep generated>

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '<new-rev>'
down_revision: Union[str, None] = '<prev-rev>'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # org_usage_daily
    op.create_table(
        'org_usage_daily',
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('runs', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('run_seconds', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('org_id', 'date'),
    )

    # org_usage_threshold
    op.create_table(
        'org_usage_threshold',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('metric', sa.String(length=32), nullable=False),
        sa.Column('period', sa.String(length=16), nullable=False),
        sa.Column('threshold_value', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_fired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('org_usage_threshold', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_org_usage_threshold_org_active'), ['org_id', 'is_active'], unique=False)

    # alert_rule
    op.create_table(
        'alert_rule',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('flow_id', sa.Uuid(), nullable=True),
        sa.Column('rule_type', sa.String(length=32), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_fired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='900'),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('alert_rule', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alert_rule_org_flow_active'), ['org_id', 'flow_id', 'is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_alert_rule_org_active'), ['org_id', 'is_active'], unique=False)

    # admin_notification
    op.create_table(
        'admin_notification',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='warning'),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('audience', sa.String(length=32), nullable=False, server_default='super_admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_by_user_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['read_by_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('admin_notification', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_admin_notification_audience_read_created'),
            ['audience', 'read_at', 'created_at'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('admin_notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_notification_audience_read_created'))
    op.drop_table('admin_notification')

    with op.batch_alter_table('alert_rule', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_rule_org_active'))
        batch_op.drop_index(batch_op.f('ix_alert_rule_org_flow_active'))
    op.drop_table('alert_rule')

    with op.batch_alter_table('org_usage_threshold', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_org_usage_threshold_org_active'))
    op.drop_table('org_usage_threshold')

    op.drop_table('org_usage_daily')
```

Replace the two `<new-rev>` placeholders and the `<prev-rev>` placeholder with the values alembic generated. Keep the `Create Date` as generated.

- [ ] **Step 3: Apply + rollback to verify migration works both directions**

Run: `cd src/backend/base && uv run alembic upgrade head`

Expected: exit 0, no errors. The four tables exist.

Run: `cd src/backend/base && uv run alembic downgrade -1 && uv run alembic upgrade head`

Expected: both succeed; tables round-trip cleanly.

---

### Task A2: `OrgUsageDaily` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/org_usage_daily/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/org_usage_daily/model.py`

- [ ] **Step 1: Write `model.py`**

Create `src/backend/base/langflow/services/database/models/org_usage_daily/model.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel

if TYPE_CHECKING:
    pass


class OrgUsageDaily(SQLModel, table=True):
    __tablename__ = "org_usage_daily"

    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    date: date = Field(primary_key=True, nullable=False)
    runs: int = Field(default=0, nullable=False)
    run_seconds: int = Field(default=0, nullable=False)
    tokens: int = Field(default=0, nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 2: Re-export from `__init__.py`**

Create `src/backend/base/langflow/services/database/models/org_usage_daily/__init__.py`:

```python
from langflow.services.database.models.org_usage_daily.model import OrgUsageDaily

__all__ = ["OrgUsageDaily"]
```

---

### Task A3: `OrgUsageThreshold` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/org_usage_threshold/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/org_usage_threshold/model.py`

- [ ] **Step 1: Write `model.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class UsageMetric(str, Enum):
    RUNS = "runs"
    RUN_SECONDS = "run_seconds"
    TOKENS = "tokens"


class UsagePeriod(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class OrgUsageThreshold(SQLModel, table=True):
    __tablename__ = "org_usage_threshold"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    metric: UsageMetric = Field(max_length=32, nullable=False)
    period: UsagePeriod = Field(max_length=16, nullable=False)
    threshold_value: int = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    last_fired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    cooldown_seconds: int = Field(default=3600, nullable=False)
    created_by_user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id"), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 2: Re-export**

```python
# src/backend/base/langflow/services/database/models/org_usage_threshold/__init__.py
from langflow.services.database.models.org_usage_threshold.model import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)

__all__ = ["OrgUsageThreshold", "UsageMetric", "UsagePeriod"]
```

---

### Task A4: `AlertRule` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/alert_rule/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/alert_rule/model.py`

- [ ] **Step 1: Write `model.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class AlertRuleType(str, Enum):
    CONSECUTIVE_FAILURES = "consecutive_failures"
    ERROR_RATE = "error_rate"
    SLA_DURATION = "sla_duration"


class AlertRule(SQLModel, table=True):
    __tablename__ = "alert_rule"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=True),
    )
    rule_type: AlertRuleType = Field(max_length=32, nullable=False)
    config: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    is_active: bool = Field(default=True, nullable=False)
    last_fired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    cooldown_seconds: int = Field(default=900, nullable=False)
    created_by_user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id"), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 2: Re-export**

```python
# src/backend/base/langflow/services/database/models/alert_rule/__init__.py
from langflow.services.database.models.alert_rule.model import AlertRule, AlertRuleType

__all__ = ["AlertRule", "AlertRuleType"]
```

---

### Task A5: `AdminNotification` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/admin_notification/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/admin_notification/model.py`

- [ ] **Step 1: Write `model.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class NotificationCategory(str, Enum):
    USAGE_THRESHOLD = "usage_threshold"
    ALERT_RULE = "alert_rule"
    SYSTEM = "system"


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationAudience(str, Enum):
    SUPER_ADMIN = "super_admin"


class AdminNotification(SQLModel, table=True):
    __tablename__ = "admin_notification"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
    )
    category: NotificationCategory = Field(max_length=32, nullable=False)
    severity: NotificationSeverity = Field(max_length=16, default=NotificationSeverity.WARNING, nullable=False)
    title: str = Field(max_length=512, nullable=False)
    body_md: str = Field(nullable=False)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    audience: NotificationAudience = Field(
        max_length=32, default=NotificationAudience.SUPER_ADMIN, nullable=False,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    read_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    read_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
```

- [ ] **Step 2: Re-export**

```python
# src/backend/base/langflow/services/database/models/admin_notification/__init__.py
from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)

__all__ = [
    "AdminNotification",
    "NotificationAudience",
    "NotificationCategory",
    "NotificationSeverity",
]
```

- [ ] **Step 3: Register all four models in the shared package index**

Open `src/backend/base/langflow/services/database/models/__init__.py` and add these re-exports next to the existing ones (look for the block that re-exports `Organization`, `Flow`, etc.):

```python
from langflow.services.database.models.admin_notification import AdminNotification
from langflow.services.database.models.alert_rule import AlertRule
from langflow.services.database.models.org_usage_daily import OrgUsageDaily
from langflow.services.database.models.org_usage_threshold import OrgUsageThreshold
```

Add their names to `__all__` if the module has one.

- [ ] **Step 4: Import-check**

Run: `cd src/backend && uv run python -c "from langflow.services.database.models import AdminNotification, AlertRule, OrgUsageDaily, OrgUsageThreshold; print('ok')"`

Expected: `ok`.

---

### Task A6: Commit Phase A

- [ ] **Step 1: Stage + commit**

```bash
git add src/backend/base/langflow/alembic/versions/<new-rev>_add_metering_tables.py \
        src/backend/base/langflow/services/database/models/org_usage_daily/ \
        src/backend/base/langflow/services/database/models/org_usage_threshold/ \
        src/backend/base/langflow/services/database/models/alert_rule/ \
        src/backend/base/langflow/services/database/models/admin_notification/ \
        src/backend/base/langflow/services/database/models/__init__.py

git commit -m "feat(db): metering + alerting schema

Add four new tables via a single migration:
- org_usage_daily (write-through per-org/day counters)
- org_usage_threshold (soft-limit config, no hard stops)
- alert_rule (run-outcome rules: consecutive_failures, error_rate, sla_duration)
- admin_notification (in-app super-admin sink)

All FKs cascade from organization; FKs from flow cascade from flow.
Indexes cover the query shapes needed by the run-completion hook and
the admin feed. No data backfill — counters start empty and fill forward.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval before committing if the no-commits-without-permission rule is active.**

---

## Phase B — Pluggable notifier infrastructure

### Task B1: `UsageAlertEvent` + `UsageAlertNotifier` protocol

**Files:**
- Create: `src/backend/base/langflow/services/notifier/__init__.py`
- Create: `src/backend/base/langflow/services/notifier/protocol.py`

- [ ] **Step 1: Write protocol + event dataclass**

`src/backend/base/langflow/services/notifier/protocol.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID


NotificationCategoryValue = Literal["usage_threshold", "alert_rule"]
NotificationSeverityValue = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class UsageAlertEvent:
    category: NotificationCategoryValue
    severity: NotificationSeverityValue
    org_id: UUID
    title: str
    body_md: str
    metadata: dict[str, Any]


class UsageAlertNotifier(Protocol):
    """Pluggable sink for usage/alert notifications.

    Implementations must be idempotent-safe: the dispatcher may retry on
    transient failures, and a notifier raising must not block siblings.
    """

    async def notify(self, event: UsageAlertEvent) -> None: ...
```

- [ ] **Step 2: Re-export**

`src/backend/base/langflow/services/notifier/__init__.py`:

```python
from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier

__all__ = ["UsageAlertEvent", "UsageAlertNotifier"]
```

---

### Task B2: `UsageAlertDispatcher` with unit test

**Files:**
- Create: `src/backend/base/langflow/services/notifier/dispatcher.py`
- Create: `src/backend/tests/unit/services/notifier/__init__.py` (empty)
- Create: `src/backend/tests/unit/services/notifier/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

`src/backend/tests/unit/services/notifier/test_dispatcher.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest

from langflow.services.notifier.dispatcher import UsageAlertDispatcher
from langflow.services.notifier.protocol import UsageAlertEvent


def _event() -> UsageAlertEvent:
    return UsageAlertEvent(
        category="usage_threshold",
        severity="warning",
        org_id=uuid4(),
        title="test",
        body_md="x",
        metadata={},
    )


class _Recorder:
    def __init__(self) -> None:
        self.seen: list[UsageAlertEvent] = []

    async def notify(self, event: UsageAlertEvent) -> None:
        self.seen.append(event)


class _Exploder:
    async def notify(self, event: UsageAlertEvent) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_dispatcher_fans_out_to_all_notifiers():
    a, b = _Recorder(), _Recorder()
    dispatcher = UsageAlertDispatcher([a, b])
    event = _event()

    await dispatcher.dispatch(event)

    assert a.seen == [event]
    assert b.seen == [event]


@pytest.mark.asyncio
async def test_dispatcher_isolates_notifier_failures():
    good = _Recorder()
    dispatcher = UsageAlertDispatcher([_Exploder(), good])
    event = _event()

    # Must not raise even though one notifier raises.
    await dispatcher.dispatch(event)

    assert good.seen == [event]


@pytest.mark.asyncio
async def test_dispatcher_with_empty_notifier_list_is_noop():
    dispatcher = UsageAlertDispatcher([])
    # Must not raise
    await dispatcher.dispatch(_event())
```

Run: `cd src/backend && uv run pytest tests/unit/services/notifier/test_dispatcher.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'langflow.services.notifier.dispatcher'`.

- [ ] **Step 2: Write the dispatcher**

`src/backend/base/langflow/services/notifier/dispatcher.py`:

```python
from __future__ import annotations

import asyncio

from lfx.log.logger import logger

from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier


class UsageAlertDispatcher:
    """Fan-out dispatcher. A failing notifier is logged but does not block siblings."""

    def __init__(self, notifiers: list[UsageAlertNotifier]) -> None:
        self._notifiers = list(notifiers)

    async def dispatch(self, event: UsageAlertEvent) -> None:
        if not self._notifiers:
            return
        results = await asyncio.gather(
            *(self._safe_notify(n, event) for n in self._notifiers),
            return_exceptions=False,  # _safe_notify swallows
        )
        del results  # kept for future metrics hook

    @staticmethod
    async def _safe_notify(notifier: UsageAlertNotifier, event: UsageAlertEvent) -> None:
        try:
            await notifier.notify(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "notifier=%s failed on event.category=%s org_id=%s: %s",
                type(notifier).__name__,
                event.category,
                event.org_id,
                exc,
            )
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/notifier/test_dispatcher.py -v`

Expected: 3 PASS.

---

### Task B3: `InAppNotifier` with unit test

**Files:**
- Create: `src/backend/base/langflow/services/notifier/in_app.py`
- Create: `src/backend/tests/unit/services/notifier/test_in_app.py`

- [ ] **Step 1: Write the failing test**

`src/backend/tests/unit/services/notifier/test_in_app.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.notifier.in_app import InAppNotifier
from langflow.services.notifier.protocol import UsageAlertEvent


@pytest.mark.asyncio
async def test_in_app_notifier_writes_admin_notification_row(client, session_factory):
    # client is unused but triggers app startup / schema.
    notifier = InAppNotifier(session_factory)
    org_id = uuid4()
    event = UsageAlertEvent(
        category="usage_threshold",
        severity="warning",
        org_id=org_id,
        title="Daily tokens exceeded 10000",
        body_md="Your org crossed the **10000 tokens/day** threshold.",
        metadata={"threshold_id": str(uuid4()), "metric": "tokens", "value": 10050},
    )

    await notifier.notify(event)

    async with session_factory() as session:
        rows = (await session.exec(select(AdminNotification))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.org_id == org_id
    assert row.category == NotificationCategory.USAGE_THRESHOLD
    assert row.severity == NotificationSeverity.WARNING
    assert row.audience == NotificationAudience.SUPER_ADMIN
    assert row.title == event.title
    assert row.body_md == event.body_md
    assert row.metadata_json["metric"] == "tokens"
    assert row.read_at is None
```

Assume `session_factory` is available as a fixture via `conftest.py` (it already is via `db_service.async_session_maker`). If not, derive it from `get_db_service()` in the test.

Run: `cd src/backend && uv run pytest tests/unit/services/notifier/test_in_app.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'langflow.services.notifier.in_app'`.

- [ ] **Step 2: Write the notifier**

`src/backend/base/langflow/services/notifier/in_app.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from sqlmodel.ext.asyncio.session import AsyncSession


class InAppNotifier(UsageAlertNotifier):
    """Persists UsageAlertEvent into the admin_notification table, audience=super_admin."""

    def __init__(
        self,
        session_factory: "Callable[[], AbstractAsyncContextManager[AsyncSession]]",
    ) -> None:
        self._session_factory = session_factory

    async def notify(self, event: UsageAlertEvent) -> None:
        row = AdminNotification(
            org_id=event.org_id,
            category=NotificationCategory(event.category),
            severity=NotificationSeverity(event.severity),
            title=event.title,
            body_md=event.body_md,
            metadata_json=dict(event.metadata),
            audience=NotificationAudience.SUPER_ADMIN,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/notifier/test_in_app.py -v`

Expected: PASS.

---

### Task B4: Dispatcher factory + service registration

**Files:**
- Create: `src/backend/base/langflow/services/notifier/factory.py`
- Modify: `src/backend/base/langflow/services/schema.py`
- Modify: `src/backend/base/langflow/services/deps.py`
- Modify: `src/backend/base/langflow/services/utils.py`

- [ ] **Step 1: Write the factory**

`src/backend/base/langflow/services/notifier/factory.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.notifier.dispatcher import UsageAlertDispatcher
from langflow.services.notifier.in_app import InAppNotifier

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


class UsageAlertDispatcherFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(UsageAlertDispatcher)

    @override
    def create(self, database_service: "DatabaseService") -> UsageAlertDispatcher:
        # v1: only InAppNotifier. Future notifiers are added here, gated on settings.
        notifiers = [InAppNotifier(database_service.async_session_maker)]
        return UsageAlertDispatcher(notifiers)
```

- [ ] **Step 2: Add the enum value**

Edit `src/backend/base/langflow/services/schema.py` and add the new value at the bottom of the enum (preserving existing order):

```python
    USAGE_ALERT_DISPATCHER = "usage_alert_dispatcher"
```

- [ ] **Step 3: Add the getter**

Append to `src/backend/base/langflow/services/deps.py` (after the existing `get_variable_service`):

```python
def get_usage_alert_dispatcher():
    """Retrieves the UsageAlertDispatcher instance from the service manager."""
    from langflow.services.notifier.factory import UsageAlertDispatcherFactory

    return get_service(ServiceType.USAGE_ALERT_DISPATCHER, UsageAlertDispatcherFactory())
```

- [ ] **Step 4: Register the factory at startup**

In `src/backend/base/langflow/services/utils.py`, near line 254 (where `variable_factory.VariableServiceFactory()` is registered), add:

```python
    from langflow.services.notifier import factory as notifier_factory
    service_manager.register_factory(notifier_factory.UsageAlertDispatcherFactory())
```

Place the import at the top of the function alongside the other factory imports (or keep it local — follow whichever style is used by neighbouring factories). If there's an existing import block for the factories, add the `notifier_factory` import there and drop the in-function import.

- [ ] **Step 5: Smoke-test**

Run: `cd src/backend && uv run python -c "
import asyncio
from langflow.services.utils import initialize_services
from langflow.services.deps import get_usage_alert_dispatcher

async def main():
    await initialize_services()
    d = get_usage_alert_dispatcher()
    print(type(d).__name__)

asyncio.run(main())
"`

Expected: prints `UsageAlertDispatcher`.

---

### Task B5: Commit Phase B

- [ ] **Step 1: Stage and commit**

```bash
git add src/backend/base/langflow/services/notifier/ \
        src/backend/base/langflow/services/schema.py \
        src/backend/base/langflow/services/deps.py \
        src/backend/base/langflow/services/utils.py \
        src/backend/tests/unit/services/notifier/

git commit -m "feat(notifier): pluggable usage-alert dispatcher

Introduce UsageAlertNotifier protocol + UsageAlertEvent dataclass,
UsageAlertDispatcher (fan-out, isolates notifier failures), and
InAppNotifier that persists events to admin_notification.

Register UsageAlertDispatcher via the existing service factory pattern
so future notifiers (email/webhook/Slack) plug in without touching
threshold or alerting code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval if required.**

---

## Phase C — Metering service (OrgUsageDaily upsert + token attribution)

### Task C1: Metering service skeleton + daily-counter upsert test

**Files:**
- Create: `src/backend/base/langflow/services/metering/__init__.py`
- Create: `src/backend/base/langflow/services/metering/service.py`
- Create: `src/backend/tests/unit/services/metering/__init__.py` (empty)
- Create: `src/backend/tests/unit/services/metering/test_service.py`

- [ ] **Step 1: Write the failing test for the upsert helper**

`src/backend/tests/unit/services/metering/test_service.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.org_usage_daily import OrgUsageDaily
from langflow.services.metering.service import upsert_org_usage_daily


@pytest.mark.asyncio
async def test_upsert_creates_row_when_absent(session_factory):
    org_id = uuid4()
    day = date(2026, 4, 22)

    async with session_factory() as session:
        await upsert_org_usage_daily(
            session,
            org_id=org_id,
            day=day,
            runs_delta=1,
            run_seconds_delta=30,
            tokens_delta=1250,
        )
        await session.commit()

        row = (
            await session.exec(
                select(OrgUsageDaily).where(OrgUsageDaily.org_id == org_id, OrgUsageDaily.date == day)
            )
        ).one()

    assert row.runs == 1
    assert row.run_seconds == 30
    assert row.tokens == 1250


@pytest.mark.asyncio
async def test_upsert_accumulates_into_existing_row(session_factory):
    org_id = uuid4()
    day = date(2026, 4, 22)

    async with session_factory() as session:
        await upsert_org_usage_daily(session, org_id=org_id, day=day, runs_delta=1, run_seconds_delta=10, tokens_delta=100)
        await upsert_org_usage_daily(session, org_id=org_id, day=day, runs_delta=2, run_seconds_delta=20, tokens_delta=200)
        await session.commit()

        row = (
            await session.exec(
                select(OrgUsageDaily).where(OrgUsageDaily.org_id == org_id, OrgUsageDaily.date == day)
            )
        ).one()

    assert row.runs == 3
    assert row.run_seconds == 30
    assert row.tokens == 300


@pytest.mark.asyncio
async def test_upsert_partitions_by_org_and_date(session_factory):
    org_a, org_b = uuid4(), uuid4()
    d1, d2 = date(2026, 4, 22), date(2026, 4, 23)

    async with session_factory() as session:
        await upsert_org_usage_daily(session, org_id=org_a, day=d1, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await upsert_org_usage_daily(session, org_id=org_a, day=d2, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await upsert_org_usage_daily(session, org_id=org_b, day=d1, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await session.commit()

        all_rows = (await session.exec(select(OrgUsageDaily))).all()

    assert len(all_rows) == 3
```

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_service.py -v`

Expected: FAIL — module not found.

- [ ] **Step 2: Write the helper**

`src/backend/base/langflow/services/metering/service.py`:

```python
from __future__ import annotations

from datetime import date as date_type, datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import select

from langflow.services.database.models.org_usage_daily import OrgUsageDaily

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def upsert_org_usage_daily(
    session: "AsyncSession",
    *,
    org_id: UUID,
    day: date_type,
    runs_delta: int,
    run_seconds_delta: int,
    tokens_delta: int,
) -> None:
    """Atomic per-(org, date) counter upsert.

    Uses INSERT ... ON CONFLICT DO UPDATE on both Postgres and SQLite so
    two workers completing the same day concurrently never drop a count.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    now = datetime.now(timezone.utc)
    stmt = insert_fn(OrgUsageDaily).values(
        org_id=org_id,
        date=day,
        runs=runs_delta,
        run_seconds=run_seconds_delta,
        tokens=tokens_delta,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["org_id", "date"],
        set_={
            "runs": OrgUsageDaily.runs + stmt.excluded.runs,
            "run_seconds": OrgUsageDaily.run_seconds + stmt.excluded.run_seconds,
            "tokens": OrgUsageDaily.tokens + stmt.excluded.tokens,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.exec(stmt)
```

Also create the package marker:

`src/backend/base/langflow/services/metering/__init__.py`:

```python
from langflow.services.metering.service import upsert_org_usage_daily

__all__ = ["upsert_org_usage_daily"]
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_service.py -v`

Expected: 3 PASS.

---

### Task C2: Token attribution helper

**Files:**
- Modify: `src/backend/base/langflow/services/metering/service.py`
- Modify: `src/backend/tests/unit/services/metering/test_service.py` — add one test

- [ ] **Step 1: Write the failing test**

Append to the existing test module:

```python
from langflow.services.database.models.traces.model import SpanTable, TraceTable


@pytest.mark.asyncio
async def test_sum_tokens_for_flow_day(session_factory):
    from datetime import datetime

    flow_id = uuid4()
    target_day = date(2026, 4, 22)

    async with session_factory() as session:
        # trace on target day, same flow
        trace = TraceTable(
            id=uuid4(),
            flow_id=flow_id,
            trace_id="t1",
            trace_name="run",
            trace_type="flow",
            session_id=None,
            total_tokens=500,
            start_time=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 22, 10, 1, tzinfo=timezone.utc),
        )
        # trace on target day, different flow — must be excluded
        trace_other = TraceTable(
            id=uuid4(),
            flow_id=uuid4(),
            trace_id="t2",
            trace_name="run",
            trace_type="flow",
            session_id=None,
            total_tokens=9999,
            start_time=datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 22, 11, 1, tzinfo=timezone.utc),
        )
        # trace on adjacent day — must be excluded
        trace_prev_day = TraceTable(
            id=uuid4(),
            flow_id=flow_id,
            trace_id="t3",
            trace_name="run",
            trace_type="flow",
            session_id=None,
            total_tokens=100,
            start_time=datetime(2026, 4, 21, 23, 59, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 21, 23, 59, tzinfo=timezone.utc),
        )
        session.add_all([trace, trace_other, trace_prev_day])
        await session.commit()

        from langflow.services.metering.service import sum_tokens_for_flow_day
        total = await sum_tokens_for_flow_day(session, flow_id=flow_id, day=target_day)

    assert total == 500
```

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_service.py::test_sum_tokens_for_flow_day -v`

Expected: FAIL — `sum_tokens_for_flow_day` not defined.

- [ ] **Step 2: Write the helper**

Append to `src/backend/base/langflow/services/metering/service.py`:

```python
from datetime import datetime, time

from sqlalchemy import func
from sqlmodel import select as sm_select

from langflow.services.database.models.traces.model import TraceTable


async def sum_tokens_for_flow_day(
    session: "AsyncSession",
    *,
    flow_id: UUID,
    day: date_type,
) -> int:
    """Sum total_tokens across traces for a flow on a specific UTC day.

    Attribution window is [start_of_day_utc, end_of_day_utc]; traces with a null
    total_tokens are ignored.
    """
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)

    stmt = sm_select(func.coalesce(func.sum(TraceTable.total_tokens), 0)).where(
        TraceTable.flow_id == flow_id,
        TraceTable.start_time >= start,
        TraceTable.start_time <= end,
    )
    result = await session.exec(stmt)
    return int(result.one())
```

Update `__init__.py` to re-export:

```python
from langflow.services.metering.service import sum_tokens_for_flow_day, upsert_org_usage_daily

__all__ = ["sum_tokens_for_flow_day", "upsert_org_usage_daily"]
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_service.py -v`

Expected: 4 PASS.

---

### Task C3: Commit Phase C

- [ ] **Step 1: Commit**

```bash
git add src/backend/base/langflow/services/metering/ \
        src/backend/tests/unit/services/metering/

git commit -m "feat(metering): per-org daily counters + token attribution

Add upsert_org_usage_daily (atomic INSERT ... ON CONFLICT on both
Postgres and SQLite) and sum_tokens_for_flow_day. Both helpers are
pure service-layer functions callable from the worker run-completion
hook; threshold/alert eval and the run-completion service function
will compose them in Phase D.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase D — Evaluators + run-completion service + hook

### Task D1: Threshold evaluator (pure, no DB)

**Files:**
- Create: `src/backend/base/langflow/services/metering/thresholds.py`
- Create: `src/backend/tests/unit/services/metering/test_thresholds.py`

- [ ] **Step 1: Write the failing test**

`src/backend/tests/unit/services/metering/test_thresholds.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)
from langflow.services.metering.thresholds import check_threshold_crossed


def _threshold(**over) -> OrgUsageThreshold:
    defaults = dict(
        id=uuid4(),
        org_id=uuid4(),
        metric=UsageMetric.RUNS,
        period=UsagePeriod.DAILY,
        threshold_value=100,
        is_active=True,
        last_fired_at=None,
        cooldown_seconds=3600,
        created_by_user_id=uuid4(),
    )
    defaults.update(over)
    return OrgUsageThreshold(**defaults)


def test_crossing_upward_fires():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=99, current=101, now=datetime.now(timezone.utc)) is True


def test_exactly_hitting_the_threshold_fires():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=99, current=100, now=datetime.now(timezone.utc)) is True


def test_already_above_does_not_re_fire():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=120, current=150, now=datetime.now(timezone.utc)) is False


def test_below_threshold_does_not_fire():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=50, current=75, now=datetime.now(timezone.utc)) is False


def test_inactive_threshold_does_not_fire():
    t = _threshold(threshold_value=100, is_active=False)
    assert check_threshold_crossed(t, previous=99, current=101, now=datetime.now(timezone.utc)) is False


def test_cooldown_suppresses_re_fire():
    now = datetime.now(timezone.utc)
    t = _threshold(
        threshold_value=100,
        last_fired_at=now - timedelta(minutes=30),
        cooldown_seconds=3600,  # 1 hr
    )
    assert check_threshold_crossed(t, previous=150, current=200, now=now) is False


def test_cooldown_elapsed_allows_re_fire_on_new_crossing():
    now = datetime.now(timezone.utc)
    t = _threshold(
        threshold_value=100,
        last_fired_at=now - timedelta(hours=2),
        cooldown_seconds=3600,
    )
    # The counters reset at period boundary, so a new crossing looks like 80 -> 120.
    assert check_threshold_crossed(t, previous=80, current=120, now=now) is True
```

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_thresholds.py -v`

Expected: FAIL — module not found.

- [ ] **Step 2: Write the evaluator**

`src/backend/base/langflow/services/metering/thresholds.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta

from langflow.services.database.models.org_usage_threshold import OrgUsageThreshold


def check_threshold_crossed(
    threshold: OrgUsageThreshold,
    *,
    previous: int,
    current: int,
    now: datetime,
) -> bool:
    """Return True iff this is a fresh upward crossing that clears cooldown."""
    if not threshold.is_active:
        return False
    if current < threshold.threshold_value:
        return False
    if previous >= threshold.threshold_value:
        # Already above — only re-fire on a fresh crossing (handled by period reset).
        return False
    if threshold.last_fired_at is not None:
        elapsed = now - threshold.last_fired_at
        if elapsed < timedelta(seconds=threshold.cooldown_seconds):
            return False
    return True
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_thresholds.py -v`

Expected: 7 PASS.

---

### Task D2: Alert-rule evaluators (pure, no DB)

**Files:**
- Create: `src/backend/base/langflow/services/metering/rules.py`
- Create: `src/backend/tests/unit/services/metering/test_rules.py`

- [ ] **Step 1: Write the failing tests**

`src/backend/tests/unit/services/metering/test_rules.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import RunStatus
from langflow.services.metering.rules import (
    RunSummary,
    eval_consecutive_failures,
    eval_error_rate,
    eval_sla_duration,
    is_failure,
)


def _rule(rule_type: AlertRuleType, config: dict) -> AlertRule:
    return AlertRule(
        id=uuid4(),
        org_id=uuid4(),
        flow_id=None,
        rule_type=rule_type,
        config=config,
        is_active=True,
        last_fired_at=None,
        cooldown_seconds=0,
        created_by_user_id=uuid4(),
    )


def _summary(status: RunStatus, finished: datetime, duration_s: float = 5.0) -> RunSummary:
    return RunSummary(
        status=status,
        finished_at=finished,
        duration_seconds=duration_s,
    )


def test_is_failure_classifies_terminal_states():
    assert is_failure(RunStatus.FAILED)
    assert is_failure(RunStatus.TIMED_OUT)
    assert not is_failure(RunStatus.SUCCEEDED)
    assert not is_failure(RunStatus.CANCELLED)


def test_consecutive_failures_fires_at_threshold():
    rule = _rule(AlertRuleType.CONSECUTIVE_FAILURES, {"n": 3})
    now = datetime.now(timezone.utc)
    recent = [
        _summary(RunStatus.FAILED, now - timedelta(minutes=i)) for i in range(3)
    ]
    assert eval_consecutive_failures(rule, recent_runs=recent, now=now) is True


def test_consecutive_failures_breaks_on_success():
    rule = _rule(AlertRuleType.CONSECUTIVE_FAILURES, {"n": 3})
    now = datetime.now(timezone.utc)
    recent = [
        _summary(RunStatus.FAILED, now - timedelta(minutes=1)),
        _summary(RunStatus.SUCCEEDED, now - timedelta(minutes=2)),
        _summary(RunStatus.FAILED, now - timedelta(minutes=3)),
    ]
    assert eval_consecutive_failures(rule, recent_runs=recent, now=now) is False


def test_error_rate_needs_min_samples():
    rule = _rule(AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 10, "rate_pct": 50})
    now = datetime.now(timezone.utc)
    small_sample = [_summary(RunStatus.FAILED, now) for _ in range(5)]
    assert eval_error_rate(rule, recent_runs=small_sample, now=now) is False


def test_error_rate_fires_on_crossing():
    rule = _rule(AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 10, "rate_pct": 20})
    now = datetime.now(timezone.utc)
    runs = (
        [_summary(RunStatus.FAILED, now) for _ in range(3)]
        + [_summary(RunStatus.SUCCEEDED, now) for _ in range(7)]
    )
    # 3/10 = 30% >= 20% → fire
    assert eval_error_rate(rule, recent_runs=runs, now=now) is True


def test_sla_duration_fires_when_exceeded():
    rule = _rule(AlertRuleType.SLA_DURATION, {"max_seconds": 120})
    current = _summary(RunStatus.SUCCEEDED, datetime.now(timezone.utc), duration_s=200)
    assert eval_sla_duration(rule, current_run=current) is True


def test_sla_duration_does_not_fire_under_budget():
    rule = _rule(AlertRuleType.SLA_DURATION, {"max_seconds": 120})
    current = _summary(RunStatus.SUCCEEDED, datetime.now(timezone.utc), duration_s=60)
    assert eval_sla_duration(rule, current_run=current) is False


def test_cooldown_gates_all_rule_types():
    now = datetime.now(timezone.utc)
    for rt, cfg, runs, current in [
        (AlertRuleType.CONSECUTIVE_FAILURES, {"n": 1}, [_summary(RunStatus.FAILED, now)], None),
        (AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 1, "rate_pct": 1},
         [_summary(RunStatus.FAILED, now)], None),
        (AlertRuleType.SLA_DURATION, {"max_seconds": 1}, [], _summary(RunStatus.SUCCEEDED, now, duration_s=999)),
    ]:
        rule = _rule(rt, cfg)
        rule.last_fired_at = now - timedelta(seconds=1)
        rule.cooldown_seconds = 600  # 10 min

        if rt is AlertRuleType.CONSECUTIVE_FAILURES:
            fired = eval_consecutive_failures(rule, recent_runs=runs, now=now)
        elif rt is AlertRuleType.ERROR_RATE:
            fired = eval_error_rate(rule, recent_runs=runs, now=now)
        else:
            fired = eval_sla_duration(rule, current_run=current)

        assert fired is False
```

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_rules.py -v`

Expected: FAIL — module not found.

- [ ] **Step 2: Write the evaluators**

`src/backend/base/langflow/services/metering/rules.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import RunStatus


_FAILURE_STATES: frozenset[RunStatus] = frozenset({RunStatus.FAILED, RunStatus.TIMED_OUT})


def is_failure(status: RunStatus) -> bool:
    return status in _FAILURE_STATES


@dataclass(frozen=True)
class RunSummary:
    status: RunStatus
    finished_at: datetime
    duration_seconds: float


def _cooldown_elapsed(rule: AlertRule, now: datetime) -> bool:
    if rule.last_fired_at is None:
        return True
    return (now - rule.last_fired_at) >= timedelta(seconds=rule.cooldown_seconds)


def eval_consecutive_failures(
    rule: AlertRule,
    *,
    recent_runs: Sequence[RunSummary],  # ordered most-recent-first
    now: datetime,
) -> bool:
    if not rule.is_active or not _cooldown_elapsed(rule, now):
        return False
    n = int(rule.config.get("n", 0))
    if n <= 0 or len(recent_runs) < n:
        return False
    return all(is_failure(r.status) for r in recent_runs[:n])


def eval_error_rate(
    rule: AlertRule,
    *,
    recent_runs: Sequence[RunSummary],  # already filtered to window
    now: datetime,
) -> bool:
    if not rule.is_active or not _cooldown_elapsed(rule, now):
        return False
    min_samples = int(rule.config.get("min_samples", 1))
    rate_pct = float(rule.config.get("rate_pct", 100))
    if len(recent_runs) < min_samples:
        return False
    failures = sum(1 for r in recent_runs if is_failure(r.status))
    observed_pct = (failures * 100.0) / len(recent_runs)
    return observed_pct >= rate_pct


def eval_sla_duration(
    rule: AlertRule,
    *,
    current_run: RunSummary,
) -> bool:
    if not rule.is_active:
        return False
    if not _cooldown_elapsed(rule, current_run.finished_at):
        return False
    max_seconds = float(rule.config.get("max_seconds", float("inf")))
    return current_run.duration_seconds > max_seconds
```

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_rules.py -v`

Expected: 8 PASS.

---

### Task D3: `record_run_completion_and_eval` service function

**Files:**
- Modify: `src/backend/base/langflow/services/metering/service.py`
- Modify: `src/backend/tests/unit/services/metering/test_service.py`

- [ ] **Step 1: Write the integration test**

Append to `test_service.py`:

```python
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)


@pytest.mark.asyncio
async def test_record_run_completion_upserts_counters_and_fires_threshold(session_factory, monkeypatch):
    from langflow.services.metering.service import record_run_completion_and_eval
    from langflow.services.notifier.dispatcher import UsageAlertDispatcher
    from langflow.services.notifier.protocol import UsageAlertEvent

    fired: list[UsageAlertEvent] = []

    class Capturing:
        async def notify(self, event):
            fired.append(event)

    dispatcher = UsageAlertDispatcher([Capturing()])

    org_id = uuid4()
    user_id = uuid4()
    flow_id = uuid4()

    started = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)

    async with session_factory() as session:
        # Seed a threshold at runs >= 1, daily — crossing on this single run.
        threshold = OrgUsageThreshold(
            id=uuid4(),
            org_id=org_id,
            metric=UsageMetric.RUNS,
            period=UsagePeriod.DAILY,
            threshold_value=1,
            is_active=True,
            last_fired_at=None,
            cooldown_seconds=0,
            created_by_user_id=user_id,
        )
        session.add(threshold)
        await session.commit()

        run = FlowRun(
            id=uuid4(),
            organization_id=org_id,
            flow_id=flow_id,
            triggered_by=TriggeredBy.API,
            status=RunStatus.SUCCEEDED,
            queued_at=started,
            started_at=started,
            finished_at=finished,
        )
        session.add(run)
        await session.commit()

        await record_run_completion_and_eval(session, run=run, dispatcher=dispatcher)
        await session.commit()

        row = (
            await session.exec(
                select(OrgUsageDaily).where(OrgUsageDaily.org_id == org_id)
            )
        ).one()

    assert row.runs == 1
    assert row.run_seconds == 30
    assert len(fired) == 1
    assert fired[0].category == "usage_threshold"
    assert fired[0].org_id == org_id
```

Run: `cd src/backend && uv run pytest tests/unit/services/metering/test_service.py::test_record_run_completion_upserts_counters_and_fires_threshold -v`

Expected: FAIL — `record_run_completion_and_eval` not defined.

- [ ] **Step 2: Write the function**

Append to `src/backend/base/langflow/services/metering/service.py`:

```python
from datetime import date as date_type
from typing import Iterable

from sqlalchemy import and_
from sqlalchemy.orm import attributes

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)
from langflow.services.metering.rules import (
    RunSummary,
    eval_consecutive_failures,
    eval_error_rate,
    eval_sla_duration,
    is_failure,
)
from langflow.services.metering.thresholds import check_threshold_crossed
from langflow.services.notifier.protocol import UsageAlertEvent


async def record_run_completion_and_eval(
    session: "AsyncSession",
    *,
    run: FlowRun,
    dispatcher,
) -> None:
    """Single entry point called from the worker post-commit hook.

    Upserts org_usage_daily, sums tokens for the run's day, evaluates
    thresholds + alert rules, stamps last_fired_at inside the same
    transaction, and dispatches events.
    """
    if run.organization_id is None or run.finished_at is None:
        return

    day = run.finished_at.astimezone(timezone.utc).date()
    duration_s = 0
    if run.started_at is not None:
        started = run.started_at
        finished = run.finished_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        duration_s = int(max(0, (finished - started).total_seconds()))

    tokens = 0
    if run.flow_id is not None:
        tokens = await sum_tokens_for_flow_day(session, flow_id=run.flow_id, day=day)

    # Re-read the pre-increment counters so threshold eval sees the crossing delta.
    previous = _DailyCounters(runs=0, run_seconds=0, tokens=0)
    existing = (
        await session.exec(
            sm_select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == run.organization_id,
                OrgUsageDaily.date == day,
            )
        )
    ).first()
    if existing is not None:
        previous = _DailyCounters(
            runs=existing.runs, run_seconds=existing.run_seconds, tokens=existing.tokens
        )

    await upsert_org_usage_daily(
        session,
        org_id=run.organization_id,
        day=day,
        runs_delta=1,
        run_seconds_delta=duration_s,
        tokens_delta=tokens,
    )
    current = _DailyCounters(
        runs=previous.runs + 1,
        run_seconds=previous.run_seconds + duration_s,
        tokens=previous.tokens + tokens,
    )

    events: list[UsageAlertEvent] = []
    events.extend(
        await _eval_thresholds(session, run.organization_id, previous, current, day)
    )
    events.extend(await _eval_alert_rules(session, run, duration_s))

    await session.flush()  # stamp last_fired_at updates before dispatch

    for event in events:
        await dispatcher.dispatch(event)


@dataclass(frozen=True)
class _DailyCounters:
    runs: int
    run_seconds: int
    tokens: int

    def value_for(self, metric: UsageMetric) -> int:
        if metric is UsageMetric.RUNS:
            return self.runs
        if metric is UsageMetric.RUN_SECONDS:
            return self.run_seconds
        return self.tokens


async def _eval_thresholds(
    session: "AsyncSession",
    org_id: UUID,
    previous: _DailyCounters,
    current: _DailyCounters,
    day: date_type,
) -> list[UsageAlertEvent]:
    # Row-lock active thresholds for this org to serialize concurrent workers.
    thresholds = (
        await session.exec(
            sm_select(OrgUsageThreshold)
            .where(
                OrgUsageThreshold.org_id == org_id,
                OrgUsageThreshold.is_active.is_(True),
            )
            .with_for_update()
        )
    ).all()

    now = datetime.now(timezone.utc)
    events: list[UsageAlertEvent] = []

    for t in thresholds:
        # v1 supports daily period only; monthly is a P1 extension. Skip non-daily.
        if t.period is not UsagePeriod.DAILY:
            continue
        prev_v = previous.value_for(t.metric)
        cur_v = current.value_for(t.metric)
        if not check_threshold_crossed(t, previous=prev_v, current=cur_v, now=now):
            continue

        t.last_fired_at = now
        session.add(t)
        events.append(
            UsageAlertEvent(
                category="usage_threshold",
                severity="warning",
                org_id=org_id,
                title=f"{t.metric.value} threshold crossed ({t.threshold_value}) for {day.isoformat()}",
                body_md=(
                    f"Org `{org_id}` crossed the {t.period.value} {t.metric.value} "
                    f"threshold of **{t.threshold_value}** (observed: {cur_v})."
                ),
                metadata={
                    "threshold_id": str(t.id),
                    "metric": t.metric.value,
                    "period": t.period.value,
                    "threshold_value": t.threshold_value,
                    "observed_value": cur_v,
                    "day": day.isoformat(),
                },
            )
        )
    return events


async def _eval_alert_rules(
    session: "AsyncSession",
    run: FlowRun,
    duration_s: int,
) -> list[UsageAlertEvent]:
    from sqlalchemy import or_

    rules = (
        await session.exec(
            sm_select(AlertRule)
            .where(
                AlertRule.org_id == run.organization_id,
                AlertRule.is_active.is_(True),
                or_(AlertRule.flow_id.is_(None), AlertRule.flow_id == run.flow_id),
            )
            .with_for_update()
        )
    ).all()

    if not rules:
        return []

    now = datetime.now(timezone.utc)
    # Pull recent runs once per (flow, largest_window) to avoid N queries.
    largest_window = max(
        int(r.config.get("window_minutes", 60)) for r in rules if r.rule_type is AlertRuleType.ERROR_RATE
    ) if any(r.rule_type is AlertRuleType.ERROR_RATE for r in rules) else 0
    max_n = max(
        int(r.config.get("n", 1)) for r in rules if r.rule_type is AlertRuleType.CONSECUTIVE_FAILURES
    ) if any(r.rule_type is AlertRuleType.CONSECUTIVE_FAILURES for r in rules) else 0

    recent_runs: list[RunSummary] = []
    if max_n > 0 or largest_window > 0:
        window_start = now - timedelta(minutes=max(largest_window, 60))
        records = (
            await session.exec(
                sm_select(FlowRun.status, FlowRun.finished_at, FlowRun.started_at)
                .where(
                    FlowRun.flow_id == run.flow_id,
                    FlowRun.finished_at.is_not(None),
                    FlowRun.finished_at >= window_start,
                )
                .order_by(FlowRun.finished_at.desc())
                .limit(max(max_n, 500))
            )
        ).all()
        for status, finished_at, started_at in records:
            dur = 0.0
            if started_at and finished_at:
                s = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
                f = finished_at if finished_at.tzinfo else finished_at.replace(tzinfo=timezone.utc)
                dur = max(0.0, (f - s).total_seconds())
            recent_runs.append(RunSummary(status=status, finished_at=finished_at, duration_seconds=dur))

    current_summary = RunSummary(
        status=run.status, finished_at=run.finished_at, duration_seconds=float(duration_s)
    )

    events: list[UsageAlertEvent] = []
    for rule in rules:
        fired = False
        if rule.rule_type is AlertRuleType.CONSECUTIVE_FAILURES:
            fired = eval_consecutive_failures(rule, recent_runs=recent_runs, now=now)
        elif rule.rule_type is AlertRuleType.ERROR_RATE:
            window = int(rule.config.get("window_minutes", 60))
            windowed = [r for r in recent_runs if r.finished_at >= now - timedelta(minutes=window)]
            fired = eval_error_rate(rule, recent_runs=windowed, now=now)
        elif rule.rule_type is AlertRuleType.SLA_DURATION:
            fired = eval_sla_duration(rule, current_run=current_summary)

        if not fired:
            continue

        rule.last_fired_at = now
        session.add(rule)
        events.append(
            UsageAlertEvent(
                category="alert_rule",
                severity="warning",
                org_id=run.organization_id,
                title=f"Alert rule fired: {rule.rule_type.value}",
                body_md=(
                    f"Rule `{rule.id}` ({rule.rule_type.value}) fired on flow "
                    f"`{run.flow_id}` after run `{run.id}`."
                ),
                metadata={
                    "rule_id": str(rule.id),
                    "rule_type": rule.rule_type.value,
                    "flow_id": str(run.flow_id) if run.flow_id else None,
                    "run_id": str(run.id),
                    "config": dict(rule.config),
                },
            )
        )
    return events
```

Update the package re-export:

`src/backend/base/langflow/services/metering/__init__.py`:

```python
from langflow.services.metering.service import (
    record_run_completion_and_eval,
    sum_tokens_for_flow_day,
    upsert_org_usage_daily,
)

__all__ = [
    "record_run_completion_and_eval",
    "sum_tokens_for_flow_day",
    "upsert_org_usage_daily",
]
```

- [ ] **Step 2: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/ -v`

Expected: all PASS.

---

### Task D4: Hook into `worker_app/execute.py`

**Files:**
- Modify: `src/backend/base/langflow/worker_app/execute.py:171-190`

- [ ] **Step 1: Add a kill-switch setting**

Edit `src/backend/base/langflow/services/settings/base.py` and add (near existing toggles):

```python
    metering_enabled: bool = True
```

If the file uses pydantic-settings, this reads from `LANGFLOW_METERING_ENABLED`.

- [ ] **Step 2: Insert the hook call**

Open `src/backend/base/langflow/worker_app/execute.py`. Find the post-commit block (line ~171). After the Prometheus metrics block (ending at line ~189), and before `await concurrency.release(org_id_captured)` (line ~190), insert:

```python
        # Metering + threshold/alert eval (kill-switch: settings.metering_enabled).
        try:
            from langflow.services.deps import get_settings_service, get_usage_alert_dispatcher
            if get_settings_service().settings.metering_enabled:
                from langflow.services.metering import record_run_completion_and_eval
                dispatcher = get_usage_alert_dispatcher()
                await record_run_completion_and_eval(session, run=run, dispatcher=dispatcher)
                await session.commit()
        except Exception:  # noqa: BLE001
            # Never let metering break run completion. Log and move on.
            logger.exception(f"[run={run_id}] metering post-commit failed")
```

(Place inside the `async with session_factory() as session:` block so `session` is still in scope. If the session has already exited that block, move the code to its own `async with session_factory() as session:` block.)

- [ ] **Step 3: Sanity run the test module + the existing execute tests**

Run: `cd src/backend && uv run pytest tests/unit/services/metering/ tests/unit/workers/ -v` (if `tests/unit/workers/` exists — use `grep -rln "worker_app/execute" src/backend/tests` to find the actual test file).

Expected: all PASS. If no `workers` test exists, that's acceptable — proceed.

---

### Task D5: Commit Phase D

- [ ] **Step 1: Commit**

```bash
git add src/backend/base/langflow/services/metering/ \
        src/backend/base/langflow/worker_app/execute.py \
        src/backend/base/langflow/services/settings/base.py \
        src/backend/tests/unit/services/metering/

git commit -m "feat(metering): run-completion hook + threshold/alert evaluators

Add record_run_completion_and_eval which upserts org_usage_daily,
attributes tokens via TraceTable join, evaluates thresholds (row-level
FOR UPDATE + cooldown) and the three v1 alert rule types
(consecutive_failures, error_rate, sla_duration), then dispatches
events through UsageAlertDispatcher. Hook the call in to execute.py
post-commit. Wrap with settings.metering_enabled kill switch; metering
failures never break run completion.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase E — Admin API endpoints

### Task E1: Notifications API (list, unread count, mark read, mark all)

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/notifications.py`
- Create: `src/backend/tests/unit/api/v1/admin/test_notifications.py`

- [ ] **Step 1: Write the failing test**

`src/backend/tests/unit/api/v1/admin/test_notifications.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationCategory,
    NotificationSeverity,
)


async def _seed_notification(session_factory, **over) -> AdminNotification:
    async with session_factory() as session:
        row = AdminNotification(
            org_id=over.get("org_id", uuid4()),
            category=over.get("category", NotificationCategory.USAGE_THRESHOLD),
            severity=over.get("severity", NotificationSeverity.WARNING),
            title=over.get("title", "Test"),
            body_md=over.get("body_md", "body"),
            metadata_json=over.get("metadata_json", {}),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def test_list_notifications_requires_platform_admin(
    client: AsyncClient, logged_in_headers: dict
):
    resp = await client.get("api/v1/admin/notifications", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_list_notifications_returns_unread_by_default(
    client: AsyncClient, logged_in_headers_platform_admin: dict, session_factory
):
    await _seed_notification(session_factory, title="A")
    await _seed_notification(session_factory, title="B")

    resp = await client.get(
        "api/v1/admin/notifications", headers=logged_in_headers_platform_admin
    )
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()["items"]
    assert len(items) == 2
    assert {i["title"] for i in items} == {"A", "B"}


async def test_unread_count_endpoint(
    client: AsyncClient, logged_in_headers_platform_admin: dict, session_factory
):
    await _seed_notification(session_factory)
    await _seed_notification(session_factory)

    resp = await client.get(
        "api/v1/admin/notifications/unread-count",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"unread": 2}


async def test_mark_read(
    client: AsyncClient, logged_in_headers_platform_admin: dict, session_factory
):
    row = await _seed_notification(session_factory)

    resp = await client.post(
        f"api/v1/admin/notifications/{row.id}/read",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    unread = await client.get(
        "api/v1/admin/notifications/unread-count",
        headers=logged_in_headers_platform_admin,
    )
    assert unread.json() == {"unread": 0}
```

This test uses a new `logged_in_headers_platform_admin` fixture. Add it to `src/backend/tests/conftest.py` near the existing `logged_in_headers_super_user` (around line 518):

```python
@pytest.fixture
async def active_platform_admin(client):  # noqa: ARG001
    async with session_scope() as session:
        user = User(
            username="platformadmin",
            password=get_auth_service().get_password_hash("testpassword"),
            is_active=True,
            is_superuser=True,
            is_platform_admin=True,
        )
        stmt = select(User).where(User.username == user.username)
        if existing := (await session.exec(stmt)).first():
            user = existing
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
    yield user


@pytest.fixture
async def logged_in_headers_platform_admin(client, active_platform_admin):
    login_data = {"username": active_platform_admin.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
```

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_notifications.py -v`

Expected: FAIL (all four tests; router not wired yet).

- [ ] **Step 2: Write the router**

`src/backend/base/langflow/api/v1/admin/notifications.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationCategory,
    NotificationSeverity,
)

router = APIRouter(tags=["Admin · Notifications"])


class NotificationRead(BaseModel):
    id: UUID
    org_id: UUID | None
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    body_md: str
    metadata: dict
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    admin: PlatformAdmin,
    session: DbSession,
    unread: Annotated[bool | None, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    stmt = select(AdminNotification).order_by(AdminNotification.created_at.desc())
    if unread:
        stmt = stmt.where(AdminNotification.read_at.is_(None))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.exec(stmt)).all()
    items = [
        NotificationRead(
            id=r.id,
            org_id=r.org_id,
            category=r.category,
            severity=r.severity,
            title=r.title,
            body_md=r.body_md,
            metadata=r.metadata_json,
            created_at=r.created_at,
            read_at=r.read_at,
        )
        for r in rows
    ]
    total_stmt = select(AdminNotification)
    if unread:
        total_stmt = total_stmt.where(AdminNotification.read_at.is_(None))
    total = len((await session.exec(total_stmt)).all())
    return NotificationListResponse(items=items, total=total)


@router.get("/notifications/unread-count")
async def unread_count(
    admin: PlatformAdmin,
    session: DbSession,
) -> dict[str, int]:
    rows = (
        await session.exec(
            select(AdminNotification).where(AdminNotification.read_at.is_(None))
        )
    ).all()
    return {"unread": len(rows)}


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    row = await session.get(AdminNotification, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        row.read_by_user_id = admin.id
        session.add(row)
        await session.commit()


@router.post("/notifications/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    rows = (
        await session.exec(
            select(AdminNotification).where(AdminNotification.read_at.is_(None))
        )
    ).all()
    for r in rows:
        r.read_at = now
        r.read_by_user_id = admin.id
        session.add(r)
    await session.commit()
```

- [ ] **Step 3: Register the router**

Edit `src/backend/base/langflow/api/v1/admin/__init__.py`:

```python
"""Admin-gated API endpoints."""

from fastapi import APIRouter

from .metadata import router as _metadata_router
from .notifications import router as _notifications_router
from .orgs import router as _orgs_router
from .users import router as _users_router

router = APIRouter(prefix="/admin", tags=["Admin"])
router.include_router(_orgs_router)
router.include_router(_metadata_router)
router.include_router(_users_router)
router.include_router(_notifications_router)

__all__ = ["router"]
```

- [ ] **Step 4: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_notifications.py -v`

Expected: 4 PASS.

---

### Task E2: Usage thresholds CRUD

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/usage_thresholds.py`
- Create: `src/backend/tests/unit/api/v1/admin/test_usage_thresholds.py`
- Modify: `src/backend/base/langflow/api/v1/admin/__init__.py`

- [ ] **Step 1: Write the failing test**

`src/backend/tests/unit/api/v1/admin/test_usage_thresholds.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


async def test_usage_thresholds_crud_happy_path(
    client: AsyncClient, logged_in_headers_platform_admin: dict, seeded_org
):
    # Create
    create_resp = await client.post(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds",
        json={"metric": "runs", "period": "daily", "threshold_value": 100},
        headers=logged_in_headers_platform_admin,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["metric"] == "runs"
    threshold_id = created["id"]

    # List
    list_resp = await client.get(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds",
        headers=logged_in_headers_platform_admin,
    )
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(t["id"] == threshold_id for t in list_resp.json()["items"])

    # Patch
    patch_resp = await client.patch(
        f"api/v1/admin/usage/thresholds/{threshold_id}",
        json={"threshold_value": 200, "is_active": False},
        headers=logged_in_headers_platform_admin,
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["threshold_value"] == 200
    assert patch_resp.json()["is_active"] is False

    # Delete
    del_resp = await client.delete(
        f"api/v1/admin/usage/thresholds/{threshold_id}",
        headers=logged_in_headers_platform_admin,
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


async def test_usage_thresholds_reject_non_admin(
    client: AsyncClient, logged_in_headers: dict, seeded_org
):
    resp = await client.get(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds", headers=logged_in_headers
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
```

This relies on a `seeded_org` fixture (Organization row with a known id). If not already present, add to `conftest.py`:

```python
@pytest.fixture
async def seeded_org(client):  # noqa: ARG001
    from langflow.services.database.models.organization.model import Organization

    async with session_scope() as session:
        org = Organization(id=uuid4(), name="test-org", slug="test-org")
        session.add(org)
        await session.commit()
        await session.refresh(org)
    yield org
```

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_usage_thresholds.py -v`

Expected: FAIL — endpoint not wired.

- [ ] **Step 2: Write the router**

`src/backend/base/langflow/api/v1/admin/usage_thresholds.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)

router = APIRouter(tags=["Admin · Usage Thresholds"])


class ThresholdCreate(BaseModel):
    metric: UsageMetric
    period: UsagePeriod
    threshold_value: int
    cooldown_seconds: int = 3600


class ThresholdPatch(BaseModel):
    threshold_value: int | None = None
    is_active: bool | None = None
    cooldown_seconds: int | None = None


class ThresholdRead(BaseModel):
    id: UUID
    org_id: UUID
    metric: UsageMetric
    period: UsagePeriod
    threshold_value: int
    is_active: bool
    last_fired_at: datetime | None
    cooldown_seconds: int


class ThresholdListResponse(BaseModel):
    items: list[ThresholdRead]


@router.get("/orgs/{org_id}/usage/thresholds", response_model=ThresholdListResponse)
async def list_thresholds(
    org_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdListResponse:
    rows = (
        await session.exec(
            select(OrgUsageThreshold).where(OrgUsageThreshold.org_id == org_id)
        )
    ).all()
    return ThresholdListResponse(items=[ThresholdRead.model_validate(r, from_attributes=True) for r in rows])


@router.post(
    "/orgs/{org_id}/usage/thresholds",
    response_model=ThresholdRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_threshold(
    org_id: UUID,
    payload: ThresholdCreate,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdRead:
    row = OrgUsageThreshold(
        org_id=org_id,
        metric=payload.metric,
        period=payload.period,
        threshold_value=payload.threshold_value,
        cooldown_seconds=payload.cooldown_seconds,
        created_by_user_id=admin.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ThresholdRead.model_validate(row, from_attributes=True)


@router.patch("/usage/thresholds/{threshold_id}", response_model=ThresholdRead)
async def patch_threshold(
    threshold_id: UUID,
    payload: ThresholdPatch,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdRead:
    row = await session.get(OrgUsageThreshold, threshold_id)
    if row is None:
        raise HTTPException(status_code=404, detail="threshold not found")
    if payload.threshold_value is not None:
        row.threshold_value = payload.threshold_value
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.cooldown_seconds is not None:
        row.cooldown_seconds = payload.cooldown_seconds
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ThresholdRead.model_validate(row, from_attributes=True)


@router.delete("/usage/thresholds/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    threshold_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    row = await session.get(OrgUsageThreshold, threshold_id)
    if row is None:
        raise HTTPException(status_code=404, detail="threshold not found")
    await session.delete(row)
    await session.commit()
```

- [ ] **Step 3: Register the router**

Edit `src/backend/base/langflow/api/v1/admin/__init__.py` to include `_usage_thresholds_router` the same way as `_notifications_router` was wired.

- [ ] **Step 4: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_usage_thresholds.py -v`

Expected: PASS.

---

### Task E3: Alert rules CRUD (mirrors Task E2)

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/alert_rules.py`
- Create: `src/backend/tests/unit/api/v1/admin/test_alert_rules.py`
- Modify: `src/backend/base/langflow/api/v1/admin/__init__.py`

Follow the exact same pattern as Task E2, substituting `AlertRule` / `AlertRuleType` for `OrgUsageThreshold` / `UsageMetric`, and these route paths:
- `GET    /admin/orgs/{org_id}/alert-rules`
- `POST   /admin/orgs/{org_id}/alert-rules`
- `PATCH  /admin/alert-rules/{rule_id}`
- `DELETE /admin/alert-rules/{rule_id}`

Request body shapes:
- `RuleCreate`: `rule_type` (enum), `flow_id` (UUID, optional), `config` (dict), `cooldown_seconds` (int, default 900).
- `RulePatch`: `config` (dict, optional), `is_active` (bool, optional), `cooldown_seconds` (int, optional).

Config validation: for `consecutive_failures`, require `n: int > 0`. For `error_rate`, require `window_minutes: int > 0, min_samples: int > 0, rate_pct: float 0-100`. For `sla_duration`, require `max_seconds: number > 0`. Validate in the `create` / `patch` endpoints; reject with 422 on violations.

- [ ] **Step 1: Write the mirror test + rule-config validation tests**

Mirror `test_usage_thresholds.py` and add:

```python
async def test_alert_rule_rejects_invalid_consecutive_failures_config(
    client, logged_in_headers_platform_admin, seeded_org
):
    resp = await client.post(
        f"api/v1/admin/orgs/{seeded_org.id}/alert-rules",
        json={"rule_type": "consecutive_failures", "config": {"n": 0}},
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

- [ ] **Step 2: Write the router and validation**

Mirror `usage_thresholds.py`. In create/patch, call a helper `_validate_rule_config(rule_type, config)` that raises `HTTPException(422)` on violations per the rules above.

- [ ] **Step 3: Run tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_alert_rules.py -v`

Expected: PASS.

---

### Task E4: Commit Phase E

- [ ] **Step 1: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin/notifications.py \
        src/backend/base/langflow/api/v1/admin/usage_thresholds.py \
        src/backend/base/langflow/api/v1/admin/alert_rules.py \
        src/backend/base/langflow/api/v1/admin/__init__.py \
        src/backend/tests/conftest.py \
        src/backend/tests/unit/api/v1/admin/

git commit -m "feat(api): admin endpoints for metering + alerting

Wire three admin routers (PlatformAdmin-gated):
- /admin/notifications (list / unread-count / mark-read / mark-all-read)
- /admin/orgs/:id/usage/thresholds + /admin/usage/thresholds/:id (CRUD)
- /admin/orgs/:id/alert-rules + /admin/alert-rules/:id (CRUD, with
  per-rule-type config validation)

Add logged_in_headers_platform_admin + seeded_org test fixtures.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase F — Front-end

### Task F1: React-query hooks for notifications

**Files:**
- Create: the 4 notification hook files listed under "Frontend — create" above.
- Modify: `src/frontend/src/controllers/API/helpers/constants.ts` (add `ADMIN_NOTIFICATIONS`).

- [ ] **Step 1: Register the URL constant**

Find the existing URL map (grep for `ADMIN_ORGS`). Add:

```typescript
ADMIN_NOTIFICATIONS: `${BASE_URL_API}v1/admin/notifications`,
ADMIN_USAGE_THRESHOLDS: `${BASE_URL_API}v1/admin/orgs/`,     // per-org list/create; full path built at call site
ADMIN_USAGE_THRESHOLD: `${BASE_URL_API}v1/admin/usage/thresholds/`,  // PATCH / DELETE by id
ADMIN_ALERT_RULES: `${BASE_URL_API}v1/admin/orgs/`,  // per-org list/create; full path at call site
ADMIN_ALERT_RULE: `${BASE_URL_API}v1/admin/alert-rules/`,  // PATCH / DELETE by id
```

- [ ] **Step 2: Write `useGetAdminNotifications`**

`src/frontend/src/controllers/API/queries/admin/use-get-admin-notifications.ts`:

```typescript
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type Params = { unread?: boolean; limit?: number; offset?: number };
type NotificationRead = {
  id: string;
  org_id: string | null;
  category: "usage_threshold" | "alert_rule" | "system";
  severity: "info" | "warning" | "critical";
  title: string;
  body_md: string;
  metadata: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
};
type Response = { items: NotificationRead[]; total: number };

export const useGetAdminNotifications: useQueryFunctionType<Params, Response> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<Response> => {
    const { data } = await api.get<Response>(getURL("ADMIN_NOTIFICATIONS"), {
      params,
    });
    return data;
  };
  return query(["admin", "notifications", params], fn, { ...options });
};
```

- [ ] **Step 3: Write the other 3 notification hooks**

Copy the shape of `use-get-admin-notifications` for:
- `use-get-unread-notifications-count.ts` — GET `/admin/notifications/unread-count`, query key `["admin", "notifications", "unread-count"]`, returns `{ unread: number }`.
- `use-mark-notification-read.ts` — POST `/admin/notifications/:id/read`, mutation that invalidates `["admin", "notifications"]`.
- `use-mark-all-notifications-read.ts` — POST `/admin/notifications/mark-all-read`, same invalidation.

Use the existing `use-create-organization.ts` as the mutation pattern reference.

---

### Task F2: React-query hooks for thresholds + alert rules

Mirror the notification hooks for the 4 threshold hooks (`useGetUsageThresholds`, `useCreateUsageThreshold`, `usePatchUsageThreshold`, `useDeleteUsageThreshold`) and the 4 alert-rule hooks.

Query keys:
- Thresholds: `["admin", "usage-thresholds", orgId]` for the list; invalidate on all mutations.
- Alert rules: `["admin", "alert-rules", orgId]`.

---

### Task F3: Admin notification bell

**Files:**
- Create: `src/frontend/src/components/core/adminNotificationBell/index.tsx`
- Create: `src/frontend/src/components/core/adminNotificationBell/__tests__/index.test.tsx`

- [ ] **Step 1: Write the failing render test**

`__tests__/index.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AdminNotificationBell from "..";

jest.mock("@/controllers/API/queries/admin/use-get-unread-notifications-count", () => ({
  useGetUnreadNotificationsCount: () => ({ data: { unread: 3 }, isPending: false }),
}));

function renderBell() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <AdminNotificationBell />
    </QueryClientProvider>,
  );
}

describe("AdminNotificationBell", () => {
  it("renders the unread badge count", () => {
    renderBell();
    expect(screen.getByTestId("admin-bell")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the bell component**

`index.tsx`:

```typescript
import { useNavigate } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetUnreadNotificationsCount } from "@/controllers/API/queries/admin/use-get-unread-notifications-count";

export default function AdminNotificationBell() {
  const navigate = useNavigate();
  const { data } = useGetUnreadNotificationsCount({}, {
    refetchInterval: 30000,  // 30s poll
  });
  const unread = data?.unread ?? 0;

  return (
    <div className="relative" data-testid="admin-bell">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate("/admin/notifications")}
        aria-label="Notifications"
      >
        <IconComponent name="Bell" className="h-5 w-5" />
      </Button>
      {unread > 0 && (
        <span
          className="absolute -top-1 -right-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white"
          data-testid="admin-bell-badge"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run the test — expect pass**

Run: `cd src/frontend && npx jest src/components/core/adminNotificationBell/__tests__/index.test.tsx`

Expected: PASS.

- [ ] **Step 4: Mount in the main header**

Find the main header that renders the user avatar / settings gear (grep for `userData` in `src/frontend/src/pages/MainPage/`). Add a conditional render:

```typescript
{userData?.is_platform_admin && <AdminNotificationBell />}
```

Place it next to the existing header-right actions.

---

### Task F4: Notification center page + route

**Files:**
- Create: `src/frontend/src/pages/AdminPage/AdminNotificationsPage/index.tsx`
- Modify: `src/frontend/src/routes.tsx`

- [ ] **Step 1: Write the page**

```typescript
import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetAdminNotifications } from "@/controllers/API/queries/admin/use-get-admin-notifications";
import { useMarkAllNotificationsRead } from "@/controllers/API/queries/admin/use-mark-all-notifications-read";
import { useMarkNotificationRead } from "@/controllers/API/queries/admin/use-mark-notification-read";

export default function AdminNotificationsPage() {
  const [unread, setUnread] = useState(true);
  const { data, isPending } = useGetAdminNotifications({ unread, limit: 100 });
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin Notifications</h1>
        <div className="flex gap-2">
          <Button
            variant={unread ? "default" : "outline"}
            onClick={() => setUnread(true)}
          >
            Unread
          </Button>
          <Button
            variant={!unread ? "default" : "outline"}
            onClick={() => setUnread(false)}
          >
            All
          </Button>
          <Button onClick={() => markAll.mutate(undefined)} variant="outline">
            Mark all read
          </Button>
        </div>
      </div>

      {isPending && <div>Loading…</div>}
      {!isPending && (data?.items.length ?? 0) === 0 && (
        <div className="text-muted-foreground">No notifications.</div>
      )}

      <ul className="flex flex-col gap-2">
        {data?.items.map((n) => (
          <li
            key={n.id}
            className="flex items-start gap-3 rounded border p-3"
            data-testid={`notification-${n.id}`}
          >
            <IconComponent
              name={n.severity === "critical" ? "AlertOctagon" : "AlertTriangle"}
              className="h-5 w-5 text-muted-foreground"
            />
            <div className="flex-1">
              <div className="font-medium">{n.title}</div>
              <div className="text-sm text-muted-foreground">{n.body_md}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {new Date(n.created_at).toLocaleString()} · {n.category}
              </div>
            </div>
            {n.read_at === null && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => markRead.mutate(n.id)}
              >
                Mark read
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `src/frontend/src/routes.tsx`, next to other admin routes (around line 46-243), add:

```typescript
const AdminNotificationsPage = lazy(
  () => import("@/pages/AdminPage/AdminNotificationsPage"),
);
```

And in the admin route group:

```typescript
<Route path="notifications" element={<AdminNotificationsPage />} />
```

- [ ] **Step 3: Type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

---

### Task F5: Thresholds + Alert Rules tabs on org detail

**Files:**
- Create: `src/frontend/src/pages/AdminPage/OrgDetailPage/UsageTab.tsx`
- Modify: `src/frontend/src/pages/AdminPage/OrgDetailPage/index.tsx` — mount `<UsageTab />` inside the existing tab layout.

- [ ] **Step 1: Write `UsageTab`**

The component has two sub-sections:

1. **Thresholds**: list with `metric / period / value / active` columns, inline create form (metric dropdown × period dropdown × value input × Save), per-row toggle + delete.
2. **Alert rules**: same UX, with rule-type-dependent config inputs:
   - `consecutive_failures` → `n: number`
   - `error_rate` → `window_minutes: number, min_samples: number, rate_pct: number`
   - `sla_duration` → `max_seconds: number`

Skeleton:

```typescript
import { useParams } from "react-router-dom";
import { useGetAlertRules } from "@/controllers/API/queries/admin/use-get-alert-rules";
import { useGetUsageThresholds } from "@/controllers/API/queries/admin/use-get-usage-thresholds";
// ...

export default function UsageTab() {
  const { orgId } = useParams();
  const { data: thresholds } = useGetUsageThresholds({ orgId: orgId! });
  const { data: rules } = useGetAlertRules({ orgId: orgId! });

  return (
    <div className="flex flex-col gap-8">
      <ThresholdsSection orgId={orgId!} items={thresholds?.items ?? []} />
      <AlertRulesSection orgId={orgId!} items={rules?.items ?? []} />
    </div>
  );
}
```

Each section uses the matching create/patch/delete hooks + the existing `Button`, `Input`, and `Select` primitives from `components/ui/`. Follow the form patterns in existing admin pages (e.g., `OrganizationDetailPage/index.tsx`).

- [ ] **Step 2: Wire the tab in the existing org detail page**

Add a `<Tabs>` section (or extend the existing tab set) to surface `<UsageTab />` under a label like "Usage & Alerts".

- [ ] **Step 3: Type-check + manual smoke**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

Start the dev server (`npm start`) and verify: as platform admin, `/admin/organizations/:id` shows the Usage & Alerts tab; create → list → patch → delete all work.

---

### Task F6: Commit Phase F

- [ ] **Step 1: Commit**

```bash
git add src/frontend/src/controllers/API/queries/admin/ \
        src/frontend/src/controllers/API/helpers/constants.ts \
        src/frontend/src/components/core/adminNotificationBell/ \
        src/frontend/src/pages/AdminPage/AdminNotificationsPage/ \
        src/frontend/src/pages/AdminPage/OrgDetailPage/ \
        src/frontend/src/routes.tsx \
        src/frontend/src/pages/MainPage

git commit -m "feat(ui): admin notifications bell + thresholds + alert rules

Wire the frontend surfaces for the metering feature:
- 12 react-query hooks for notifications / thresholds / alert rules
- AdminNotificationBell component (30s poll of unread-count) mounted
  in the main header when is_platform_admin
- AdminNotificationsPage at /admin/notifications
- Usage & Alerts tab on the org detail page with CRUD for thresholds
  and alert rules (per-rule-type config form)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause for user approval.**

---

## Phase G — Integration smoke test + verification

### Task G1: End-to-end smoke test

- [ ] **Step 1: Start the full stack**

Run: `cd src/backend/base && uv run langflow run` (or the project's make target). Separately `cd src/frontend && npm start`.

- [ ] **Step 2: Walk through the super-admin experience**

| Step | Expected |
|---|---|
| Sign in as super admin | Bell appears in top header |
| Navigate to `/admin/organizations/:some-org` | "Usage & Alerts" tab renders |
| Create threshold: metric=runs, period=daily, value=1 | Row appears in the table |
| Execute one flow in that org (via any trigger) | Run completes normally. Bell badge shows `1`. |
| Click the bell | Navigates to `/admin/notifications` with the new notification visible |
| Click "Mark read" | Badge → 0 |
| Create alert rule: sla_duration, max_seconds=1 | Row appears |
| Execute a run that takes > 1s | Second notification lands |

- [ ] **Step 3: Walk through the non-admin experience**

As a regular member:
- `/admin/notifications` should redirect or show a 403 page.
- The bell is not rendered in the header.
- Direct API call to `/api/v1/admin/notifications` returns 403.

- [ ] **Step 4: Run full test suites**

Run: `cd src/backend && uv run pytest tests/unit/services/metering tests/unit/services/notifier tests/unit/api/v1/admin -v`

Expected: all PASS.

Run: `cd src/frontend && npm test -- --passWithNoTests`

Expected: all PASS.

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

- [ ] **Step 5: Final housekeeping commit (if needed)**

If any incidental fixes landed during smoke, stage and commit with a descriptive message. Otherwise skip.

---

## Self-review notes

1. **Spec coverage:**
   - OrgUsageDaily + threshold eval + pluggable notifier (P0-4) → Phases A, B, C, D, E, F.
   - AlertRule types + cooldown + eval → Phase D Tasks D2, D3.
   - Run-completion hook placement → Task D4.
   - Row-level `FOR UPDATE` for race safety → Task D3 (`with_for_update()` in `_eval_thresholds` and `_eval_alert_rules`).
   - Super-admin bell + notification center + thresholds/alert-rule UI → Phase F.
   - Kill switch `ENABLE_METERING` → Task D4 Step 1 + Step 2 (`settings.metering_enabled`).
   - Unknown/monthly-period thresholds intentionally skipped in v1 → `_eval_thresholds` skips non-daily with a TODO line of code.
   - Latency budgets (from spec: ~20–40ms p95 typical) → achieved through single-query recent-runs batch in `_eval_alert_rules`, row locks narrow per-threshold, single `upsert_org_usage_daily`.

2. **Placeholder scan:** no TBDs. The mirror task (E3) and the FE hook mirror (F2) describe the pattern explicitly with references to existing code (Task E2 / F1).

3. **Type consistency:** `UsageAlertEvent` signature used in `protocol.py`, `dispatcher.py`, `in_app.py`, `service.py`, and tests — all keyword-constructed with the same field names (`category`, `severity`, `org_id`, `title`, `body_md`, `metadata`). `record_run_completion_and_eval` takes `session, *, run, dispatcher` across the service file, the test, and the worker hook call.

4. **Risks addressed:**
   - Race on threshold crossing → `FOR UPDATE`.
   - Dispatcher failure blast radius → `_safe_notify` log-and-continue.
   - Metering breaking run completion → outer `try/except` around the hook call.
   - Token attribution hole when tracing is off → `sum_tokens_for_flow_day` returns 0 via `coalesce`.

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-04-22-metering-notifier-alerting.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using the executing-plans skill, batch execution with checkpoints.

**Which approach?**
