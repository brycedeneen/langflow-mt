# Pro-Service Quotes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a v1 Pro-Service Quotes feature that lets a user request a Professional Services engagement from the flow builder, generates an AI ballpark estimate (hours range × hourly rate band → dollar range) plus an LLM-written headline/narrative/summary, persists the quote as a first-class entity, broadcasts it to admin bells, and optionally mirrors it to an HMAC-signed webhook.

**Architecture:** Internal queue is the source of truth (admins triage in-app via a new "Pro-Service Quotes" sidebar nav above "Knowledge"). Optional HMAC-signed webhook fires on submit as a notification mirror, reusing `worker_app/webhook.py`. ADP Assist gets a new `suggest_professional_services` tool that emits a `ps_suggestion` SSE event, which the frontend renders as an inline card. Lifecycle is `open → in_progress → closed` with a `flow.ps_request_active` dedup flag cleared on terminal transitions. Two notes fields (`org_notes`, `admin_notes`) let each side leave context. Notification routing is extended with a nullable `audience_user_id` for targeted bell rows and a new `PLATFORM_ADMIN` audience.

**Tech Stack:** FastAPI + SQLModel + alembic (backend), React + TanStack Query v5 + Jest + Tailwind v4 (frontend), Anthropic + OpenAI providers via existing assistant adapters, existing `worker_app/webhook.py` for HMAC delivery.

**Spec:** [`docs/superpowers/specs/2026-04-25-pro-service-quotes-design.md`](../specs/2026-04-25-pro-service-quotes-design.md)

---

## Phase A: Database Schema

### Task 1: Define SQLModel for `pro_service_quote`

**Files:**
- Create: `src/backend/base/langflow/services/database/models/pro_service_quote/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/pro_service_quote/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_pro_service_quote_model.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/database/models/test_pro_service_quote_model.py
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


def test_pro_service_quote_default_status():
    quote = ProServiceQuote(
        org_id=uuid4(),
        flow_id=uuid4(),
        requester_user_id=uuid4(),
        estimated_minutes_low=15,
        estimated_minutes_high=60,
        rate_low_per_hour=Decimal("200.00"),
        rate_high_per_hour=Decimal("200.00"),
        headline_summary="Wire up Slack notifications.",
        narrative="The user wants to push build events to Slack.",
        submitted_at=datetime.now(timezone.utc),
    )
    assert quote.status == ProServiceQuoteStatus.OPEN
    assert quote.id is not None
    assert quote.created_at is not None


def test_pro_service_quote_status_enum_values():
    assert ProServiceQuoteStatus.OPEN.value == "open"
    assert ProServiceQuoteStatus.IN_PROGRESS.value == "in_progress"
    assert ProServiceQuoteStatus.CLOSED.value == "closed"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_pro_service_quote_model.py -v`
Expected: ImportError for `ProServiceQuote`.

- [ ] **Step 3: Implement the model**

```python
# src/backend/base/langflow/services/database/models/pro_service_quote/__init__.py
from .model import ProServiceQuote, ProServiceQuoteStatus

__all__ = ["ProServiceQuote", "ProServiceQuoteStatus"]
```

```python
# src/backend/base/langflow/services/database/models/pro_service_quote/model.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlmodel import Column, Field, SQLModel


class ProServiceQuoteStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProServiceQuote(SQLModel, table=True):
    __tablename__ = "pro_service_quote"
    __table_args__ = (
        Index("ix_pro_service_quote_org_status_created", "org_id", "status", "created_at"),
        Index("ix_pro_service_quote_status_created", "status", "created_at"),
        Index("ix_pro_service_quote_flow_id", "flow_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("flow.id", ondelete="SET NULL"), nullable=True),
    )
    requester_user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
    )
    status: ProServiceQuoteStatus = Field(
        default=ProServiceQuoteStatus.OPEN,
        sa_column=Column(String(length=24), nullable=False),
    )
    assigned_admin_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )

    estimated_minutes_low: int = Field(nullable=False)
    estimated_minutes_high: int = Field(nullable=False)
    rate_low_per_hour: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )
    rate_high_per_hour: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )

    headline_summary: str = Field(sa_column=Column(Text, nullable=False))
    narrative: str = Field(sa_column=Column(Text, nullable=False))
    conversation_summary: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True),
    )
    org_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    admin_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_utcnow),
    )
    submitted_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    in_progress_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    closed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    closed_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_pro_service_quote_model.py -v`
Expected: 2 passed.

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/database/models/pro_service_quote/ \
        src/backend/tests/unit/services/database/models/test_pro_service_quote_model.py
git commit -m "feat(pro-services): add ProServiceQuote SQLModel"
```

---

### Task 2: Define SQLModel for `professional_services_settings`

**Files:**
- Create: `src/backend/base/langflow/services/database/models/professional_services_settings/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/professional_services_settings/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_professional_services_settings_model.py`

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)


def test_settings_singleton_id_is_one():
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    assert settings.id == 1


def test_settings_optional_webhook_fields():
    settings = ProfessionalServicesSettings()
    assert settings.webhook_url is None
    assert settings.webhook_secret_encrypted is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_professional_services_settings_model.py -v`

- [ ] **Step 3: Implement the model**

```python
# src/backend/base/langflow/services/database/models/professional_services_settings/__init__.py
from .model import ProfessionalServicesSettings

__all__ = ["ProfessionalServicesSettings"]
```

```python
# src/backend/base/langflow/services/database/models/professional_services_settings/model.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfessionalServicesSettings(SQLModel, table=True):
    __tablename__ = "professional_services_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ps_settings_singleton"),)

    id: int = Field(default=1, primary_key=True)
    default_hourly_rate_low: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )
    default_hourly_rate_high: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )
    webhook_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    webhook_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_utcnow),
    )
    updated_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/database/models/professional_services_settings/ \
        src/backend/tests/unit/services/database/models/test_professional_services_settings_model.py
git commit -m "feat(pro-services): add ProfessionalServicesSettings singleton model"
```

---

### Task 3: Extend existing models — column additions + enum extensions

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/component_metadata/model.py` — add `integration_minutes_low/high`
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py` — add `ps_request_active`
- Modify: `src/backend/base/langflow/services/database/models/organization/model.py` — add `billable_rate_low_per_hour/high_per_hour`
- Modify: `src/backend/base/langflow/services/database/models/admin_notification/model.py` — add `audience_user_id`, extend `NotificationCategory` and `NotificationAudience` enums
- Test: `src/backend/tests/unit/services/database/models/test_pro_service_column_extensions.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/database/models/test_pro_service_column_extensions.py
from langflow.services.database.models.admin_notification.model import (
    NotificationAudience,
    NotificationCategory,
)


def test_notification_audience_has_platform_admin():
    assert NotificationAudience.PLATFORM_ADMIN.value == "platform_admin"


def test_notification_category_has_pro_services():
    assert NotificationCategory.PROFESSIONAL_SERVICES_REQUEST.value == "professional_services_request"


def test_component_metadata_has_integration_minutes_columns():
    from langflow.services.database.models.component_metadata.model import ComponentMetadata
    cols = ComponentMetadata.__table__.columns
    assert "integration_minutes_low" in cols
    assert "integration_minutes_high" in cols


def test_flow_has_ps_request_active():
    from langflow.services.database.models.flow.model import Flow
    assert "ps_request_active" in Flow.__table__.columns


def test_organization_has_billable_rate_columns():
    from langflow.services.database.models.organization.model import Organization
    cols = Organization.__table__.columns
    assert "billable_rate_low_per_hour" in cols
    assert "billable_rate_high_per_hour" in cols


def test_admin_notification_has_audience_user_id():
    from langflow.services.database.models.admin_notification.model import AdminNotification
    assert "audience_user_id" in AdminNotification.__table__.columns
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_pro_service_column_extensions.py -v`

- [ ] **Step 3: Add columns to `ComponentMetadata`**

In `src/backend/base/langflow/services/database/models/component_metadata/model.py`, change the class to:

```python
from sqlmodel import Field

from langflow.services.database.models._metadata import AgentMetadataMixin


class ComponentMetadata(AgentMetadataMixin, table=True):
    __tablename__ = "component_metadata"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    component_name: str = Field(max_length=128, unique=True, index=True)
    integration_minutes_low: int | None = Field(default=None, nullable=True)
    integration_minutes_high: int | None = Field(default=None, nullable=True)
```

- [ ] **Step 4: Add column to `Flow`**

Locate the `Flow` SQLModel class. Add a new column:

```python
ps_request_active: bool = Field(
    default=False,
    sa_column=Column(Boolean, nullable=False, server_default=sa_text("false")),
)
```

(Add imports for `Boolean` from `sqlalchemy` and `sa_text` aliased from `sqlalchemy.text` if not already present.)

- [ ] **Step 5: Add columns to `Organization`**

```python
billable_rate_low_per_hour: Decimal | None = Field(
    default=None, sa_column=Column(Numeric(10, 2), nullable=True),
)
billable_rate_high_per_hour: Decimal | None = Field(
    default=None, sa_column=Column(Numeric(10, 2), nullable=True),
)
```

(Add `from decimal import Decimal` and `from sqlalchemy import Numeric` if not present.)

- [ ] **Step 6: Extend `admin_notification` enums and add `audience_user_id`**

```python
class NotificationCategory(str, Enum):
    USAGE_THRESHOLD = "usage_threshold"
    ALERT_RULE = "alert_rule"
    SYSTEM = "system"
    PROFESSIONAL_SERVICES_REQUEST = "professional_services_request"


class NotificationAudience(str, Enum):
    SUPER_ADMIN = "super_admin"
    PLATFORM_ADMIN = "platform_admin"
```

Add the column to `AdminNotification`:

```python
audience_user_id: UUID | None = Field(
    default=None,
    sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True),
)
```

Add an index for targeted reads. Update `__table_args__`:

```python
__table_args__ = (
    Index("ix_admin_notification_audience_read_created", "audience", "read_at", "created_at"),
    Index("ix_admin_notification_user_read_created", "audience_user_id", "read_at", "created_at"),
)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_pro_service_column_extensions.py -v`
Expected: 6 passed.

- [ ] **Step 8: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/database/models/ \
        src/backend/tests/unit/services/database/models/test_pro_service_column_extensions.py
git commit -m "feat(pro-services): extend models with PS columns + new enum values"
```

---

### Task 4: Alembic revision — schema + backfill + seed

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<gen>_pro_service_quotes.py` (filename auto-generated by alembic)
- Test: `src/backend/tests/integration/alembic/test_pro_service_quotes_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/alembic/test_pro_service_quotes_migration.py
"""Round-trip test: upgrade to head, downgrade one revision, upgrade again."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect


@pytest.mark.integration
def test_pro_service_quotes_migration_round_trip(alembic_config: Config, dev_db_engine):
    command.upgrade(alembic_config, "head")
    insp = inspect(dev_db_engine)
    assert "pro_service_quote" in insp.get_table_names()
    assert "professional_services_settings" in insp.get_table_names()
    flow_cols = {c["name"] for c in insp.get_columns("flow")}
    assert "ps_request_active" in flow_cols
    org_cols = {c["name"] for c in insp.get_columns("organization")}
    assert "billable_rate_low_per_hour" in org_cols
    assert "billable_rate_high_per_hour" in org_cols
    cm_cols = {c["name"] for c in insp.get_columns("component_metadata")}
    assert "integration_minutes_low" in cm_cols
    assert "integration_minutes_high" in cm_cols
    an_cols = {c["name"] for c in insp.get_columns("admin_notification")}
    assert "audience_user_id" in an_cols

    # Singleton row seeded
    with dev_db_engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT default_hourly_rate_low, default_hourly_rate_high "
            "FROM professional_services_settings WHERE id = 1"
        ).first()
        assert row is not None
        assert float(row[0]) == 200.00
        assert float(row[1]) == 200.00

    # Round-trip
    command.downgrade(alembic_config, "-1")
    insp = inspect(dev_db_engine)
    assert "pro_service_quote" not in insp.get_table_names()
    command.upgrade(alembic_config, "head")
```

(Use the existing `alembic_config` and `dev_db_engine` fixtures from `src/backend/tests/conftest.py`. If they don't exist, scaffold them following the pattern used by other migration tests in the repo — search for `command.upgrade` in `src/backend/tests/`.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/integration/alembic/test_pro_service_quotes_migration.py -v`
Expected: FAIL — pro_service_quote table doesn't exist.

- [ ] **Step 3: Generate the migration scaffold**

Run: `cd src/backend/base && uv run alembic revision -m "pro_service_quotes"`

This creates a new file `src/backend/base/langflow/alembic/versions/<rev>_pro_service_quotes.py`.

- [ ] **Step 4: Implement the migration**

Replace the generated file body with:

```python
"""pro_service_quotes

Revision ID: <auto-generated>
Revises: 26b3d04efba1
Create Date: 2026-04-25

"""
from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "<auto-generated>"
down_revision = "26b3d04efba1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns to component_metadata
    op.add_column(
        "component_metadata",
        sa.Column("integration_minutes_low", sa.Integer(), nullable=True),
    )
    op.add_column(
        "component_metadata",
        sa.Column("integration_minutes_high", sa.Integer(), nullable=True),
    )

    # 2. Add ps_request_active to flow
    op.add_column(
        "flow",
        sa.Column(
            "ps_request_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 3. Add billable rate columns to organization
    op.add_column(
        "organization",
        sa.Column("billable_rate_low_per_hour", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "organization",
        sa.Column("billable_rate_high_per_hour", sa.Numeric(10, 2), nullable=True),
    )

    # 4. Add audience_user_id + index to admin_notification
    op.add_column(
        "admin_notification",
        sa.Column(
            "audience_user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_admin_notification_user_read_created",
        "admin_notification",
        ["audience_user_id", "read_at", "created_at"],
    )

    # 5. Create professional_services_settings
    op.create_table(
        "professional_services_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_hourly_rate_low", sa.Numeric(10, 2), nullable=True),
        sa.Column("default_hourly_rate_high", sa.Numeric(10, 2), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_by_user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("id = 1", name="ck_ps_settings_singleton"),
    )

    # 6. Create pro_service_quote
    op.create_table(
        "pro_service_quote",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "org_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "flow_id",
            sa.UUID(),
            sa.ForeignKey("flow.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requester_user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column(
            "assigned_admin_user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("estimated_minutes_low", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes_high", sa.Integer(), nullable=False),
        sa.Column("rate_low_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("rate_high_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("headline_summary", sa.Text(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("org_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("in_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_pro_service_quote_org_status_created",
        "pro_service_quote",
        ["org_id", "status", "created_at"],
    )
    op.create_index(
        "ix_pro_service_quote_status_created",
        "pro_service_quote",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_pro_service_quote_flow_id",
        "pro_service_quote",
        ["flow_id"],
    )

    # 7. Backfill component_metadata defaults
    op.execute(
        "UPDATE component_metadata "
        "SET integration_minutes_low = 15, integration_minutes_high = 60 "
        "WHERE integration_minutes_low IS NULL OR integration_minutes_high IS NULL"
    )

    # 8. Seed professional_services_settings singleton
    op.execute(
        "INSERT INTO professional_services_settings "
        "(id, default_hourly_rate_low, default_hourly_rate_high, updated_at) "
        "VALUES (1, 200.00, 200.00, CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_index("ix_pro_service_quote_flow_id", table_name="pro_service_quote")
    op.drop_index("ix_pro_service_quote_status_created", table_name="pro_service_quote")
    op.drop_index("ix_pro_service_quote_org_status_created", table_name="pro_service_quote")
    op.drop_table("pro_service_quote")
    op.drop_table("professional_services_settings")
    op.drop_index("ix_admin_notification_user_read_created", table_name="admin_notification")
    op.drop_column("admin_notification", "audience_user_id")
    op.drop_column("organization", "billable_rate_high_per_hour")
    op.drop_column("organization", "billable_rate_low_per_hour")
    op.drop_column("flow", "ps_request_active")
    op.drop_column("component_metadata", "integration_minutes_high")
    op.drop_column("component_metadata", "integration_minutes_low")
```

Replace `<auto-generated>` with the actual revision id alembic produced.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/integration/alembic/test_pro_service_quotes_migration.py -v`
Expected: PASS.

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/alembic/versions/*_pro_service_quotes.py \
        src/backend/tests/integration/alembic/test_pro_service_quotes_migration.py
git commit -m "feat(pro-services): alembic migration with schema + seed"
```

---

## Phase B: Backend Services

### Task 5: Settings service — read singleton + resolve rate band

**Files:**
- Create: `src/backend/base/langflow/services/professional_services/__init__.py`
- Create: `src/backend/base/langflow/services/professional_services/settings_service.py`
- Test: `src/backend/tests/unit/services/professional_services/test_settings_service.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/professional_services/test_settings_service.py
from decimal import Decimal
from uuid import uuid4

import pytest

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.professional_services.settings_service import (
    RateBand,
    resolve_rate_band,
)


def test_resolve_rate_band_uses_org_override():
    org = Organization(
        id=uuid4(),
        name="Acme",
        slug="acme",
        billable_rate_low_per_hour=Decimal("150.00"),
        billable_rate_high_per_hour=Decimal("180.00"),
    )
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=Decimal("150.00"), high=Decimal("180.00"))


def test_resolve_rate_band_falls_back_to_global():
    org = Organization(id=uuid4(), name="Acme", slug="acme")
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=Decimal("200.00"), high=Decimal("200.00"))


def test_resolve_rate_band_returns_nones_when_unset():
    org = Organization(id=uuid4(), name="Acme", slug="acme")
    settings = ProfessionalServicesSettings()
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=None, high=None)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/professional_services/test_settings_service.py -v`

- [ ] **Step 3: Implement the service**

```python
# src/backend/base/langflow/services/professional_services/__init__.py
"""Professional Services domain services (settings, preview, submit, webhooks)."""
```

```python
# src/backend/base/langflow/services/professional_services/settings_service.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)


@dataclass(frozen=True)
class RateBand:
    low: Decimal | None
    high: Decimal | None


def resolve_rate_band(
    org: Organization, settings: ProfessionalServicesSettings
) -> RateBand:
    """Org override wins; falls back to global default; both can be None."""
    low = org.billable_rate_low_per_hour or settings.default_hourly_rate_low
    high = org.billable_rate_high_per_hour or settings.default_hourly_rate_high
    return RateBand(low=low, high=high)


def read_settings_singleton(session: Session) -> ProfessionalServicesSettings:
    """Returns the settings singleton; the migration seeded id=1 so this never raises."""
    settings = session.exec(
        select(ProfessionalServicesSettings).where(ProfessionalServicesSettings.id == 1)
    ).one()
    return settings
```

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/professional_services/ \
        src/backend/tests/unit/services/professional_services/test_settings_service.py
git commit -m "feat(pro-services): settings service with rate-band resolution"
```

---

### Task 6: Minutes computation from flow nodes

**Files:**
- Create: `src/backend/base/langflow/services/professional_services/estimate_service.py`
- Test: `src/backend/tests/unit/services/professional_services/test_estimate_service.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/professional_services/test_estimate_service.py
from decimal import Decimal

from langflow.services.professional_services.estimate_service import (
    MinutesEstimate,
    compute_cost_range,
    sum_component_minutes,
)


def test_sum_component_minutes_uses_metadata_when_available():
    nodes = [
        {"data": {"type": "OpenAIModel"}},
        {"data": {"type": "Webhook"}},
    ]
    metadata_by_type = {
        "OpenAIModel": (30, 90),
        "Webhook": (10, 45),
    }
    estimate = sum_component_minutes(nodes, metadata_by_type)
    assert estimate == MinutesEstimate(low=40, high=135, breakdown=[
        {"type": "OpenAIModel", "minutes_low": 30, "minutes_high": 90},
        {"type": "Webhook", "minutes_low": 10, "minutes_high": 45},
    ])


def test_sum_component_minutes_falls_back_to_defaults():
    nodes = [{"data": {"type": "UnknownComponent"}}]
    estimate = sum_component_minutes(nodes, metadata_by_type={})
    assert estimate.low == 15
    assert estimate.high == 60


def test_compute_cost_range_basic():
    cost_low, cost_high = compute_cost_range(
        minutes_low=180, minutes_high=720,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
    )
    assert cost_low == Decimal("600.00")
    assert cost_high == Decimal("2400.00")


def test_compute_cost_range_returns_none_when_rate_unset():
    cost_low, cost_high = compute_cost_range(
        minutes_low=60, minutes_high=120,
        rate_low_per_hour=None, rate_high_per_hour=None,
    )
    assert cost_low is None
    assert cost_high is None
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the service**

```python
# src/backend/base/langflow/services/professional_services/estimate_service.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

DEFAULT_MINUTES_LOW = 15
DEFAULT_MINUTES_HIGH = 60


@dataclass(frozen=True)
class MinutesEstimate:
    low: int
    high: int
    breakdown: list[dict[str, Any]]


def sum_component_minutes(
    nodes: list[dict[str, Any]],
    metadata_by_type: dict[str, tuple[int | None, int | None]],
) -> MinutesEstimate:
    """Sum integration_minutes_low/high across all flow nodes.

    `metadata_by_type` maps component_name -> (low, high). Missing types or
    NULL columns fall back to DEFAULT_MINUTES_LOW / DEFAULT_MINUTES_HIGH.
    """
    breakdown: list[dict[str, Any]] = []
    total_low = 0
    total_high = 0
    for node in nodes:
        component_type = node.get("data", {}).get("type", "Unknown")
        meta_low, meta_high = metadata_by_type.get(component_type, (None, None))
        low = meta_low if meta_low is not None else DEFAULT_MINUTES_LOW
        high = meta_high if meta_high is not None else DEFAULT_MINUTES_HIGH
        breakdown.append(
            {"type": component_type, "minutes_low": low, "minutes_high": high}
        )
        total_low += low
        total_high += high
    return MinutesEstimate(low=total_low, high=total_high, breakdown=breakdown)


def compute_cost_range(
    minutes_low: int,
    minutes_high: int,
    rate_low_per_hour: Decimal | None,
    rate_high_per_hour: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Compute dollar cost range from minutes × rate. Returns (None, None) if
    either rate is unset (graceful degradation)."""
    if rate_low_per_hour is None or rate_high_per_hour is None:
        return (None, None)
    sixty = Decimal("60")
    cost_low = (Decimal(minutes_low) * rate_low_per_hour / sixty).quantize(Decimal("0.01"))
    cost_high = (Decimal(minutes_high) * rate_high_per_hour / sixty).quantize(Decimal("0.01"))
    return (cost_low, cost_high)
```

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/professional_services/estimate_service.py \
        src/backend/tests/unit/services/professional_services/test_estimate_service.py
git commit -m "feat(pro-services): minutes + cost computation"
```

---

### Task 7: LLM generation service — headline + narrative + conversation summary

**Files:**
- Create: `src/backend/base/langflow/services/professional_services/llm_service.py`
- Test: `src/backend/tests/unit/services/professional_services/test_llm_service.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/professional_services/test_llm_service.py
from unittest.mock import AsyncMock

import pytest

from langflow.services.professional_services.llm_service import (
    GeneratedQuoteText,
    generate_quote_text,
)


@pytest.mark.asyncio
async def test_generate_quote_text_returns_three_fields():
    fake_provider = AsyncMock()
    fake_provider.complete_structured.return_value = {
        "headline_summary": "Wire up Slack notifications.",
        "narrative": "User wants to forward build events to Slack.",
        "conversation_summary": "User struggled with OAuth setup.",
    }
    result = await generate_quote_text(
        flow_name="Slack notifier",
        component_breakdown=[{"type": "Webhook", "minutes_low": 15, "minutes_high": 60}],
        chat_history=[{"role": "user", "content": "I'm stuck on OAuth"}],
        provider=fake_provider,
    )
    assert isinstance(result, GeneratedQuoteText)
    assert result.headline_summary == "Wire up Slack notifications."
    assert result.narrative.startswith("User wants")
    assert result.conversation_summary is not None


@pytest.mark.asyncio
async def test_generate_quote_text_null_summary_when_no_chat():
    fake_provider = AsyncMock()
    fake_provider.complete_structured.return_value = {
        "headline_summary": "Forward webhook events.",
        "narrative": "Simple webhook forwarder.",
        "conversation_summary": None,
    }
    result = await generate_quote_text(
        flow_name="Forwarder",
        component_breakdown=[{"type": "Webhook", "minutes_low": 15, "minutes_high": 60}],
        chat_history=None,
        provider=fake_provider,
    )
    assert result.conversation_summary is None


@pytest.mark.asyncio
async def test_system_prompt_includes_secret_redaction_clause():
    """Verifies the system prompt forbids credentials/tokens in output."""
    from langflow.services.professional_services.llm_service import SYSTEM_PROMPT

    text = SYSTEM_PROMPT.lower()
    assert "api key" in text or "credential" in text
    assert "token" in text
    assert "never include" in text or "must not" in text or "do not include" in text
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the service**

```python
# src/backend/base/langflow/services/professional_services/llm_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


SYSTEM_PROMPT = """\
You are scoping a Langflow integration for a Professional Services engineer.
Generate three fields about the user's project:

1. `headline_summary`: ONE sentence under 120 characters describing what the
   user is trying to build.
2. `narrative`: 2-4 sentences for a Professional Services scoping engineer:
   what the integration does, the main components involved, any complexity
   signals from the conversation.
3. `conversation_summary`: 2-3 sentences summarizing what the user has tried
   so far, based on the chat history. Return null if no chat history was
   provided.

CRITICAL CONSTRAINTS:
- Never include API keys, tokens, passwords, secret values, or URLs containing
  tokens. If the conversation references credentials, refer to them generically
  ("their OAuth token", "the API key").
- Do not include personally identifiable information (email addresses, phone
  numbers) — refer to "the user" or "their team."
- Output must be a JSON object with exactly the three keys above.
"""


class LLMProvider(Protocol):
    async def complete_structured(
        self, system_prompt: str, user_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GeneratedQuoteText:
    headline_summary: str
    narrative: str
    conversation_summary: str | None


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline_summary": {"type": "string", "maxLength": 240},
        "narrative": {"type": "string"},
        "conversation_summary": {"type": ["string", "null"]},
    },
    "required": ["headline_summary", "narrative", "conversation_summary"],
}


def _build_user_prompt(
    flow_name: str,
    component_breakdown: list[dict[str, Any]],
    chat_history: list[dict[str, Any]] | None,
) -> str:
    parts = [f"Flow name: {flow_name}", "Components used:"]
    for c in component_breakdown:
        parts.append(f"  - {c['type']} ({c['minutes_low']}-{c['minutes_high']} min)")
    if chat_history:
        parts.append("\nConversation history:")
        for msg in chat_history:
            parts.append(f"  [{msg.get('role', 'user')}] {msg.get('content', '')}")
    else:
        parts.append("\nNo conversation history available.")
    return "\n".join(parts)


async def generate_quote_text(
    flow_name: str,
    component_breakdown: list[dict[str, Any]],
    chat_history: list[dict[str, Any]] | None,
    provider: LLMProvider,
) -> GeneratedQuoteText:
    user_prompt = _build_user_prompt(flow_name, component_breakdown, chat_history)
    response = await provider.complete_structured(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=_RESPONSE_SCHEMA,
    )
    return GeneratedQuoteText(
        headline_summary=response["headline_summary"],
        narrative=response["narrative"],
        conversation_summary=response.get("conversation_summary"),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/services/professional_services/test_llm_service.py -v`

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/professional_services/llm_service.py \
        src/backend/tests/unit/services/professional_services/test_llm_service.py
git commit -m "feat(pro-services): LLM generation service with secret-redaction prompt"
```

---

### Task 8: Permissions module

**Files:**
- Create: `src/backend/base/langflow/services/professional_services/permissions.py`
- Test: `src/backend/tests/unit/services/professional_services/test_permissions.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/professional_services/test_permissions.py
from uuid import uuid4

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.professional_services.permissions import (
    can_close,
    can_edit_admin_notes,
    can_edit_org_notes,
    can_mark_in_progress,
    can_submit,
    can_view_quote,
)


class FakeUser:
    def __init__(self, user_id, org_id, is_super_admin=False, is_platform_admin=False, is_org_admin=False):
        self.id = user_id
        self.org_id = org_id
        self.is_super_admin = is_super_admin
        self.is_platform_admin = is_platform_admin
        self.is_org_admin = is_org_admin


def _quote(org_id, requester_id, status=ProServiceQuoteStatus.OPEN):
    return ProServiceQuote(
        org_id=org_id,
        flow_id=uuid4(),
        requester_user_id=requester_id,
        status=status,
        estimated_minutes_low=15,
        estimated_minutes_high=60,
        headline_summary="x",
        narrative="x",
        submitted_at=__import__("datetime").datetime.utcnow(),
    )


def test_view_admin_sees_all():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    super_admin = FakeUser(uuid4(), org_b, is_super_admin=True)
    platform_admin = FakeUser(uuid4(), org_b, is_platform_admin=True)
    assert can_view_quote(quote, super_admin)
    assert can_view_quote(quote, platform_admin)


def test_view_org_member_sees_their_org_only():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    org_member = FakeUser(uuid4(), org_a)
    other_org_member = FakeUser(uuid4(), org_b)
    assert can_view_quote(quote, org_member)
    assert not can_view_quote(quote, other_org_member)


def test_submit_requires_owner_or_org_admin():
    user_owner = FakeUser(uuid4(), uuid4())
    user_admin = FakeUser(uuid4(), uuid4(), is_org_admin=True)
    user_member = FakeUser(uuid4(), uuid4())
    assert can_submit(flow_owner_id=user_owner.id, user=user_owner)
    assert can_submit(flow_owner_id=uuid4(), user=user_admin)
    assert not can_submit(flow_owner_id=uuid4(), user=user_member)


def test_close_requester_can_self_cancel_open_only():
    org_a = uuid4()
    requester_id = uuid4()
    quote_open = _quote(org_a, requester_id, ProServiceQuoteStatus.OPEN)
    quote_in_progress = _quote(org_a, requester_id, ProServiceQuoteStatus.IN_PROGRESS)
    user = FakeUser(requester_id, org_a)
    assert can_close(quote_open, user)
    assert not can_close(quote_in_progress, user)


def test_mark_in_progress_admin_only_from_open():
    org_a = uuid4()
    quote_open = _quote(org_a, uuid4(), ProServiceQuoteStatus.OPEN)
    quote_closed = _quote(org_a, uuid4(), ProServiceQuoteStatus.CLOSED)
    admin = FakeUser(uuid4(), uuid4(), is_super_admin=True)
    org_user = FakeUser(uuid4(), org_a)
    assert can_mark_in_progress(quote_open, admin)
    assert not can_mark_in_progress(quote_closed, admin)
    assert not can_mark_in_progress(quote_open, org_user)


def test_edit_admin_notes_admin_only():
    quote = _quote(uuid4(), uuid4())
    admin = FakeUser(uuid4(), uuid4(), is_platform_admin=True)
    org_user = FakeUser(uuid4(), quote.org_id)
    assert can_edit_admin_notes(quote, admin)
    assert not can_edit_admin_notes(quote, org_user)


def test_edit_org_notes_any_org_member():
    quote = _quote(uuid4(), uuid4())
    org_member = FakeUser(uuid4(), quote.org_id)
    other_org_member = FakeUser(uuid4(), uuid4())
    assert can_edit_org_notes(quote, org_member)
    assert not can_edit_org_notes(quote, other_org_member)
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement permissions**

```python
# src/backend/base/langflow/services/professional_services/permissions.py
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class _UserLike(Protocol):
    id: UUID
    org_id: UUID | None
    is_super_admin: bool
    is_platform_admin: bool
    is_org_admin: bool


def _is_admin(user: _UserLike) -> bool:
    return bool(user.is_super_admin or user.is_platform_admin)


def can_view_quote(quote: ProServiceQuote, user: _UserLike) -> bool:
    if _is_admin(user):
        return True
    return user.org_id == quote.org_id


def can_submit(*, flow_owner_id: UUID, user: _UserLike) -> bool:
    return user.id == flow_owner_id or user.is_org_admin or _is_admin(user)


def can_mark_in_progress(quote: ProServiceQuote, user: _UserLike) -> bool:
    return _is_admin(user) and quote.status == ProServiceQuoteStatus.OPEN


def can_close(quote: ProServiceQuote, user: _UserLike) -> bool:
    if _is_admin(user) and quote.status != ProServiceQuoteStatus.CLOSED:
        return True
    if (
        user.id == quote.requester_user_id
        and quote.status == ProServiceQuoteStatus.OPEN
    ):
        return True
    return False


def can_edit_admin_notes(quote: ProServiceQuote, user: _UserLike) -> bool:
    return _is_admin(user)


def can_edit_org_notes(quote: ProServiceQuote, user: _UserLike) -> bool:
    return user.org_id == quote.org_id or _is_admin(user)
```

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/professional_services/permissions.py \
        src/backend/tests/unit/services/professional_services/test_permissions.py
git commit -m "feat(pro-services): permissions module with role-based scope checks"
```

---

## Phase C: Backend API Endpoints

### Task 9: Pydantic schemas for API requests/responses

**Files:**
- Create: `src/backend/base/langflow/api/v1/schemas/pro_service_quote.py`
- Test: `src/backend/tests/unit/api/v1/schemas/test_pro_service_quote_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/api/v1/schemas/test_pro_service_quote_schemas.py
from decimal import Decimal
from uuid import uuid4

from langflow.api.v1.schemas.pro_service_quote import (
    PreviewResponse,
    QuoteRead,
    QuoteSubmitRequest,
    QuoteUpdateRequest,
)


def test_preview_response_validates():
    resp = PreviewResponse(
        minutes_low=180, minutes_high=720,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
        cost_low=Decimal("600.00"), cost_high=Decimal("2400.00"),
        headline_summary="x", narrative="y", conversation_summary=None,
        component_breakdown=[],
    )
    assert resp.cost_low == Decimal("600.00")


def test_submit_request_requires_text_fields():
    req = QuoteSubmitRequest(
        minutes_low=15, minutes_high=60,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
        headline_summary="x", narrative="y", conversation_summary=None,
        org_notes=None,
    )
    assert req.minutes_low == 15


def test_update_request_all_optional():
    req = QuoteUpdateRequest()
    assert req.org_notes is None and req.admin_notes is None and req.status is None
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement schemas**

```python
# src/backend/base/langflow/api/v1/schemas/pro_service_quote.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuoteStatus,
)


class ComponentBreakdownItem(BaseModel):
    type: str
    minutes_low: int
    minutes_high: int


class PreviewResponse(BaseModel):
    minutes_low: int
    minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    cost_low: Decimal | None
    cost_high: Decimal | None
    headline_summary: str
    narrative: str
    conversation_summary: str | None
    component_breakdown: list[ComponentBreakdownItem]


class QuoteSubmitRequest(BaseModel):
    minutes_low: int
    minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    headline_summary: str = Field(max_length=240)
    narrative: str
    conversation_summary: str | None
    org_notes: str | None


class QuoteUpdateRequest(BaseModel):
    org_notes: str | None = None
    admin_notes: str | None = None
    status: ProServiceQuoteStatus | None = None
    assigned_admin_user_id: UUID | None = None


class QuoteRead(BaseModel):
    id: UUID
    org_id: UUID
    org_name: str  # denormalized at read time for list/detail
    flow_id: UUID | None
    flow_name: str | None  # denormalized at read time; None when flow was deleted
    requester_user_id: UUID
    requester_email: str | None
    status: ProServiceQuoteStatus
    assigned_admin_user_id: UUID | None
    estimated_minutes_low: int
    estimated_minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    headline_summary: str
    narrative: str
    conversation_summary: str | None
    org_notes: str | None
    admin_notes: str | None
    created_at: datetime
    submitted_at: datetime
    in_progress_at: datetime | None
    closed_at: datetime | None
    closed_by_user_id: UUID | None

    model_config = {"from_attributes": True}


def quote_to_read(quote, org, flow, requester) -> "QuoteRead":
    """Build a QuoteRead with denormalized org_name/flow_name/requester_email.
    Each related entity may be None (e.g., flow deleted)."""
    return QuoteRead(
        id=quote.id,
        org_id=quote.org_id,
        org_name=org.name if org else "(unknown)",
        flow_id=quote.flow_id,
        flow_name=flow.name if flow else None,
        requester_user_id=quote.requester_user_id,
        requester_email=requester.email if requester else None,
        status=quote.status,
        assigned_admin_user_id=quote.assigned_admin_user_id,
        estimated_minutes_low=quote.estimated_minutes_low,
        estimated_minutes_high=quote.estimated_minutes_high,
        rate_low_per_hour=quote.rate_low_per_hour,
        rate_high_per_hour=quote.rate_high_per_hour,
        headline_summary=quote.headline_summary,
        narrative=quote.narrative,
        conversation_summary=quote.conversation_summary,
        org_notes=quote.org_notes,
        admin_notes=quote.admin_notes,
        created_at=quote.created_at,
        submitted_at=quote.submitted_at,
        in_progress_at=quote.in_progress_at,
        closed_at=quote.closed_at,
        closed_by_user_id=quote.closed_by_user_id,
    )


class QuoteListResponse(BaseModel):
    items: list[QuoteRead]
    total: int
```

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/schemas/pro_service_quote.py \
        src/backend/tests/unit/api/v1/schemas/test_pro_service_quote_schemas.py
git commit -m "feat(pro-services): API schemas for preview/submit/update/read"
```

---

### Task 10: Preview endpoint

**Files:**
- Create: `src/backend/base/langflow/api/v1/pro_service_quotes.py`
- Modify: `src/backend/base/langflow/api/v1/__init__.py` — register router
- Test: `src/backend/tests/integration/api/test_pro_service_quotes_preview.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/api/test_pro_service_quotes_preview.py
import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_preview_returns_estimate(
    async_client: AsyncClient, authenticated_org_owner_headers, seeded_flow
):
    resp = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes/preview",
        headers=authenticated_org_owner_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["minutes_low"] >= 15
    assert body["minutes_high"] >= body["minutes_low"]
    assert body["rate_low_per_hour"] == "200.00"
    assert body["headline_summary"]
    assert body["narrative"]


@pytest.mark.integration
async def test_preview_returns_409_when_active(
    async_client: AsyncClient, authenticated_org_owner_headers, seeded_flow_with_active_request
):
    resp = await async_client.post(
        f"/api/v1/flows/{seeded_flow_with_active_request.id}/pro-service-quotes/preview",
        headers=authenticated_org_owner_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ps_request_active"
```

(Use the existing fixtures: `async_client`, `authenticated_org_owner_headers`, `seeded_flow`. Add `seeded_flow_with_active_request` to a fixtures file using the same factory pattern as `seeded_flow` but flipping `ps_request_active=True`.)

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the endpoint module skeleton + preview**

```python
# src/backend/base/langflow/api/v1/pro_service_quotes.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from langflow.api.utils import get_current_organization, get_current_user
from langflow.api.v1.schemas.pro_service_quote import (
    ComponentBreakdownItem,
    PreviewResponse,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_db_service, get_llm_provider
from langflow.services.professional_services.estimate_service import (
    compute_cost_range,
    sum_component_minutes,
)
from langflow.services.professional_services.llm_service import generate_quote_text
from langflow.services.professional_services.settings_service import (
    read_settings_singleton,
    resolve_rate_band,
)

router = APIRouter(prefix="/pro-service-quotes", tags=["Pro-Service Quotes"])


@router.post("/flows/{flow_id}/pro-service-quotes/preview", response_model=PreviewResponse)
async def preview_quote(
    flow_id: UUID,
    user=Depends(get_current_user),
    org=Depends(get_current_organization),
    db_service=Depends(get_db_service),
    llm_provider=Depends(get_llm_provider),
):
    async with db_service.with_session() as session:
        flow = session.get(Flow, flow_id)
        if flow is None:
            raise HTTPException(status_code=404, detail="flow_not_found")
        if flow.ps_request_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ps_request_active", "message": "An active PS request already exists for this flow."},
            )

        nodes = flow.data.get("nodes", []) if isinstance(flow.data, dict) else []
        component_types = sorted({n.get("data", {}).get("type", "") for n in nodes if n.get("data")})
        rows = session.exec(
            select(ComponentMetadata).where(ComponentMetadata.component_name.in_(component_types))
        ).all()
        metadata_by_type = {
            row.component_name: (row.integration_minutes_low, row.integration_minutes_high)
            for row in rows
        }
        estimate = sum_component_minutes(nodes, metadata_by_type)

        settings = read_settings_singleton(session)
        rate_band = resolve_rate_band(org, settings)
        cost_low, cost_high = compute_cost_range(
            estimate.low, estimate.high, rate_band.low, rate_band.high
        )

        # Pull recent assistant chat history for this flow if available; otherwise None.
        chat_history = _load_assistant_history(session, flow_id=flow.id, user_id=user.id)
        generated = await generate_quote_text(
            flow_name=flow.name,
            component_breakdown=estimate.breakdown,
            chat_history=chat_history,
            provider=llm_provider,
        )

    return PreviewResponse(
        minutes_low=estimate.low,
        minutes_high=estimate.high,
        rate_low_per_hour=rate_band.low,
        rate_high_per_hour=rate_band.high,
        cost_low=cost_low,
        cost_high=cost_high,
        headline_summary=generated.headline_summary,
        narrative=generated.narrative,
        conversation_summary=generated.conversation_summary,
        component_breakdown=[ComponentBreakdownItem(**b) for b in estimate.breakdown],
    )


def _load_assistant_history(session: Session, *, flow_id: UUID, user_id: UUID) -> list[dict] | None:
    """Returns recent assistant conversation messages for this flow/user, or None if absent.

    The exact source depends on the assistant message persistence layer. If
    chat history isn't readily queryable, return None — the LLM prompt
    handles the no-history case explicitly.
    """
    return None  # v1: skip; v1.1 wires this when assistant message persistence is settled
```

(`get_llm_provider` should resolve to whichever provider the assistant currently uses. If a single provider isn't centrally registered, follow the pattern in `services/assistant/service.py` to instantiate one inline.)

- [ ] **Step 4: Register the router**

In `src/backend/base/langflow/api/v1/__init__.py`, add:

```python
from langflow.api.v1.pro_service_quotes import router as pro_service_quotes_router

# in the router registration block:
api_router.include_router(pro_service_quotes_router)
```

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/pro_service_quotes.py \
        src/backend/base/langflow/api/v1/__init__.py \
        src/backend/tests/integration/api/test_pro_service_quotes_preview.py
git commit -m "feat(pro-services): preview endpoint with rate resolution + LLM call"
```

---

### Task 11: Submit endpoint with bell broadcast + webhook enqueue

**Files:**
- Modify: `src/backend/base/langflow/api/v1/pro_service_quotes.py` — add submit handler
- Create: `src/backend/base/langflow/services/professional_services/submit_service.py`
- Test: `src/backend/tests/integration/api/test_pro_service_quotes_submit.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/api/test_pro_service_quotes_submit.py
import pytest


@pytest.mark.integration
async def test_submit_persists_and_sets_flag(
    async_client, authenticated_org_owner_headers, seeded_flow, db_session
):
    payload = {
        "minutes_low": 30, "minutes_high": 90,
        "rate_low_per_hour": "200.00", "rate_high_per_hour": "200.00",
        "headline_summary": "Build Slack notifier",
        "narrative": "Send build events to Slack",
        "conversation_summary": None,
        "org_notes": "we need this by end of quarter",
    }
    resp = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes",
        headers=authenticated_org_owner_headers,
        json=payload,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["headline_summary"] == "Build Slack notifier"

    db_session.refresh(seeded_flow)
    assert seeded_flow.ps_request_active is True


@pytest.mark.integration
async def test_submit_writes_admin_bell_rows(
    async_client, authenticated_org_owner_headers, seeded_flow, db_session
):
    resp = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes",
        headers=authenticated_org_owner_headers,
        json={
            "minutes_low": 30, "minutes_high": 90,
            "rate_low_per_hour": "200.00", "rate_high_per_hour": "200.00",
            "headline_summary": "x", "narrative": "y", "conversation_summary": None, "org_notes": None,
        },
    )
    assert resp.status_code == 201
    from langflow.services.database.models.admin_notification.model import (
        AdminNotification, NotificationCategory,
    )
    from sqlmodel import select
    rows = db_session.exec(
        select(AdminNotification).where(
            AdminNotification.category == NotificationCategory.PROFESSIONAL_SERVICES_REQUEST
        )
    ).all()
    audiences = {r.audience for r in rows}
    assert "super_admin" in {a.value for a in audiences}
    assert "platform_admin" in {a.value for a in audiences}


@pytest.mark.integration
async def test_submit_409_when_active(
    async_client, authenticated_org_owner_headers, seeded_flow_with_active_request
):
    resp = await async_client.post(
        f"/api/v1/flows/{seeded_flow_with_active_request.id}/pro-service-quotes",
        headers=authenticated_org_owner_headers,
        json={
            "minutes_low": 15, "minutes_high": 60,
            "rate_low_per_hour": "200.00", "rate_high_per_hour": "200.00",
            "headline_summary": "x", "narrative": "y", "conversation_summary": None, "org_notes": None,
        },
    )
    assert resp.status_code == 409
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the submit service**

```python
# src/backend/base/langflow/services/professional_services/submit_service.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session

from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class ActiveRequestError(Exception):
    """Raised when a flow already has ps_request_active=True at submit time."""


def submit_quote(
    *,
    session: Session,
    flow: Flow,
    org: Organization,
    requester_user_id: UUID,
    payload,  # QuoteSubmitRequest
) -> ProServiceQuote:
    """Atomically create the quote, set the flag, and write admin bell rows."""
    if flow.ps_request_active:
        raise ActiveRequestError()

    now = datetime.now(timezone.utc)
    quote = ProServiceQuote(
        org_id=org.id,
        flow_id=flow.id,
        requester_user_id=requester_user_id,
        status=ProServiceQuoteStatus.OPEN,
        estimated_minutes_low=payload.minutes_low,
        estimated_minutes_high=payload.minutes_high,
        rate_low_per_hour=payload.rate_low_per_hour,
        rate_high_per_hour=payload.rate_high_per_hour,
        headline_summary=payload.headline_summary,
        narrative=payload.narrative,
        conversation_summary=payload.conversation_summary,
        org_notes=payload.org_notes,
        submitted_at=now,
    )
    session.add(quote)
    flow.ps_request_active = True
    session.add(flow)
    session.flush()  # ensures quote.id is populated for the bell metadata

    for audience in (NotificationAudience.SUPER_ADMIN, NotificationAudience.PLATFORM_ADMIN):
        session.add(
            AdminNotification(
                org_id=org.id,
                category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
                severity=NotificationSeverity.INFO,
                title=f"New Pro-Service request from {org.name}",
                body_md=quote.headline_summary,
                metadata_json={"quote_id": str(quote.id), "event": "submitted"},
                audience=audience,
            )
        )
    return quote
```

- [ ] **Step 4: Add the submit handler to `pro_service_quotes.py`**

Append to `src/backend/base/langflow/api/v1/pro_service_quotes.py`:

```python
from fastapi import status as http_status

from langflow.api.v1.schemas.pro_service_quote import QuoteRead, QuoteSubmitRequest
from langflow.services.professional_services.permissions import can_submit
from langflow.services.professional_services.submit_service import (
    ActiveRequestError,
    submit_quote,
)
from langflow.services.professional_services.webhook_service import enqueue_quote_webhook


@router.post(
    "/flows/{flow_id}/pro-service-quotes",
    response_model=QuoteRead,
    status_code=http_status.HTTP_201_CREATED,
)
async def submit_quote_endpoint(
    flow_id: UUID,
    payload: QuoteSubmitRequest,
    user=Depends(get_current_user),
    org=Depends(get_current_organization),
    db_service=Depends(get_db_service),
):
    async with db_service.with_session() as session:
        flow = session.get(Flow, flow_id)
        if flow is None:
            raise HTTPException(status_code=404, detail="flow_not_found")
        if not can_submit(flow_owner_id=flow.user_id, user=user):
            raise HTTPException(status_code=403, detail="forbidden")
        try:
            quote = submit_quote(
                session=session, flow=flow, org=org,
                requester_user_id=user.id, payload=payload,
            )
        except ActiveRequestError:
            raise HTTPException(
                status_code=409,
                detail={"code": "ps_request_active"},
            )
        await session.commit()
        await session.refresh(quote)

        from langflow.services.database.models.user.model import User
        requester = session.get(User, quote.requester_user_id)
        result = quote_to_read(quote, org, flow, requester)

    # Async tail: webhook (no-op if URL not configured)
    enqueue_quote_webhook(quote_id=quote.id)
    return result
```

(`enqueue_quote_webhook` is implemented in Task 12; for now stub it as a no-op so this task compiles. `quote_to_read` was added to the schema module in Task 9.)

- [ ] **Step 5: Stub the webhook enqueue**

Create `src/backend/base/langflow/services/professional_services/webhook_service.py` with a stub:

```python
"""Webhook delivery for pro-service-quote.submitted events. Implemented in Task 12."""
from __future__ import annotations

from uuid import UUID


def enqueue_quote_webhook(*, quote_id: UUID) -> None:
    """Stub — replaced in Task 12 with real HMAC-signed delivery."""
    return None
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/integration/api/test_pro_service_quotes_submit.py -v`

- [ ] **Step 7: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/pro_service_quotes.py \
        src/backend/base/langflow/services/professional_services/submit_service.py \
        src/backend/base/langflow/services/professional_services/webhook_service.py \
        src/backend/tests/integration/api/test_pro_service_quotes_submit.py
git commit -m "feat(pro-services): submit endpoint with admin bell broadcast"
```

---

### Task 12: Webhook delivery (HMAC-signed mirror)

**Files:**
- Modify: `src/backend/base/langflow/services/professional_services/webhook_service.py` — full implementation
- Test: `src/backend/tests/integration/services/professional_services/test_webhook_service.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/services/professional_services/test_webhook_service.py
import pytest

from langflow.services.professional_services.webhook_service import (
    build_webhook_payload,
    enqueue_quote_webhook,
)


@pytest.mark.integration
async def test_enqueue_no_op_when_url_unset(seeded_quote, settings_with_no_webhook):
    # Should silently skip; no exceptions, no broker calls.
    enqueue_quote_webhook(quote_id=seeded_quote.id)


@pytest.mark.integration
async def test_enqueue_dispatches_when_url_set(
    seeded_quote, settings_with_webhook_url, mock_webhook_broker
):
    enqueue_quote_webhook(quote_id=seeded_quote.id)
    assert mock_webhook_broker.deliver.call_count == 1
    payload = mock_webhook_broker.deliver.call_args.kwargs["body"]
    assert payload["event"] == "pro_service_quote.submitted"
    assert payload["quote_id"] == str(seeded_quote.id)
    assert "rate_low_per_hour" in payload["estimate"]


def test_build_webhook_payload_omits_secrets():
    """The payload should not include any user/admin notes verbatim if they
    contain credential-shaped strings — but for v1 we trust the LLM redaction
    in narrative/summary and omit org_notes/admin_notes from the webhook entirely."""
    from langflow.services.database.models.pro_service_quote.model import ProServiceQuote
    quote = ProServiceQuote.__new__(ProServiceQuote)  # build minimally for serialization
    # ... populate fields
    # Assert the dict returned by build_webhook_payload has no key "org_notes" / "admin_notes"
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the webhook service**

```python
# src/backend/base/langflow/services/professional_services/webhook_service.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from langflow.services.database.models.pro_service_quote.model import ProServiceQuote
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.professional_services.settings_service import (
    read_settings_singleton,
)
from langflow.worker_app.webhook import deliver_webhook  # existing HMAC-signed dispatcher


def build_webhook_payload(quote: ProServiceQuote, *, base_url: str, org_name: str, requester_email: str) -> dict[str, Any]:
    flow_url = f"{base_url}/flow/{quote.flow_id}" if quote.flow_id else None
    return {
        "event": "pro_service_quote.submitted",
        "quote_id": str(quote.id),
        "org": {"id": str(quote.org_id), "name": org_name},
        "flow": {"id": str(quote.flow_id) if quote.flow_id else None, "url": flow_url},
        "requester": {"id": str(quote.requester_user_id), "email": requester_email},
        "estimate": {
            "minutes_low": quote.estimated_minutes_low,
            "minutes_high": quote.estimated_minutes_high,
            "rate_low_per_hour": float(quote.rate_low_per_hour) if quote.rate_low_per_hour else None,
            "rate_high_per_hour": float(quote.rate_high_per_hour) if quote.rate_high_per_hour else None,
            "currency": "USD",
        },
        "headline_summary": quote.headline_summary,
        "narrative": quote.narrative,
        "conversation_summary": quote.conversation_summary,
        # Intentionally exclude org_notes / admin_notes — webhook receivers may
        # persist payloads in less-trusted places, and the spec says only
        # narrative/summary go through secret redaction in the LLM prompt.
    }


def enqueue_quote_webhook(*, quote_id: UUID) -> None:
    """No-op when webhook_url is unset; otherwise enqueues HMAC-signed delivery."""
    db_service = get_db_service()
    settings_service = get_settings_service()
    base_url = settings_service.langflow_base_url

    with db_service.session_scope() as session:
        quote = session.get(ProServiceQuote, quote_id)
        if quote is None:
            return
        ps_settings = read_settings_singleton(session)
        if not ps_settings.webhook_url or not ps_settings.webhook_secret_encrypted:
            return

        # Resolve org and requester email
        from langflow.services.database.models.organization.model import Organization
        from langflow.services.database.models.user.model import User
        org = session.get(Organization, quote.org_id)
        requester = session.get(User, quote.requester_user_id)

        body = build_webhook_payload(
            quote,
            base_url=base_url,
            org_name=org.name if org else "",
            requester_email=requester.email if requester else "",
        )
        secret = settings_service.decrypt(ps_settings.webhook_secret_encrypted)

    deliver_webhook(
        url=ps_settings.webhook_url,
        body=body,
        secret=secret,
        event="pro_service_quote.submitted",
    )
```

(Adapt the deliver_webhook call signature to whatever `worker_app/webhook.py` actually exposes — the spec says it's `deliver_webhook` with HMAC signing built in. Read the existing function signature first.)

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/professional_services/webhook_service.py \
        src/backend/tests/integration/services/professional_services/test_webhook_service.py
git commit -m "feat(pro-services): HMAC-signed webhook mirror on submit"
```

---

### Task 13: List + detail endpoints with role-scoped filtering

**Files:**
- Modify: `src/backend/base/langflow/api/v1/pro_service_quotes.py` — add list and detail handlers
- Test: `src/backend/tests/integration/api/test_pro_service_quotes_list.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/api/test_pro_service_quotes_list.py
import pytest


@pytest.mark.integration
async def test_org_member_sees_only_their_org_quotes(
    async_client, authenticated_org_a_member_headers, seeded_quote_org_a, seeded_quote_org_b
):
    resp = await async_client.get(
        "/api/v1/pro-service-quotes",
        headers=authenticated_org_a_member_headers,
    )
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(seeded_quote_org_a.id) in ids
    assert str(seeded_quote_org_b.id) not in ids


@pytest.mark.integration
async def test_super_admin_sees_all_orgs(
    async_client, authenticated_super_admin_headers, seeded_quote_org_a, seeded_quote_org_b
):
    resp = await async_client.get(
        "/api/v1/pro-service-quotes",
        headers=authenticated_super_admin_headers,
    )
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(seeded_quote_org_a.id) in ids
    assert str(seeded_quote_org_b.id) in ids


@pytest.mark.integration
async def test_detail_404_for_other_org_member(
    async_client, authenticated_org_a_member_headers, seeded_quote_org_b
):
    resp = await async_client.get(
        f"/api/v1/pro-service-quotes/{seeded_quote_org_b.id}",
        headers=authenticated_org_a_member_headers,
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_status_filter(
    async_client, authenticated_super_admin_headers, seeded_quote_open, seeded_quote_closed
):
    resp = await async_client.get(
        "/api/v1/pro-service-quotes?status=open",
        headers=authenticated_super_admin_headers,
    )
    statuses = {item["status"] for item in resp.json()["items"]}
    assert statuses == {"open"}
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement list and detail handlers**

Append to `src/backend/base/langflow/api/v1/pro_service_quotes.py`:

```python
from typing import Annotated

from fastapi import Query

from langflow.api.v1.schemas.pro_service_quote import QuoteListResponse
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.professional_services.permissions import can_view_quote


from langflow.api.v1.schemas.pro_service_quote import quote_to_read
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@router.get("", response_model=QuoteListResponse)
async def list_quotes(
    status_filter: Annotated[ProServiceQuoteStatus | None, Query(alias="status")] = None,
    org_id_filter: Annotated[UUID | None, Query(alias="org_id")] = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
    org=Depends(get_current_organization),
    db_service=Depends(get_db_service),
):
    is_admin = bool(user.is_super_admin or user.is_platform_admin)
    async with db_service.with_session() as session:
        query = select(ProServiceQuote).order_by(ProServiceQuote.created_at.desc())
        if not is_admin:
            query = query.where(ProServiceQuote.org_id == org.id)
        elif org_id_filter is not None:
            query = query.where(ProServiceQuote.org_id == org_id_filter)
        if status_filter is not None:
            query = query.where(ProServiceQuote.status == status_filter)

        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        rows = session.exec(query.limit(limit).offset(offset)).all()

        # Resolve denormalized fields (org name, flow name, requester email) in batch
        org_ids = {r.org_id for r in rows}
        flow_ids = {r.flow_id for r in rows if r.flow_id}
        user_ids = {r.requester_user_id for r in rows}
        orgs = {o.id: o for o in session.exec(select(Organization).where(Organization.id.in_(org_ids))).all()}
        flows = {f.id: f for f in session.exec(select(Flow).where(Flow.id.in_(flow_ids))).all()} if flow_ids else {}
        users = {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all()}

        items = [
            quote_to_read(r, orgs.get(r.org_id), flows.get(r.flow_id), users.get(r.requester_user_id))
            for r in rows
        ]
    return QuoteListResponse(items=items, total=total)


@router.get("/{quote_id}", response_model=QuoteRead)
async def get_quote(
    quote_id: UUID,
    user=Depends(get_current_user),
    db_service=Depends(get_db_service),
):
    async with db_service.with_session() as session:
        quote = session.get(ProServiceQuote, quote_id)
        if quote is None or not can_view_quote(quote, user):
            # 404 (not 403) for cross-tenant — don't leak existence
            raise HTTPException(status_code=404, detail="quote_not_found")
        org = session.get(Organization, quote.org_id)
        flow = session.get(Flow, quote.flow_id) if quote.flow_id else None
        requester = session.get(User, quote.requester_user_id)
    return quote_to_read(quote, org, flow, requester)
```

(Add `from sqlalchemy import func` to the imports.)

- [ ] **Step 4: Run the test to verify it passes**

- [ ] **Step 5: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/pro_service_quotes.py \
        src/backend/tests/integration/api/test_pro_service_quotes_list.py
git commit -m "feat(pro-services): list and detail endpoints with role-scoped filtering"
```

---

### Task 14: PATCH endpoint with state transitions

**Files:**
- Modify: `src/backend/base/langflow/api/v1/pro_service_quotes.py` — add PATCH handler
- Create: `src/backend/base/langflow/services/professional_services/transitions.py`
- Test: `src/backend/tests/integration/api/test_pro_service_quotes_patch.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/api/test_pro_service_quotes_patch.py
import pytest


@pytest.mark.integration
async def test_admin_marks_in_progress(
    async_client, authenticated_super_admin_headers, seeded_quote_open, db_session
):
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_open.id}",
        headers=authenticated_super_admin_headers,
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    db_session.refresh(seeded_quote_open)
    assert seeded_quote_open.status.value == "in_progress"
    assert seeded_quote_open.in_progress_at is not None


@pytest.mark.integration
async def test_admin_closes_clears_active_flag(
    async_client, authenticated_super_admin_headers, seeded_quote_in_progress, db_session
):
    flow = seeded_quote_in_progress.flow_id
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_in_progress.id}",
        headers=authenticated_super_admin_headers,
        json={"status": "closed"},
    )
    assert resp.status_code == 200
    # flow.ps_request_active must be False
    from langflow.services.database.models.flow.model import Flow
    refreshed_flow = db_session.get(Flow, flow)
    assert refreshed_flow.ps_request_active is False


@pytest.mark.integration
async def test_requester_self_cancels_open(
    async_client, authenticated_requester_headers, seeded_quote_open, db_session
):
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_open.id}",
        headers=authenticated_requester_headers,
        json={"status": "closed"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
async def test_requester_cannot_mark_in_progress(
    async_client, authenticated_requester_headers, seeded_quote_open
):
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_open.id}",
        headers=authenticated_requester_headers,
        json={"status": "in_progress"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
async def test_org_member_edits_org_notes(
    async_client, authenticated_other_org_member_headers, seeded_quote_open, db_session
):
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_open.id}",
        headers=authenticated_other_org_member_headers,
        json={"org_notes": "team discussed: prioritize for Q2"},
    )
    assert resp.status_code == 200
    db_session.refresh(seeded_quote_open)
    assert seeded_quote_open.org_notes == "team discussed: prioritize for Q2"


@pytest.mark.integration
async def test_org_member_cannot_edit_admin_notes(
    async_client, authenticated_other_org_member_headers, seeded_quote_open
):
    resp = await async_client.patch(
        f"/api/v1/pro-service-quotes/{seeded_quote_open.id}",
        headers=authenticated_other_org_member_headers,
        json={"admin_notes": "internal only"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement transitions module**

```python
# src/backend/base/langflow/services/professional_services/transitions.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session

from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class IllegalTransitionError(Exception):
    """Raised when a state transition is not legal."""


def transition_to_in_progress(
    *, session: Session, quote: ProServiceQuote, actor_user_id: UUID
) -> None:
    if quote.status != ProServiceQuoteStatus.OPEN:
        raise IllegalTransitionError(f"cannot move from {quote.status} to in_progress")
    quote.status = ProServiceQuoteStatus.IN_PROGRESS
    quote.in_progress_at = datetime.now(timezone.utc)
    if quote.assigned_admin_user_id is None:
        quote.assigned_admin_user_id = actor_user_id
    session.add(quote)
    _bell_for_requester(session, quote, "in_progress")


def transition_to_closed(
    *, session: Session, quote: ProServiceQuote, actor_user_id: UUID, by_requester: bool
) -> None:
    if quote.status == ProServiceQuoteStatus.CLOSED:
        raise IllegalTransitionError("already closed")
    quote.status = ProServiceQuoteStatus.CLOSED
    quote.closed_at = datetime.now(timezone.utc)
    quote.closed_by_user_id = actor_user_id
    session.add(quote)

    flow = session.get(Flow, quote.flow_id) if quote.flow_id else None
    if flow is not None:
        flow.ps_request_active = False
        session.add(flow)

    if by_requester:
        _bell_broadcast_admins(session, quote, "cancelled")
    else:
        _bell_for_requester(session, quote, "closed")


def _bell_for_requester(session: Session, quote: ProServiceQuote, new_status: str) -> None:
    session.add(
        AdminNotification(
            org_id=quote.org_id,
            category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
            severity=NotificationSeverity.INFO,
            title="Pro-Service request status updated",
            body_md=f"Your Pro-Service request is now {new_status.replace('_', ' ')}.",
            metadata_json={"quote_id": str(quote.id), "event": new_status},
            audience_user_id=quote.requester_user_id,
            audience=NotificationAudience.SUPER_ADMIN,  # ignored when audience_user_id is set
        )
    )


def _bell_broadcast_admins(session: Session, quote: ProServiceQuote, event: str) -> None:
    for audience in (NotificationAudience.SUPER_ADMIN, NotificationAudience.PLATFORM_ADMIN):
        session.add(
            AdminNotification(
                org_id=quote.org_id,
                category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
                severity=NotificationSeverity.INFO,
                title=f"Pro-Service request {event}",
                body_md=f"{event.title()}: {quote.headline_summary}",
                metadata_json={"quote_id": str(quote.id), "event": event},
                audience=audience,
            )
        )
```

- [ ] **Step 4: Add the PATCH handler**

Append to `src/backend/base/langflow/api/v1/pro_service_quotes.py`:

```python
from langflow.api.v1.schemas.pro_service_quote import QuoteUpdateRequest
from langflow.services.professional_services.permissions import (
    can_close,
    can_edit_admin_notes,
    can_edit_org_notes,
    can_mark_in_progress,
)
from langflow.services.professional_services.transitions import (
    IllegalTransitionError,
    transition_to_closed,
    transition_to_in_progress,
)


@router.patch("/{quote_id}", response_model=QuoteRead)
async def update_quote(
    quote_id: UUID,
    payload: QuoteUpdateRequest,
    user=Depends(get_current_user),
    db_service=Depends(get_db_service),
):
    async with db_service.with_session() as session:
        quote = session.get(ProServiceQuote, quote_id)
        if quote is None or not can_view_quote(quote, user):
            raise HTTPException(status_code=404, detail="quote_not_found")

        if payload.org_notes is not None:
            if not can_edit_org_notes(quote, user):
                raise HTTPException(status_code=403, detail="cannot_edit_org_notes")
            quote.org_notes = payload.org_notes

        if payload.admin_notes is not None:
            if not can_edit_admin_notes(quote, user):
                raise HTTPException(status_code=403, detail="cannot_edit_admin_notes")
            quote.admin_notes = payload.admin_notes

        if payload.assigned_admin_user_id is not None:
            if not (user.is_super_admin or user.is_platform_admin):
                raise HTTPException(status_code=403, detail="cannot_assign")
            quote.assigned_admin_user_id = payload.assigned_admin_user_id

        if payload.status is not None and payload.status != quote.status:
            try:
                if payload.status == ProServiceQuoteStatus.IN_PROGRESS:
                    if not can_mark_in_progress(quote, user):
                        raise HTTPException(status_code=403, detail="cannot_mark_in_progress")
                    transition_to_in_progress(session=session, quote=quote, actor_user_id=user.id)
                elif payload.status == ProServiceQuoteStatus.CLOSED:
                    if not can_close(quote, user):
                        raise HTTPException(status_code=403, detail="cannot_close")
                    by_requester = (
                        user.id == quote.requester_user_id
                        and not (user.is_super_admin or user.is_platform_admin)
                    )
                    transition_to_closed(
                        session=session, quote=quote,
                        actor_user_id=user.id, by_requester=by_requester,
                    )
                else:
                    raise HTTPException(status_code=422, detail="unsupported_target_status")
            except IllegalTransitionError as e:
                raise HTTPException(status_code=409, detail=str(e))

        session.add(quote)
        await session.commit()
        await session.refresh(quote)

        org = session.get(Organization, quote.org_id)
        flow = session.get(Flow, quote.flow_id) if quote.flow_id else None
        requester = session.get(User, quote.requester_user_id)
        result = quote_to_read(quote, org, flow, requester)
    return result
```

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/pro_service_quotes.py \
        src/backend/base/langflow/services/professional_services/transitions.py \
        src/backend/tests/integration/api/test_pro_service_quotes_patch.py
git commit -m "feat(pro-services): PATCH endpoint with state transitions + targeted bell"
```

---

### Task 15: Admin settings endpoints + test-webhook

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/professional_services_settings.py`
- Modify: `src/backend/base/langflow/api/v1/admin/__init__.py` — register router
- Test: `src/backend/tests/integration/api/admin/test_professional_services_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/integration/api/admin/test_professional_services_settings.py
import pytest


@pytest.mark.integration
async def test_get_settings_returns_seeded(async_client, authenticated_super_admin_headers):
    resp = await async_client.get(
        "/api/v1/admin/professional-services/settings",
        headers=authenticated_super_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_hourly_rate_low"] == "200.00"
    assert body["default_hourly_rate_high"] == "200.00"
    assert body["webhook_url"] is None


@pytest.mark.integration
async def test_put_settings_updates(async_client, authenticated_super_admin_headers):
    resp = await async_client.put(
        "/api/v1/admin/professional-services/settings",
        headers=authenticated_super_admin_headers,
        json={
            "default_hourly_rate_low": "180.00",
            "default_hourly_rate_high": "220.00",
            "webhook_url": "https://example.com/hook",
            "webhook_secret": "shh",
        },
    )
    assert resp.status_code == 200


@pytest.mark.integration
async def test_org_admin_cannot_read_settings(async_client, authenticated_org_admin_headers):
    resp = await async_client.get(
        "/api/v1/admin/professional-services/settings",
        headers=authenticated_org_admin_headers,
    )
    assert resp.status_code == 403


@pytest.mark.integration
async def test_test_webhook_requires_url_configured(
    async_client, authenticated_super_admin_headers, settings_with_no_webhook
):
    resp = await async_client.post(
        "/api/v1/admin/professional-services/settings/test-webhook",
        headers=authenticated_super_admin_headers,
    )
    assert resp.status_code == 422  # url not configured
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the admin endpoints**

```python
# src/backend/base/langflow/api/v1/admin/professional_services_settings.py
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from langflow.api.utils import require_super_admin
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.professional_services.settings_service import (
    read_settings_singleton,
)

router = APIRouter(prefix="/professional-services", tags=["Admin: Professional Services"])


class SettingsRead(BaseModel):
    default_hourly_rate_low: Decimal | None
    default_hourly_rate_high: Decimal | None
    webhook_url: str | None
    has_webhook_secret: bool


class SettingsWrite(BaseModel):
    default_hourly_rate_low: Decimal | None = None
    default_hourly_rate_high: Decimal | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None  # write-only; never returned


@router.get("/settings", response_model=SettingsRead)
async def get_settings(
    user=Depends(require_super_admin),
    db_service=Depends(get_db_service),
):
    async with db_service.with_session() as session:
        s = read_settings_singleton(session)
    return SettingsRead(
        default_hourly_rate_low=s.default_hourly_rate_low,
        default_hourly_rate_high=s.default_hourly_rate_high,
        webhook_url=s.webhook_url,
        has_webhook_secret=bool(s.webhook_secret_encrypted),
    )


@router.put("/settings", response_model=SettingsRead)
async def put_settings(
    payload: SettingsWrite,
    user=Depends(require_super_admin),
    db_service=Depends(get_db_service),
    settings_service=Depends(get_settings_service),
):
    async with db_service.with_session() as session:
        s = read_settings_singleton(session)
        if payload.default_hourly_rate_low is not None:
            s.default_hourly_rate_low = payload.default_hourly_rate_low
        if payload.default_hourly_rate_high is not None:
            s.default_hourly_rate_high = payload.default_hourly_rate_high
        if payload.webhook_url is not None:
            s.webhook_url = payload.webhook_url or None
        if payload.webhook_secret:
            s.webhook_secret_encrypted = settings_service.encrypt(payload.webhook_secret)
        s.updated_by_user_id = user.id
        session.add(s)
        await session.commit()
        await session.refresh(s)
    return SettingsRead(
        default_hourly_rate_low=s.default_hourly_rate_low,
        default_hourly_rate_high=s.default_hourly_rate_high,
        webhook_url=s.webhook_url,
        has_webhook_secret=bool(s.webhook_secret_encrypted),
    )


@router.post("/settings/test-webhook")
async def test_webhook(
    user=Depends(require_super_admin),
    db_service=Depends(get_db_service),
    settings_service=Depends(get_settings_service),
):
    async with db_service.with_session() as session:
        s = read_settings_singleton(session)
        if not s.webhook_url or not s.webhook_secret_encrypted:
            raise HTTPException(status_code=422, detail="webhook_not_configured")
        secret = settings_service.decrypt(s.webhook_secret_encrypted)

    from langflow.worker_app.webhook import deliver_webhook  # synchronous test ping
    delivery = deliver_webhook(
        url=s.webhook_url,
        body={"event": "pro_service_quote.test_ping"},
        secret=secret,
        event="pro_service_quote.test_ping",
        synchronous=True,
    )
    return {"status": "ok" if delivery.success else "failed", "detail": delivery.detail}
```

(Adapt `deliver_webhook` invocation to actual signature — read `worker_app/webhook.py`.)

- [ ] **Step 4: Register the admin router**

In `src/backend/base/langflow/api/v1/admin/__init__.py`:

```python
from langflow.api.v1.admin.professional_services_settings import (
    router as professional_services_router,
)
admin_router.include_router(professional_services_router)
```

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/admin/professional_services_settings.py \
        src/backend/base/langflow/api/v1/admin/__init__.py \
        src/backend/tests/integration/api/admin/test_professional_services_settings.py
git commit -m "feat(pro-services): admin settings + test-webhook endpoints"
```

---

## Phase D: Assistant Integration

### Task 16: Register `suggest_professional_services` tool

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/pro_services.py`
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py` — register tool
- Modify: `src/backend/base/langflow/services/assistant/service.py` — extend SYSTEM_PROMPT_TEMPLATE
- Test: `src/backend/tests/unit/services/assistant/tools/test_pro_services_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/assistant/tools/test_pro_services_tool.py
from langflow.services.assistant.tools.pro_services import (
    SUGGEST_PROFESSIONAL_SERVICES_TOOL,
    handle_suggest_professional_services,
)
from langflow.services.assistant.tools.registry import all_tools


def test_tool_is_registered():
    names = {t.name for t in all_tools()}
    assert "suggest_professional_services" in names


def test_tool_schema_has_reason_field():
    schema = SUGGEST_PROFESSIONAL_SERVICES_TOOL.input_schema
    assert "reason" in schema["properties"]
    assert schema["required"] == ["reason"]


async def test_handler_emits_ps_suggestion_event():
    events = []
    class FakeEmitter:
        async def emit(self, event_type, payload):
            events.append((event_type, payload))
    await handle_suggest_professional_services(
        {"reason": "user has been stuck on OAuth for 15 minutes"},
        emitter=FakeEmitter(),
    )
    assert events == [
        ("ps_suggestion", {"reason": "user has been stuck on OAuth for 15 minutes"}),
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the tool**

```python
# src/backend/base/langflow/services/assistant/tools/pro_services.py
from __future__ import annotations

from typing import Any, Protocol

from langflow.services.assistant.tools.base import AssistantTool


class _Emitter(Protocol):
    async def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...


SUGGEST_PROFESSIONAL_SERVICES_TOOL = AssistantTool(
    name="suggest_professional_services",
    description=(
        "Surface a Professional Services suggestion card to the user. "
        "Use when the user explicitly asks for human help, says they're stuck, "
        "or hits the same error twice. Provide a one-sentence reason."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "One-sentence reason for surfacing the suggestion.",
                "maxLength": 240,
            },
        },
        "required": ["reason"],
    },
)


async def handle_suggest_professional_services(
    args: dict[str, Any], *, emitter: _Emitter
) -> dict[str, Any]:
    """Emit a ps_suggestion SSE event; return tool-result for the LLM loop."""
    reason = args["reason"]
    await emitter.emit("ps_suggestion", {"reason": reason})
    return {"status": "shown", "reason": reason}
```

- [ ] **Step 4: Register the tool in the registry**

In `src/backend/base/langflow/services/assistant/tools/registry.py`, add to the appropriate tool list (likely `INSPECTION_TOOLS` since it doesn't mutate the flow):

```python
from langflow.services.assistant.tools.pro_services import (
    SUGGEST_PROFESSIONAL_SERVICES_TOOL,
    handle_suggest_professional_services,
)

# Append to INSPECTION_TOOLS
INSPECTION_TOOLS.append(SUGGEST_PROFESSIONAL_SERVICES_TOOL)

TOOL_HANDLERS["suggest_professional_services"] = handle_suggest_professional_services
```

(Adapt to whatever the actual registry pattern is — read the file first.)

- [ ] **Step 5: Update SYSTEM_PROMPT_TEMPLATE**

In `src/backend/base/langflow/services/assistant/service.py`, append to the system prompt:

```
PROFESSIONAL SERVICES ESCALATION:
If the user explicitly asks for human help, says they're stuck, or hits the
same error twice, call the `suggest_professional_services` tool with a
one-sentence reason. Ask at most two clarifying questions before suggesting;
do not try to solve the problem yourself once professional help is on the
table. The goal is to get a quote out the door, not to keep iterating.
```

- [ ] **Step 6: Run the test to verify it passes**

- [ ] **Step 7: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/services/assistant/tools/pro_services.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/services/assistant/tools/test_pro_services_tool.py
git commit -m "feat(pro-services): assistant tool + system-prompt guideline"
```

---

## Phase E: Frontend In-Flow Surfaces

### Task 17: API hooks (preview, submit)

**Files:**
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/use-preview.ts`
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/use-submit.ts`
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/types.ts`

- [ ] **Step 1: Write the type module**

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/types.ts
export type ProServiceQuoteStatus = "open" | "in_progress" | "closed";

export type ComponentBreakdownItem = {
  type: string;
  minutes_low: number;
  minutes_high: number;
};

export type PreviewResponse = {
  minutes_low: number;
  minutes_high: number;
  rate_low_per_hour: string | null;  // Decimal serialized
  rate_high_per_hour: string | null;
  cost_low: string | null;
  cost_high: string | null;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  component_breakdown: ComponentBreakdownItem[];
};

export type QuoteSubmitRequest = {
  minutes_low: number;
  minutes_high: number;
  rate_low_per_hour: string | null;
  rate_high_per_hour: string | null;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  org_notes: string | null;
};

export type QuoteRead = {
  id: string;
  org_id: string;
  org_name: string;
  flow_id: string | null;
  flow_name: string | null;
  requester_user_id: string;
  requester_email: string | null;
  status: ProServiceQuoteStatus;
  assigned_admin_user_id: string | null;
  estimated_minutes_low: number;
  estimated_minutes_high: number;
  rate_low_per_hour: string | null;
  rate_high_per_hour: string | null;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  org_notes: string | null;
  admin_notes: string | null;
  created_at: string;
  submitted_at: string;
  in_progress_at: string | null;
  closed_at: string | null;
  closed_by_user_id: string | null;
};
```

- [ ] **Step 2: Implement the preview hook**

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/use-preview.ts
import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { PreviewResponse } from "./types";

export function usePreviewQuote(flowId: string) {
  return useMutation<PreviewResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await api.post<PreviewResponse>(
        `/api/v1/flows/${flowId}/pro-service-quotes/preview`,
      );
      return data;
    },
  });
}
```

- [ ] **Step 3: Implement the submit hook**

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/use-submit.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { QuoteRead, QuoteSubmitRequest } from "./types";

export function useSubmitQuote(flowId: string) {
  const qc = useQueryClient();
  return useMutation<QuoteRead, Error, QuoteSubmitRequest>({
    mutationFn: async (payload) => {
      const { data } = await api.post<QuoteRead>(
        `/api/v1/flows/${flowId}/pro-service-quotes`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pro-service-quotes"] });
    },
  });
}
```

- [ ] **Step 4: Pause and ask permission to commit**

```bash
git add src/frontend/src/controllers/API/queries/pro-service-quotes/
git commit -m "feat(pro-services): frontend API hooks for preview/submit"
```

---

### Task 18: PreviewProposalModal component

**Files:**
- Create: `src/frontend/src/components/core/proServiceQuotes/PreviewProposalModal/index.tsx`
- Create: `src/frontend/src/components/core/proServiceQuotes/PreviewProposalModal/__tests__/index.test.tsx`
- Create: `src/frontend/src/utils/formatMoney.ts` (if no shared formatter exists — search first)

- [ ] **Step 1: Confirm/reuse money formatter**

Search the codebase: `grep -r "formatMoney\|formatUSD\|<\\\\\$0\\.01" src/frontend/src/utils/`. If a formatter exists, use it. Otherwise create:

```typescript
// src/frontend/src/utils/formatMoney.ts
export function formatUSD(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(n)) return "—";
  if (n > 0 && n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}
```

- [ ] **Step 2: Write the failing component test**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PreviewProposalModal/__tests__/index.test.tsx
import { render, screen } from "@testing-library/react";
import { PreviewProposalModal } from "../index";

const mockPreview = {
  minutes_low: 180, minutes_high: 720,
  rate_low_per_hour: "200.00", rate_high_per_hour: "200.00",
  cost_low: "600.00", cost_high: "2400.00",
  headline_summary: "Wire up Slack notifications",
  narrative: "User wants to push events.",
  conversation_summary: "User struggled with OAuth.",
  component_breakdown: [
    { type: "Webhook", minutes_low: 30, minutes_high: 90 },
  ],
};

describe("PreviewProposalModal", () => {
  it("renders hours and dollar ranges", () => {
    render(
      <PreviewProposalModal
        open
        flowId="flow-1"
        preview={mockPreview}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText(/180/)).toBeInTheDocument();
    expect(screen.getByText(/\$600\.00/)).toBeInTheDocument();
    expect(screen.getByText(/\$2400\.00/)).toBeInTheDocument();
  });

  it("hides dollar range when rates are null", () => {
    render(
      <PreviewProposalModal
        open flowId="flow-1"
        preview={{ ...mockPreview, rate_low_per_hour: null, rate_high_per_hour: null, cost_low: null, cost_high: null }}
        onClose={() => {}}
      />,
    );
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd src/frontend && npx jest PreviewProposalModal`

- [ ] **Step 4: Implement the modal**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PreviewProposalModal/index.tsx
import { useState } from "react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useSubmitQuote } from "@/controllers/API/queries/pro-service-quotes/use-submit";
import { formatUSD } from "@/utils/formatMoney";
import type { PreviewResponse } from "@/controllers/API/queries/pro-service-quotes/types";

type Props = {
  open: boolean;
  flowId: string;
  preview: PreviewResponse | null;
  onClose: () => void;
  onSuccess?: () => void;
};

export function PreviewProposalModal({ open, flowId, preview, onClose, onSuccess }: Props) {
  const [headline, setHeadline] = useState(preview?.headline_summary ?? "");
  const [narrative, setNarrative] = useState(preview?.narrative ?? "");
  const [conversationSummary, setConversationSummary] = useState(preview?.conversation_summary ?? "");
  const [orgNotes, setOrgNotes] = useState("");
  const submit = useSubmitQuote(flowId);

  if (!open || !preview) return null;

  const showDollars = preview.rate_low_per_hour !== null && preview.rate_high_per_hour !== null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <div className="space-y-4">
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
          This is an AI-generated ballpark estimate, not a commitment. The PS team will follow up with a formal scope.
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Estimated time</div>
            <div className="text-lg">{preview.minutes_low} – {preview.minutes_high} minutes</div>
          </div>
          {showDollars && (
            <div>
              <div className="text-sm text-muted-foreground">Estimated cost</div>
              <div className="text-lg">{formatUSD(preview.cost_low)} – {formatUSD(preview.cost_high)}</div>
            </div>
          )}
        </div>

        <details className="rounded border p-2 text-sm">
          <summary>Component breakdown</summary>
          <ul className="mt-2 space-y-1">
            {preview.component_breakdown.map((c, i) => (
              <li key={i}>{c.type}: {c.minutes_low}–{c.minutes_high} min</li>
            ))}
          </ul>
        </details>

        <label className="block">
          <div className="text-sm">Headline</div>
          <Input value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={240} />
        </label>

        <label className="block">
          <div className="text-sm">Narrative</div>
          <Textarea value={narrative} onChange={(e) => setNarrative(e.target.value)} rows={4} />
        </label>

        {preview.conversation_summary !== null && (
          <label className="block">
            <div className="text-sm">Conversation summary</div>
            <Textarea
              value={conversationSummary}
              onChange={(e) => setConversationSummary(e.target.value)}
              rows={3}
            />
          </label>
        )}

        <label className="block">
          <div className="text-sm">Notes for PS (optional)</div>
          <Textarea value={orgNotes} onChange={(e) => setOrgNotes(e.target.value)} rows={2} />
        </label>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            disabled={submit.isPending || !headline.trim() || !narrative.trim()}
            onClick={() =>
              submit.mutate(
                {
                  minutes_low: preview.minutes_low,
                  minutes_high: preview.minutes_high,
                  rate_low_per_hour: preview.rate_low_per_hour,
                  rate_high_per_hour: preview.rate_high_per_hour,
                  headline_summary: headline,
                  narrative,
                  conversation_summary: conversationSummary || null,
                  org_notes: orgNotes || null,
                },
                {
                  onSuccess: () => { onSuccess?.(); onClose(); },
                },
              )
            }
          >
            {submit.isPending ? "Submitting..." : "Submit Request"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/frontend/src/components/core/proServiceQuotes/PreviewProposalModal/ \
        src/frontend/src/utils/formatMoney.ts
git commit -m "feat(pro-services): preview/submit modal"
```

---

### Task 19: Header "Request PS" button

**Files:**
- Create: `src/frontend/src/components/core/proServiceQuotes/PSRequestButton/index.tsx`
- Modify: the fullscreen builder header (search for the existing header buttons file in `src/frontend/src/pages/FlowPage/components/` or the equivalent — locate by searching for the "Save" or "Run" buttons in the header)

- [ ] **Step 1: Write the failing test**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PSRequestButton/__tests__/index.test.tsx
import { render, screen } from "@testing-library/react";
import { PSRequestButton } from "../index";

describe("PSRequestButton", () => {
  it("disables when ps_request_active is true", () => {
    render(<PSRequestButton flowId="f1" canRequest psRequestActive />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
  it("hides when canRequest=false", () => {
    const { container } = render(<PSRequestButton flowId="f1" canRequest={false} psRequestActive={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Implement the button**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PSRequestButton/index.tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { ForwardedIconComponent } from "@/components/genericIconComponent";
import { usePreviewQuote } from "@/controllers/API/queries/pro-service-quotes/use-preview";
import { PreviewProposalModal } from "../PreviewProposalModal";

type Props = {
  flowId: string;
  canRequest: boolean;
  psRequestActive: boolean;
};

export function PSRequestButton({ flowId, canRequest, psRequestActive }: Props) {
  const [open, setOpen] = useState(false);
  const preview = usePreviewQuote(flowId);

  if (!canRequest) return null;

  const handleClick = async () => {
    await preview.mutateAsync();
    setOpen(true);
  };

  const button = (
    <Button
      variant="outline"
      size="sm"
      disabled={psRequestActive || preview.isPending}
      onClick={handleClick}
    >
      <ForwardedIconComponent name="HandCoins" />
      {preview.isPending ? "Estimating..." : "Request PS"}
    </Button>
  );

  return (
    <>
      {psRequestActive ? (
        <Tooltip content="You already have an open Pro-Service request for this flow.">
          <span>{button}</span>
        </Tooltip>
      ) : button}
      <PreviewProposalModal
        open={open}
        flowId={flowId}
        preview={preview.data ?? null}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
```

- [ ] **Step 4: Wire it into the fullscreen header**

Find the file that renders the existing header buttons (likely `src/frontend/src/pages/FlowPage/components/extraSidebarComponent/` or `flowMenuComponent`). Insert `<PSRequestButton flowId={flow.id} canRequest={isOwnerOrOrgAdmin} psRequestActive={flow.ps_request_active} />` near the existing "Save" / "Run" buttons.

The `flow.ps_request_active` field comes from the existing flow read response — it now includes the new column automatically. If the frontend's flow type definition is hand-maintained, add `ps_request_active: boolean` to it.

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/frontend/src/components/core/proServiceQuotes/PSRequestButton/ \
        # any modified header files
git commit -m "feat(pro-services): header Request PS button with active-flag gating"
```

---

### Task 20: Assistant suggestion card

**Files:**
- Create: `src/frontend/src/components/core/proServiceQuotes/PSSuggestionCard/index.tsx`
- Modify: the assistant SSE event handler (search for the existing event handler that processes events from the assistant SSE stream — likely in a file named like `useAssistantStream.ts` or similar)

- [ ] **Step 1: Find the assistant event handler**

Run: `grep -rn "tool_use\|tool_result\|EventSource\|SSE" src/frontend/src/components/ --include="*.ts" --include="*.tsx" | grep -i assist`

- [ ] **Step 2: Write the failing test**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PSSuggestionCard/__tests__/index.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { PSSuggestionCard } from "../index";

describe("PSSuggestionCard", () => {
  it("renders the reason and CTA", () => {
    const onRequest = jest.fn();
    render(<PSSuggestionCard reason="Stuck on OAuth for 15 min" onRequest={onRequest} onDismiss={() => {}} />);
    expect(screen.getByText(/Stuck on OAuth/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Request Professional Services/i }));
    expect(onRequest).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Implement the card**

```tsx
// src/frontend/src/components/core/proServiceQuotes/PSSuggestionCard/index.tsx
import { Button } from "@/components/ui/button";
import { ForwardedIconComponent } from "@/components/genericIconComponent";

type Props = {
  reason: string;
  onRequest: () => void;
  onDismiss: () => void;
};

export function PSSuggestionCard({ reason, onRequest, onDismiss }: Props) {
  return (
    <div className="rounded-lg border border-[#ED1C2E]/30 bg-[#ED1C2E]/5 p-4 my-2">
      <div className="flex items-start gap-3">
        <ForwardedIconComponent name="HandCoins" className="text-[#ED1C2E] mt-0.5" />
        <div className="flex-1">
          <div className="font-medium">Need a hand?</div>
          <div className="text-sm text-muted-foreground mt-1">{reason}</div>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={onRequest}>Request Professional Services</Button>
            <Button size="sm" variant="ghost" onClick={onDismiss}>Dismiss</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire `ps_suggestion` SSE event handler**

In the assistant stream consumer, add a case for `event.type === "ps_suggestion"`. Push the reason into a piece of state (e.g., `useAssistantStore` or component-local state) that the chat renderer reads to inject `<PSSuggestionCard />` into the message list. Clicking "Request" opens the same `<PreviewProposalModal />` as the header button (call `usePreviewQuote(flowId).mutateAsync()` then open).

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/frontend/src/components/core/proServiceQuotes/PSSuggestionCard/ \
        # the assistant stream handler file
git commit -m "feat(pro-services): assistant suggestion card driven by ps_suggestion event"
```

---

## Phase F: Frontend Home + Queue UI

### Task 21: Sidebar nav entry "Pro-Service Quotes"

**Files:**
- Modify: `src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx`

- [ ] **Step 1: Add the nav entry above Knowledge**

Locate the existing block:

```tsx
{ENABLE_KNOWLEDGE_BASES && (
  <SidebarMenuButton onClick={handleKnowledgeNavigation}>
    <ForwardedIconComponent name="Library" /> Knowledge
  </SidebarMenuButton>
)}
```

Insert immediately before it:

```tsx
<SidebarMenuButton onClick={() => navigate("/pro-service-quotes")}>
  <ForwardedIconComponent name="HandCoins" /> Pro-Service Quotes
</SidebarMenuButton>
```

(Use the existing `navigate` from `useNavigate` — it should already be imported in this file.)

- [ ] **Step 2: Verify visually**

Start the dev server: `cd src/frontend && npm run dev`. Open the home page. Confirm the new entry appears above "Knowledge".

- [ ] **Step 3: Pause and ask permission to commit**

```bash
git add src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx
git commit -m "feat(pro-services): sidebar nav entry above Knowledge"
```

---

### Task 22: Quotes list page

**Files:**
- Create: `src/frontend/src/pages/ProServiceQuotesPage/index.tsx`
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/use-list.ts`
- Modify: `src/frontend/src/routes.tsx` (or wherever routes are defined) — add `/pro-service-quotes`

- [ ] **Step 1: Implement the list hook**

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/use-list.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { QuoteRead, ProServiceQuoteStatus } from "./types";

type ListResponse = { items: QuoteRead[]; total: number };

export function useListQuotes(filters: {
  status?: ProServiceQuoteStatus;
  org_id?: string;
}) {
  return useQuery<ListResponse>({
    queryKey: ["pro-service-quotes", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.org_id) params.set("org_id", filters.org_id);
      const { data } = await api.get<ListResponse>(
        `/api/v1/pro-service-quotes?${params}`,
      );
      return data;
    },
  });
}
```

- [ ] **Step 2: Implement the page**

```tsx
// src/frontend/src/pages/ProServiceQuotesPage/index.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useListQuotes } from "@/controllers/API/queries/pro-service-quotes/use-list";
import { useAuthStore } from "@/stores/authStore"; // adapt to actual store path
import { formatUSD } from "@/utils/formatMoney";
import type { ProServiceQuoteStatus } from "@/controllers/API/queries/pro-service-quotes/types";

export function ProServiceQuotesPage() {
  const [statusFilter, setStatusFilter] = useState<ProServiceQuoteStatus | "all">("open");
  const user = useAuthStore((s) => s.user);
  const isAdmin = !!(user?.is_super_admin || user?.is_platform_admin);
  const navigate = useNavigate();

  const { data, isPending } = useListQuotes({
    status: statusFilter === "all" ? undefined : statusFilter,
  });

  if (isPending) return <div className="p-6">Loading…</div>;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Pro-Service Quotes</h1>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ProServiceQuoteStatus | "all")}
          className="border rounded px-2 py-1"
        >
          <option value="all">All</option>
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b">
            {isAdmin && <th className="py-2">Org</th>}
            {!isAdmin && <th className="py-2">Flow</th>}
            <th>Price range</th>
            <th>Headline</th>
            <th>Status</th>
            <th>Submitted</th>
            <th>Open flow</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((q) => {
            const lo = q.rate_low_per_hour ? (q.estimated_minutes_low * parseFloat(q.rate_low_per_hour) / 60) : null;
            const hi = q.rate_high_per_hour ? (q.estimated_minutes_high * parseFloat(q.rate_high_per_hour) / 60) : null;
            return (
              <tr
                key={q.id}
                className="border-b cursor-pointer hover:bg-accent"
                onClick={() => navigate(`/pro-service-quotes/${q.id}`)}
              >
                {isAdmin && <td className="py-2">{q.org_name}</td>}
                {!isAdmin && <td className="py-2">{q.flow_name ?? "—"}</td>}
                <td>{formatUSD(lo)} – {formatUSD(hi)}</td>
                <td className="max-w-md truncate">{q.headline_summary}</td>
                <td>{q.status}</td>
                <td>{new Date(q.submitted_at).toLocaleDateString()}</td>
                <td>{q.flow_id ? <a onClick={(e) => { e.stopPropagation(); navigate(`/flow/${q.flow_id}`); }}>Open</a> : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

(For the admin view's `org_name` column, add a small org-name resolver — either embed `org` in the API response or hit a `/api/v1/organizations/{id}` lookup. Pick whichever pattern the codebase already uses for similar admin tables. The TODO marker above means: replace with actual org name before considering the task complete.)

- [ ] **Step 3: Wire the route**

In the routes file, add:

```tsx
import { ProServiceQuotesPage } from "@/pages/ProServiceQuotesPage";
// ...
<Route path="/pro-service-quotes" element={<ProServiceQuotesPage />} />
```

- [ ] **Step 4: Pause and ask permission to commit**

```bash
git add src/frontend/src/pages/ProServiceQuotesPage/ \
        src/frontend/src/controllers/API/queries/pro-service-quotes/use-list.ts \
        # routes file
git commit -m "feat(pro-services): quotes list page with role-conditional columns"
```

---

### Task 23: Quote detail page

**Files:**
- Create: `src/frontend/src/pages/ProServiceQuoteDetailPage/index.tsx`
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/use-detail.ts`
- Create: `src/frontend/src/controllers/API/queries/pro-service-quotes/use-update.ts`
- Modify: routes file — add `/pro-service-quotes/:id`

- [ ] **Step 1: Implement the detail and update hooks**

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/use-detail.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { QuoteRead } from "./types";

export function useQuoteDetail(id: string) {
  return useQuery<QuoteRead>({
    queryKey: ["pro-service-quotes", id],
    queryFn: async () => (await api.get<QuoteRead>(`/api/v1/pro-service-quotes/${id}`)).data,
  });
}
```

```typescript
// src/frontend/src/controllers/API/queries/pro-service-quotes/use-update.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { ProServiceQuoteStatus, QuoteRead } from "./types";

type UpdatePayload = {
  org_notes?: string;
  admin_notes?: string;
  status?: ProServiceQuoteStatus;
  assigned_admin_user_id?: string;
};

export function useUpdateQuote(id: string) {
  const qc = useQueryClient();
  return useMutation<QuoteRead, Error, UpdatePayload>({
    mutationFn: async (payload) =>
      (await api.patch<QuoteRead>(`/api/v1/pro-service-quotes/${id}`, payload)).data,
    onSuccess: (data) => {
      qc.setQueryData(["pro-service-quotes", id], data);
      qc.invalidateQueries({ queryKey: ["pro-service-quotes"], exact: false });
    },
  });
}
```

- [ ] **Step 2: Implement the detail page**

```tsx
// src/frontend/src/pages/ProServiceQuoteDetailPage/index.tsx
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useQuoteDetail } from "@/controllers/API/queries/pro-service-quotes/use-detail";
import { useUpdateQuote } from "@/controllers/API/queries/pro-service-quotes/use-update";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { formatUSD } from "@/utils/formatMoney";

export function ProServiceQuoteDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isAdmin = !!(user?.is_super_admin || user?.is_platform_admin);

  const { data: quote, isPending } = useQuoteDetail(id);
  const update = useUpdateQuote(id);
  const [orgNotes, setOrgNotes] = useState("");
  const [adminNotes, setAdminNotes] = useState("");

  useEffect(() => {
    if (quote) {
      setOrgNotes(quote.org_notes ?? "");
      setAdminNotes(quote.admin_notes ?? "");
    }
  }, [quote]);

  if (isPending || !quote) return <div className="p-6">Loading…</div>;

  const isRequester = user?.id === quote.requester_user_id;
  const canMarkInProgress = isAdmin && quote.status === "open";
  const canClose =
    (isAdmin && quote.status !== "closed") ||
    (isRequester && quote.status === "open");

  const lo = quote.rate_low_per_hour ? (quote.estimated_minutes_low * parseFloat(quote.rate_low_per_hour) / 60) : null;
  const hi = quote.rate_high_per_hour ? (quote.estimated_minutes_high * parseFloat(quote.rate_high_per_hour) / 60) : null;

  return (
    <div className="p-6 max-w-5xl mx-auto grid grid-cols-3 gap-6">
      <div className="col-span-2 space-y-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl">{quote.headline_summary}</h1>
          <span className="px-2 py-0.5 text-xs rounded bg-secondary">{quote.status}</span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Estimated time</div>
            <div>{quote.estimated_minutes_low}–{quote.estimated_minutes_high} min</div>
          </div>
          {lo !== null && hi !== null && (
            <div>
              <div className="text-sm text-muted-foreground">Estimated cost</div>
              <div>{formatUSD(lo)} – {formatUSD(hi)}</div>
            </div>
          )}
        </div>
        <div>
          <div className="text-sm text-muted-foreground">Narrative</div>
          <div className="whitespace-pre-wrap">{quote.narrative}</div>
        </div>
        {quote.conversation_summary && (
          <div>
            <div className="text-sm text-muted-foreground">Conversation summary</div>
            <div className="whitespace-pre-wrap">{quote.conversation_summary}</div>
          </div>
        )}
        {quote.flow_id && (
          <Button variant="outline" onClick={() => navigate(`/flow/${quote.flow_id}`)}>Open flow</Button>
        )}
      </div>

      <div className="space-y-4">
        <label className="block">
          <div className="text-sm">Org notes</div>
          <Textarea value={orgNotes} onChange={(e) => setOrgNotes(e.target.value)} rows={3} />
          <Button
            size="sm"
            className="mt-2"
            disabled={update.isPending}
            onClick={() => update.mutate({ org_notes: orgNotes })}
          >Save</Button>
        </label>

        {isAdmin && (
          <label className="block">
            <div className="text-sm">Admin notes</div>
            <Textarea value={adminNotes} onChange={(e) => setAdminNotes(e.target.value)} rows={3} />
            <Button
              size="sm"
              className="mt-2"
              disabled={update.isPending}
              onClick={() => update.mutate({ admin_notes: adminNotes })}
            >Save</Button>
          </label>
        )}

        <div className="border-t pt-3 space-y-2">
          {canMarkInProgress && (
            <Button
              className="w-full"
              disabled={update.isPending}
              onClick={() => update.mutate({ status: "in_progress" })}
            >Mark in progress</Button>
          )}
          {canClose && (
            <Button
              variant={isRequester ? "outline" : "default"}
              className="w-full"
              disabled={update.isPending}
              onClick={() => update.mutate({ status: "closed" })}
            >{isRequester ? "Cancel my request" : "Close"}</Button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire the route**

```tsx
<Route path="/pro-service-quotes/:id" element={<ProServiceQuoteDetailPage />} />
```

- [ ] **Step 4: Pause and ask permission to commit**

```bash
git add src/frontend/src/pages/ProServiceQuoteDetailPage/ \
        src/frontend/src/controllers/API/queries/pro-service-quotes/use-detail.ts \
        src/frontend/src/controllers/API/queries/pro-service-quotes/use-update.ts \
        # routes file
git commit -m "feat(pro-services): quote detail page with notes panels + transitions"
```

---

### Task 24: Super-admin Settings tab "Professional Services"

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/Tabs/ProfessionalServicesTab/index.tsx`
- Create: `src/frontend/src/controllers/API/queries/admin/professional-services/use-settings.ts`
- Modify: settings page tab registry to include the new tab (search for the existing tab config)

- [ ] **Step 1: Implement the settings hooks**

```typescript
// src/frontend/src/controllers/API/queries/admin/professional-services/use-settings.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";

type SettingsRead = {
  default_hourly_rate_low: string | null;
  default_hourly_rate_high: string | null;
  webhook_url: string | null;
  has_webhook_secret: boolean;
};

type SettingsWrite = Partial<{
  default_hourly_rate_low: string;
  default_hourly_rate_high: string;
  webhook_url: string;
  webhook_secret: string;
}>;

export function useProServiceSettings() {
  return useQuery<SettingsRead>({
    queryKey: ["admin", "professional-services", "settings"],
    queryFn: async () => (await api.get<SettingsRead>("/api/v1/admin/professional-services/settings")).data,
  });
}

export function useUpdateProServiceSettings() {
  const qc = useQueryClient();
  return useMutation<SettingsRead, Error, SettingsWrite>({
    mutationFn: async (payload) =>
      (await api.put<SettingsRead>("/api/v1/admin/professional-services/settings", payload)).data,
    onSuccess: (data) => {
      qc.setQueryData(["admin", "professional-services", "settings"], data);
    },
  });
}

export function useTestWebhook() {
  return useMutation<{ status: string; detail?: string }, Error, void>({
    mutationFn: async () =>
      (await api.post("/api/v1/admin/professional-services/settings/test-webhook")).data,
  });
}
```

- [ ] **Step 2: Implement the tab**

```tsx
// src/frontend/src/pages/SettingsPage/Tabs/ProfessionalServicesTab/index.tsx
import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  useProServiceSettings,
  useUpdateProServiceSettings,
  useTestWebhook,
} from "@/controllers/API/queries/admin/professional-services/use-settings";

export function ProfessionalServicesTab() {
  const { data, isPending } = useProServiceSettings();
  const update = useUpdateProServiceSettings();
  const test = useTestWebhook();

  const [rateLow, setRateLow] = useState("");
  const [rateHigh, setRateHigh] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [secret, setSecret] = useState("");

  useEffect(() => {
    if (data) {
      setRateLow(data.default_hourly_rate_low ?? "");
      setRateHigh(data.default_hourly_rate_high ?? "");
      setWebhookUrl(data.webhook_url ?? "");
    }
  }, [data]);

  if (isPending) return <div>Loading…</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Professional Services</h2>

      <div className="grid grid-cols-2 gap-4 max-w-lg">
        <label>
          <div className="text-sm">Default rate low ($/hour)</div>
          <Input value={rateLow} onChange={(e) => setRateLow(e.target.value)} />
        </label>
        <label>
          <div className="text-sm">Default rate high ($/hour)</div>
          <Input value={rateHigh} onChange={(e) => setRateHigh(e.target.value)} />
        </label>
      </div>

      <label className="block max-w-lg">
        <div className="text-sm">Webhook URL (optional)</div>
        <Input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://example.com/intake" />
      </label>

      <label className="block max-w-lg">
        <div className="text-sm">Webhook secret {data?.has_webhook_secret ? "(set; leave blank to keep current)" : ""}</div>
        <Input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="••••••"
        />
      </label>

      <div className="flex gap-2">
        <Button
          disabled={update.isPending}
          onClick={() =>
            update.mutate({
              default_hourly_rate_low: rateLow,
              default_hourly_rate_high: rateHigh,
              webhook_url: webhookUrl,
              webhook_secret: secret || undefined,
            })
          }
        >Save</Button>
        <Button
          variant="outline"
          disabled={!data?.webhook_url || !data?.has_webhook_secret || test.isPending}
          onClick={() => test.mutate()}
        >Test webhook</Button>
        {test.data && (
          <span className={test.data.status === "ok" ? "text-green-600" : "text-red-600"}>
            {test.data.status}
            {test.data.detail ? `: ${test.data.detail}` : ""}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Register the tab**

In the settings page tab registry (search for where existing tabs like "API Keys" are registered), add:

```tsx
{ id: "professional-services", label: "Professional Services", component: ProfessionalServicesTab, requireRole: "super_admin" }
```

- [ ] **Step 4: Pause and ask permission to commit**

```bash
git add src/frontend/src/pages/SettingsPage/Tabs/ProfessionalServicesTab/ \
        src/frontend/src/controllers/API/queries/admin/professional-services/ \
        # tab registry file
git commit -m "feat(pro-services): super-admin Settings tab"
```

---

## Phase G: Bell Extension

### Task 25: Extend bell endpoint to read targeted rows + role-aware audience

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/notifications.py` (or wherever `GET /v1/admin/notifications` lives — locate via grep)
- Modify: `src/frontend/src/components/core/adminNotificationBell/index.tsx` — handle the new category copy + click navigation
- Test: `src/backend/tests/integration/api/admin/test_notifications_bell_extended.py`

- [ ] **Step 1: Locate the existing bell endpoint**

Run: `grep -rn "/admin/notifications" src/backend/base/langflow/api/`

- [ ] **Step 2: Write the failing test**

```python
# src/backend/tests/integration/api/admin/test_notifications_bell_extended.py
import pytest


@pytest.mark.integration
async def test_super_admin_sees_super_admin_audience_rows(
    async_client, authenticated_super_admin_headers, seeded_super_admin_notification
):
    resp = await async_client.get("/api/v1/admin/notifications", headers=authenticated_super_admin_headers)
    ids = {n["id"] for n in resp.json()["items"]}
    assert str(seeded_super_admin_notification.id) in ids


@pytest.mark.integration
async def test_platform_admin_sees_platform_admin_audience_rows(
    async_client, authenticated_platform_admin_headers, seeded_platform_admin_notification
):
    resp = await async_client.get("/api/v1/admin/notifications", headers=authenticated_platform_admin_headers)
    ids = {n["id"] for n in resp.json()["items"]}
    assert str(seeded_platform_admin_notification.id) in ids


@pytest.mark.integration
async def test_user_sees_targeted_rows(
    async_client, authenticated_org_member_headers, seeded_targeted_notification_for_user
):
    resp = await async_client.get("/api/v1/admin/notifications", headers=authenticated_org_member_headers)
    ids = {n["id"] for n in resp.json()["items"]}
    assert str(seeded_targeted_notification_for_user.id) in ids


@pytest.mark.integration
async def test_user_does_not_see_other_users_targeted_rows(
    async_client, authenticated_org_member_headers, seeded_targeted_notification_for_other_user
):
    resp = await async_client.get("/api/v1/admin/notifications", headers=authenticated_org_member_headers)
    ids = {n["id"] for n in resp.json()["items"]}
    assert str(seeded_targeted_notification_for_other_user.id) not in ids
```

- [ ] **Step 3: Extend the bell endpoint query**

Find the existing handler (let's call it `list_notifications`). Replace its query construction with:

```python
from sqlalchemy import or_

from langflow.services.database.models.admin_notification.model import (
    AdminNotification, NotificationAudience,
)


async def list_notifications(user=Depends(get_current_user), db_service=Depends(get_db_service)):
    visible_audiences = []
    if user.is_super_admin:
        visible_audiences.append(NotificationAudience.SUPER_ADMIN)
    if user.is_platform_admin:
        visible_audiences.append(NotificationAudience.PLATFORM_ADMIN)

    async with db_service.with_session() as session:
        clauses = [AdminNotification.audience_user_id == user.id]
        if visible_audiences:
            clauses.append(
                AdminNotification.audience.in_(visible_audiences)
                & (AdminNotification.audience_user_id.is_(None))
            )
        rows = session.exec(
            select(AdminNotification).where(or_(*clauses)).order_by(AdminNotification.created_at.desc())
        ).all()
    return {"items": rows}
```

(Adapt to the actual handler signature — keep the existing pagination, unread-only filter, etc.)

- [ ] **Step 4: Update bell rendering on the frontend**

In `src/frontend/src/components/core/adminNotificationBell/index.tsx`, add a copy template + click handler for the new category:

```tsx
function renderNotification(n: NotificationRead, navigate: (path: string) => void) {
  if (n.category === "professional_services_request") {
    return {
      title: n.title,
      body: n.body_md,
      onClick: () => {
        const quoteId = n.metadata_json?.quote_id;
        if (quoteId) navigate(`/pro-service-quotes/${quoteId}`);
      },
    };
  }
  // ...existing categories
}
```

If the existing component doesn't dispatch by category, refactor the click target to use a `metadata_json.quote_id` deep link.

- [ ] **Step 5: Run the test to verify it passes**

- [ ] **Step 6: Pause and ask permission to commit**

```bash
git add src/backend/base/langflow/api/v1/admin/notifications.py \
        src/frontend/src/components/core/adminNotificationBell/index.tsx \
        src/backend/tests/integration/api/admin/test_notifications_bell_extended.py
git commit -m "feat(pro-services): bell endpoint reads targeted rows + new category copy"
```

---

## Phase H: End-to-End Smoke

### Task 26: End-to-end smoke test

**Files:**
- Create: `src/backend/tests/e2e/test_pro_service_quotes_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
# src/backend/tests/e2e/test_pro_service_quotes_smoke.py
import pytest


@pytest.mark.e2e
async def test_full_lifecycle(async_client, authenticated_org_owner_headers,
                               authenticated_super_admin_headers, seeded_flow):
    # 1. Preview
    pv = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes/preview",
        headers=authenticated_org_owner_headers,
    )
    assert pv.status_code == 200

    # 2. Submit
    body = pv.json()
    submit = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes",
        headers=authenticated_org_owner_headers,
        json={
            "minutes_low": body["minutes_low"], "minutes_high": body["minutes_high"],
            "rate_low_per_hour": body["rate_low_per_hour"], "rate_high_per_hour": body["rate_high_per_hour"],
            "headline_summary": body["headline_summary"], "narrative": body["narrative"],
            "conversation_summary": body["conversation_summary"], "org_notes": None,
        },
    )
    assert submit.status_code == 201
    quote_id = submit.json()["id"]

    # 3. Submit again on same flow → 409
    pv2 = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes/preview",
        headers=authenticated_org_owner_headers,
    )
    assert pv2.status_code == 409

    # 4. Admin lists, sees the quote
    listed = await async_client.get(
        "/api/v1/pro-service-quotes",
        headers=authenticated_super_admin_headers,
    )
    assert quote_id in {q["id"] for q in listed.json()["items"]}

    # 5. Admin marks in_progress
    p1 = await async_client.patch(
        f"/api/v1/pro-service-quotes/{quote_id}",
        headers=authenticated_super_admin_headers,
        json={"status": "in_progress"},
    )
    assert p1.status_code == 200

    # 6. Admin closes
    p2 = await async_client.patch(
        f"/api/v1/pro-service-quotes/{quote_id}",
        headers=authenticated_super_admin_headers,
        json={"status": "closed", "admin_notes": "Engagement complete."},
    )
    assert p2.status_code == 200

    # 7. ps_request_active is now false → can submit again
    pv3 = await async_client.post(
        f"/api/v1/flows/{seeded_flow.id}/pro-service-quotes/preview",
        headers=authenticated_org_owner_headers,
    )
    assert pv3.status_code == 200
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest src/backend/tests/e2e/test_pro_service_quotes_smoke.py -v`
Expected: PASS.

- [ ] **Step 3: Pause and ask permission to commit**

```bash
git add src/backend/tests/e2e/test_pro_service_quotes_smoke.py
git commit -m "test(pro-services): end-to-end lifecycle smoke"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ All 7 phases from spec Section 6 mapped to tasks (Phase A=Tasks 1-4, B=5-8, C=9-15, D=16, E=17-20, F=21-24, G=25, plus E2E smoke)
- ✅ All schema columns from spec Section 1 created (Task 1, 2, 3, 4)
- ✅ All endpoints from spec Section 2 implemented (Task 10, 11, 13, 14, 15)
- ✅ Preview pipeline matches spec Section 3 (Task 6, 7, 10)
- ✅ Submit + transitions match spec Section 4 (Task 11, 14)
- ✅ Frontend surfaces match spec Section 5 (Tasks 17-24)

**Out-of-scope items NOT in plan (per spec Section 7):**
- Templates-popup entry tile (deferred)
- Counter-quote workflow (none)
- Comments thread (none)
- Email/Slack notifications (none)
- Per-component metadata editing UI (none)

**Known fragile spots flagged in tasks:**
- Task 10: `_load_assistant_history` returns None as v1 stub — wire later when assistant message persistence is settled (LLM prompt handles the no-history case explicitly)
- Task 12: `deliver_webhook` call signature should be verified against `worker_app/webhook.py` before implementation — read the actual function first
- Task 25: bell handler signature must match the existing endpoint's pattern — locate via `grep -rn "/admin/notifications" src/backend/base/langflow/api/` before editing

These are intentional v1 cuts and integration points; the plan calls them out so the executing agent verifies before guessing.
