# Metadata Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit discipline:** The project owner has an explicit "no git commits without permission" rule. Every task ends with a **"Pause for commit"** step. Stop. Show the diff. Ask for approval. Only commit if the user says yes, and use the proposed message only if they don't suggest a different one.

**Goal:** Deliver a shared metadata layer (two tables: `template_metadata`, `component_metadata`) plus a super-admin UI ("Flow and Component Management") and assistant-side integration so the ADP Assist LLM sees admin-authored guidance when reasoning about templates and components.

**Architecture:**
Two SQLModel tables share a `AgentMetadataMixin` (`agent_usage_notes`, `agent_summary`, `updated_by`, `updated_at`). A single admin API prefix (`/api/v1/admin/metadata/*`) serves both, gated by `get_current_active_superuser`. Template metadata reaches the LLM through system-prompt summary injection + a new `get_template_instructions` tool; component metadata reaches the LLM by inline-merging into the existing `search_components` and `get_component_schema` catalog tools. A new admin page at `/settings/metadata` with two tabs exposes list + edit surfaces.

**Tech Stack:** Python 3.11+, SQLModel, Alembic, FastAPI, Pydantic v2, pytest + pytest-asyncio, React 18, @tanstack/react-query, shadcn/ui (Radix), Jest + @testing-library/react.

---

## Spec reference

The authoritative design is `docs/superpowers/specs/2026-04-18-metadata-infrastructure-design.md`. This plan realizes that spec. Two minor corrections from spec research:

1. The spec refers to "Vitest" for frontend tests; the project actually uses **Jest** + `@testing-library/react`. This plan uses Jest.
2. The spec says "filter at the API layer on `flow.is_starter`". There is no `is_starter` column on `Flow`; starter projects are identified via the starter folder. This plan uses a helper `is_flow_a_starter_project(flow, session)` that checks folder membership. Functional behavior is identical.

---

## File Structure

### New files — backend

- `src/backend/base/langflow/services/database/models/_metadata/__init__.py`
- `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py`
- `src/backend/base/langflow/services/database/models/template_metadata/__init__.py`
- `src/backend/base/langflow/services/database/models/template_metadata/model.py`
- `src/backend/base/langflow/services/database/models/component_metadata/__init__.py`
- `src/backend/base/langflow/services/database/models/component_metadata/model.py`
- `src/backend/base/langflow/alembic/versions/<rev>_add_template_and_component_metadata.py`
- `src/backend/base/langflow/api/v1/admin/__init__.py`
- `src/backend/base/langflow/api/v1/admin/metadata.py`
- `src/backend/base/langflow/services/assistant/tools/template_metadata.py` (houses `get_template_instructions`)
- `src/backend/base/langflow/services/assistant/template_prompt.py` (houses the system-prompt-block builder)
- `src/backend/tests/unit/services/database/models/test_template_metadata_model.py`
- `src/backend/tests/unit/services/database/models/test_component_metadata_model.py`
- `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`
- `src/backend/tests/unit/api/v1/test_admin_component_metadata_api.py`
- `src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py`
- `src/backend/tests/unit/services/assistant/tools/test_get_template_instructions_tool.py`
- `src/backend/tests/unit/services/assistant/test_template_prompt_block.py`

### Modified files — backend

- `src/backend/base/langflow/services/database/models/__init__.py` — register new models
- `src/backend/base/langflow/api/v1/__init__.py` — register admin metadata router
- `src/backend/base/langflow/services/assistant/tools/catalog.py` — inline-merge metadata
- `src/backend/base/langflow/services/assistant/tools/registry.py` — register new tool
- `src/backend/base/langflow/services/assistant/service.py` — inject template-prompt block, extend system-prompt bullets
- `src/backend/base/langflow/services/assistant/mcp_server.py` — update tool-schema docstrings for the enriched tools

### New files — frontend

- `src/frontend/src/components/authorization/authSuperuserGuard/index.tsx`
- `src/frontend/src/controllers/API/queries/metadata/index.ts` (re-exports)
- `src/frontend/src/controllers/API/queries/metadata/use-template-metadata.ts`
- `src/frontend/src/controllers/API/queries/metadata/use-component-metadata.ts`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/components-tab.tsx`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/metadata-edit-form.tsx`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/orphan-badge.tsx`
- `src/frontend/src/types/metadata/index.ts`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/metadata-edit-form.test.tsx`
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/components-tab.test.tsx`

### Modified files — frontend

- `src/frontend/src/routes.tsx` — add `/settings/metadata` route
- `src/frontend/src/pages/SettingsPage/index.tsx` — add sidebar nav entry
- `src/frontend/src/controllers/API/helpers/constants.ts` — add `METADATA_*` base URLs

---

## Task 1: Shared metadata mixin

**Files:**
- Create: `src/backend/base/langflow/services/database/models/_metadata/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py`

- [ ] **Step 1.1: Create the `_metadata` package init**

Create `src/backend/base/langflow/services/database/models/_metadata/__init__.py`:

```python
"""Shared SQLModel mixins for metadata tables."""

from .metadata_mixin import AgentMetadataMixin

__all__ = ["AgentMetadataMixin"]
```

- [ ] **Step 1.2: Create the mixin**

Create `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py`:

```python
"""Shared columns for template_metadata and component_metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMetadataMixin(SQLModel):
    """Mixin providing the shared columns for agent-facing metadata rows."""

    agent_usage_notes: str | None = Field(default=None, sa_column=Column(Text))
    agent_summary: str | None = Field(default=None, sa_column=Column(Text))
    updated_by: UUID = Field(foreign_key="user.id")
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )
```

- [ ] **Step 1.3: Pause for commit**

Do not commit. Show the user the two new files and ask whether to commit. Proposed message: `feat(db): add AgentMetadataMixin for shared metadata columns`.

---

## Task 2: `TemplateMetadata` SQLModel table

**Files:**
- Create: `src/backend/base/langflow/services/database/models/template_metadata/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/template_metadata/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_template_metadata_model.py`

- [ ] **Step 2.1: Write the failing model test**

Create `src/backend/tests/unit/services/database/models/test_template_metadata_model.py`:

```python
"""Unit tests for TemplateMetadata SQLModel."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, Folder, TemplateMetadata, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def _make_user(session: Session) -> User:
    user = User(username="admin", password="x", is_superuser=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_flow(session: Session, user: User) -> Flow:
    flow = Flow(name="Onboarding", user_id=user.id, data={"nodes": [], "edges": []})
    session.add(flow)
    session.commit()
    session.refresh(flow)
    return flow


def test_template_metadata_row_can_be_created(session):
    user = _make_user(session)
    flow = _make_flow(session, user)

    meta = TemplateMetadata(
        flow_id=flow.id,
        agent_usage_notes="When to use this template.",
        agent_summary="Onboarding Slack notifier.",
        updated_by=user.id,
    )
    session.add(meta)
    session.commit()
    session.refresh(meta)

    assert meta.id is not None
    assert meta.flow_id == flow.id
    assert meta.agent_summary == "Onboarding Slack notifier."


def test_template_metadata_flow_id_is_unique(session):
    user = _make_user(session)
    flow = _make_flow(session, user)

    session.add(TemplateMetadata(flow_id=flow.id, updated_by=user.id))
    session.commit()

    duplicate = TemplateMetadata(flow_id=flow.id, updated_by=user.id)
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_metadata_cascade_deletes_with_flow(session):
    user = _make_user(session)
    flow = _make_flow(session, user)
    session.add(TemplateMetadata(flow_id=flow.id, updated_by=user.id))
    session.commit()

    session.delete(flow)
    session.commit()

    rows = session.exec(select(TemplateMetadata)).all()
    assert rows == []


def test_template_metadata_updated_at_autobumps(session):
    user = _make_user(session)
    flow = _make_flow(session, user)
    meta = TemplateMetadata(flow_id=flow.id, updated_by=user.id)
    session.add(meta)
    session.commit()
    session.refresh(meta)

    first = meta.updated_at
    meta.agent_summary = "Changed"
    session.add(meta)
    session.commit()
    session.refresh(meta)

    assert meta.updated_at >= first
```

- [ ] **Step 2.2: Run the test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_template_metadata_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'TemplateMetadata' from 'langflow.services.database.models'`.

- [ ] **Step 2.3: Create the model**

Create `src/backend/base/langflow/services/database/models/template_metadata/model.py`:

```python
"""Template metadata table: admin-authored AI-facing guidance for starter-project flows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from langflow.services.database.models._metadata import AgentMetadataMixin


class TemplateMetadata(AgentMetadataMixin, table=True):
    __tablename__ = "template_metadata"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        foreign_key="flow.id",
        unique=True,
        index=True,
        sa_column_kwargs={"ondelete": "CASCADE"},
    )


class TemplateMetadataRead(BaseModel):
    agent_usage_notes: str | None
    agent_summary: str | None
    updated_by: UUID
    updated_at: datetime


class TemplateMetadataRowRead(BaseModel):
    flow_id: UUID
    flow_name: str
    flow_description: str | None
    is_starter: bool
    metadata: TemplateMetadataRead | None


class TemplateMetadataWrite(BaseModel):
    agent_usage_notes: str | None = None
    agent_summary: str | None = None
```

Create `src/backend/base/langflow/services/database/models/template_metadata/__init__.py`:

```python
from .model import (
    TemplateMetadata,
    TemplateMetadataRead,
    TemplateMetadataRowRead,
    TemplateMetadataWrite,
)

__all__ = [
    "TemplateMetadata",
    "TemplateMetadataRead",
    "TemplateMetadataRowRead",
    "TemplateMetadataWrite",
]
```

- [ ] **Step 2.4: Register the model and re-run tests**

Edit `src/backend/base/langflow/services/database/models/__init__.py` — add the import and `__all__` entry alphabetically (between `Organization` and `SSOConfig` by convention):

```python
from .template_metadata import TemplateMetadata
```

and add `"TemplateMetadata",` to `__all__`.

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_template_metadata_model.py -v`
Expected: all four tests PASS.

- [ ] **Step 2.5: Pause for commit**

Proposed message: `feat(db): add TemplateMetadata model with shared mixin`.

---

## Task 3: `ComponentMetadata` SQLModel table

**Files:**
- Create: `src/backend/base/langflow/services/database/models/component_metadata/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/component_metadata/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_component_metadata_model.py`

- [ ] **Step 3.1: Write the failing test**

Create `src/backend/tests/unit/services/database/models/test_component_metadata_model.py`:

```python
"""Unit tests for ComponentMetadata SQLModel."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import ComponentMetadata, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def _make_user(session: Session) -> User:
    user = User(username="admin", password="x", is_superuser=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_component_metadata_row_can_be_created(session):
    user = _make_user(session)

    meta = ComponentMetadata(
        component_name="ADPTrigger",
        agent_usage_notes="Use this when ...",
        agent_summary="ADP event trigger component.",
        updated_by=user.id,
    )
    session.add(meta)
    session.commit()
    session.refresh(meta)

    assert meta.id is not None
    assert meta.component_name == "ADPTrigger"


def test_component_metadata_component_name_is_unique(session):
    user = _make_user(session)
    session.add(ComponentMetadata(component_name="ADPTrigger", updated_by=user.id))
    session.commit()

    dup = ComponentMetadata(component_name="ADPTrigger", updated_by=user.id)
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.commit()


def test_component_metadata_allows_not_yet_existent_name(session):
    # Forward-compat authoring: no live-catalog validation at the model layer.
    user = _make_user(session)
    meta = ComponentMetadata(
        component_name="DoesNotExistYet",
        agent_summary="Staged for upcoming release.",
        updated_by=user.id,
    )
    session.add(meta)
    session.commit()
    session.refresh(meta)

    assert session.exec(select(ComponentMetadata)).all() == [meta]


def test_component_metadata_updated_at_autobumps(session):
    user = _make_user(session)
    meta = ComponentMetadata(component_name="X", updated_by=user.id)
    session.add(meta)
    session.commit()
    session.refresh(meta)

    first = meta.updated_at
    meta.agent_summary = "Changed"
    session.add(meta)
    session.commit()
    session.refresh(meta)

    assert meta.updated_at >= first
```

- [ ] **Step 3.2: Run to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_component_metadata_model.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3.3: Create the model**

Create `src/backend/base/langflow/services/database/models/component_metadata/model.py`:

```python
"""Component metadata table: admin-authored AI-facing guidance keyed by component name."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field

from langflow.services.database.models._metadata import AgentMetadataMixin


class ComponentMetadata(AgentMetadataMixin, table=True):
    __tablename__ = "component_metadata"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    component_name: str = Field(max_length=128, unique=True, index=True)


class ComponentMetadataRead(BaseModel):
    agent_usage_notes: str | None
    agent_summary: str | None
    updated_by: UUID
    updated_at: datetime


class ComponentMetadataRowRead(BaseModel):
    component_name: str
    display_name: str | None
    category: str | None
    icon: str | None
    is_orphan: bool
    metadata: ComponentMetadataRead | None


class ComponentMetadataWrite(BaseModel):
    agent_usage_notes: str | None = None
    agent_summary: str | None = None
```

Create `src/backend/base/langflow/services/database/models/component_metadata/__init__.py`:

```python
from .model import (
    ComponentMetadata,
    ComponentMetadataRead,
    ComponentMetadataRowRead,
    ComponentMetadataWrite,
)

__all__ = [
    "ComponentMetadata",
    "ComponentMetadataRead",
    "ComponentMetadataRowRead",
    "ComponentMetadataWrite",
]
```

- [ ] **Step 3.4: Register and re-run**

Edit `src/backend/base/langflow/services/database/models/__init__.py` — add:

```python
from .component_metadata import ComponentMetadata
```

and `"ComponentMetadata",` to `__all__` (alphabetical order — sits between `ApiKey` and `Deployment`).

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_component_metadata_model.py -v`
Expected: PASS (4 tests).

- [ ] **Step 3.5: Pause for commit**

Proposed message: `feat(db): add ComponentMetadata model`.

---

## Task 4: Alembic migration

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<rev>_add_template_and_component_metadata.py`

- [ ] **Step 4.1: Generate the revision skeleton**

Run from repo root:

```
cd src/backend/base/langflow && uv run alembic revision --autogenerate -m "add template and component metadata"
```

This creates a file in `alembic/versions/` with a name like `<hash>_add_template_and_component_metadata.py`. Open it and verify:
- `down_revision: Union[str, None] = '1c3cd3e0e845'` (or whichever is current head at generation time)
- The `upgrade()` function contains `op.create_table('template_metadata', ...)` and `op.create_table('component_metadata', ...)`
- The `downgrade()` function drops both tables

If autogenerate did not produce the tables, see Step 4.2 fallback.

- [ ] **Step 4.2 (fallback if autogenerate is empty): hand-write the migration**

Replace the file body with:

```python
"""add template and component metadata

Revision ID: <generated>
Revises: 1c3cd3e0e845
Create Date: 2026-04-18 ...

"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "<generated>"
down_revision: Union[str, None] = "1c3cd3e0e845"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "template_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("flow_id", sa.Uuid(), nullable=False),
        sa.Column("agent_usage_notes", sa.Text(), nullable=True),
        sa.Column("agent_summary", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
        sa.UniqueConstraint("flow_id", name="uq_template_metadata_flow_id"),
    )
    op.create_index(
        "ix_template_metadata_flow_id", "template_metadata", ["flow_id"], unique=True
    )

    op.create_table(
        "component_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("component_name", sa.String(length=128), nullable=False),
        sa.Column("agent_usage_notes", sa.Text(), nullable=True),
        sa.Column("agent_summary", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
        sa.UniqueConstraint("component_name", name="uq_component_metadata_name"),
    )
    op.create_index(
        "ix_component_metadata_component_name",
        "component_metadata",
        ["component_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_component_metadata_component_name", table_name="component_metadata")
    op.drop_table("component_metadata")
    op.drop_index("ix_template_metadata_flow_id", table_name="template_metadata")
    op.drop_table("template_metadata")
```

- [ ] **Step 4.3: Apply the migration**

Run: `make alembic-upgrade`
Expected: alembic logs two `CREATE TABLE` statements and reports the new head.

- [ ] **Step 4.4: Verify round-trip downgrade works**

Run: `make alembic-downgrade`
Expected: both tables dropped; previous head restored.

Re-apply: `make alembic-upgrade`
Expected: back to the new head.

- [ ] **Step 4.5: Pause for commit**

Proposed message: `feat(db): migration for template_metadata and component_metadata tables`.

---

## Task 5: Starter-project identifier helper

The admin API and system-prompt-injection both need to identify starter-project flows. Build the helper once and reuse it.

**Files:**
- Create: `src/backend/base/langflow/services/database/models/flow/starter.py`
- Test: `src/backend/tests/unit/services/database/models/test_flow_starter_helper.py`

- [ ] **Step 5.1: Write the failing test**

Create `src/backend/tests/unit/services/database/models/test_flow_starter_helper.py`:

```python
"""Unit tests for starter-project detection helper."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models import Flow, Folder, User
from langflow.services.database.models.flow.starter import (
    STARTER_FOLDER_NAME,
    is_flow_a_starter_project,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def _user(s: Session) -> User:
    u = User(username="u", password="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def test_flow_in_starter_folder_is_a_starter(session):
    user = _user(session)
    starter = Folder(name=STARTER_FOLDER_NAME, user_id=user.id)
    session.add(starter)
    session.commit()
    session.refresh(starter)

    flow = Flow(name="f", user_id=user.id, folder_id=starter.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is True


def test_flow_in_other_folder_is_not_a_starter(session):
    user = _user(session)
    other = Folder(name="My Projects", user_id=user.id)
    session.add(other)
    session.commit()
    session.refresh(other)

    flow = Flow(name="f", user_id=user.id, folder_id=other.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is False


def test_flow_without_folder_is_not_a_starter(session):
    user = _user(session)
    flow = Flow(name="f", user_id=user.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is False
```

- [ ] **Step 5.2: Run to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_starter_helper.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5.3: Implement the helper**

Create `src/backend/base/langflow/services/database/models/flow/starter.py`:

```python
"""Starter-project detection for flows.

The codebase has historically identified starter projects by folder membership
rather than a boolean column. This helper centralizes that lookup so callers
don't have to know the folder name or re-implement the query.
"""

from __future__ import annotations

from sqlmodel import Session, select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder

STARTER_FOLDER_NAME = "Starter Projects"


def is_flow_a_starter_project(flow: Flow, session: Session) -> bool:
    """Return True when the flow lives in the starter-projects folder."""
    if flow.folder_id is None:
        return False
    folder = session.exec(select(Folder).where(Folder.id == flow.folder_id)).one_or_none()
    return folder is not None and folder.name == STARTER_FOLDER_NAME


def list_starter_project_flows(session: Session) -> list[Flow]:
    """Return every flow that belongs to the starter-projects folder."""
    starter_folders = session.exec(
        select(Folder).where(Folder.name == STARTER_FOLDER_NAME)
    ).all()
    if not starter_folders:
        return []
    folder_ids = {f.id for f in starter_folders}
    return session.exec(select(Flow).where(Flow.folder_id.in_(folder_ids))).all()
```

> **Note:** If the actual starter folder name used at this project is not `"Starter Projects"`, the agent should grep the codebase (`grep -r "STARTER_FOLDER_NAME\|starter projects"`) and adjust the constant to whatever `initial_setup/setup.py` uses. The test uses the constant via import, so the test will still pass either way.

- [ ] **Step 5.4: Run tests**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_starter_helper.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5.5: Pause for commit**

Proposed message: `feat(db): add is_flow_a_starter_project helper`.

---

## Task 6: Admin metadata router scaffold + template GET endpoints

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/__init__.py`
- Create: `src/backend/base/langflow/api/v1/admin/metadata.py`
- Test: `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`

- [ ] **Step 6.1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`:

```python
"""Integration tests for admin template metadata endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_templates_returns_starter_flows_with_metadata_null(
    client: AsyncClient, logged_in_headers_super_user, starter_flow
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers_super_user
    )
    assert response.status_code == 200
    rows = response.json()
    assert any(r["flow_id"] == str(starter_flow.id) for r in rows)
    starter_row = next(r for r in rows if r["flow_id"] == str(starter_flow.id))
    assert starter_row["flow_name"] == starter_flow.name
    assert starter_row["is_starter"] is True
    assert starter_row["metadata"] is None


@pytest.mark.asyncio
async def test_list_templates_excludes_non_starter_flows(
    client: AsyncClient, logged_in_headers_super_user, non_starter_flow
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers_super_user
    )
    rows = response.json()
    assert all(r["flow_id"] != str(non_starter_flow.id) for r in rows)


@pytest.mark.asyncio
async def test_list_templates_requires_superuser(
    client: AsyncClient, logged_in_headers
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_template_returns_404_for_unknown_flow(
    client: AsyncClient, logged_in_headers_super_user
):
    response = await client.get(
        "/api/v1/admin/metadata/templates/00000000-0000-0000-0000-000000000000",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 404
```

The fixtures `starter_flow`, `non_starter_flow`, `logged_in_headers`, `logged_in_headers_super_user`, and `client` are provided by the existing conftest. If any are missing (e.g., `starter_flow`), the engineer creates them locally at the top of the test file.

- [ ] **Step 6.2: Add missing fixtures if needed**

If the fixtures do not exist, add them to `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py` as module-level `@pytest.fixture` defs that use the existing `session` fixture to insert a starter folder + flow and a non-starter folder + flow. Exact code:

```python
import pytest
from sqlmodel import select

from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME


@pytest.fixture
async def starter_flow(session, active_super_user):
    folder = session.exec(
        select(Folder).where(Folder.name == STARTER_FOLDER_NAME)
    ).one_or_none()
    if folder is None:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        session.commit()
        session.refresh(folder)
    flow = Flow(
        name="Starter Slack Flow",
        description="Starter project for Slack",
        user_id=active_super_user.id,
        folder_id=folder.id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    session.commit()
    session.refresh(flow)
    return flow


@pytest.fixture
async def non_starter_flow(session, active_super_user):
    folder = Folder(name="My Projects", user_id=active_super_user.id)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    flow = Flow(
        name="User Flow",
        user_id=active_super_user.id,
        folder_id=folder.id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    session.commit()
    session.refresh(flow)
    return flow
```

- [ ] **Step 6.3: Run to verify it fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py -v`
Expected: FAIL with 404 on all endpoints (router not registered).

- [ ] **Step 6.4: Create the admin subpackage and router**

Create `src/backend/base/langflow/api/v1/admin/__init__.py`:

```python
"""Admin-gated API endpoints."""

from .metadata import router as admin_metadata_router

__all__ = ["admin_metadata_router"]
```

Create `src/backend/base/langflow/api/v1/admin/metadata.py`:

```python
"""Super-admin metadata management endpoints.

Covers both template metadata (keyed by flow_id) and component metadata
(keyed by component_name). All endpoints require an active superuser.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models import (
    ComponentMetadata,
    Flow,
    Folder,
    TemplateMetadata,
    User,
)
from langflow.services.database.models.component_metadata import (
    ComponentMetadataRead,
    ComponentMetadataRowRead,
    ComponentMetadataWrite,
)
from langflow.services.database.models.flow.starter import (
    STARTER_FOLDER_NAME,
    is_flow_a_starter_project,
)
from langflow.services.database.models.template_metadata import (
    TemplateMetadataRead,
    TemplateMetadataRowRead,
    TemplateMetadataWrite,
)
from langflow.services.deps import DbSession

router = APIRouter(tags=["Admin Metadata"], prefix="/admin/metadata")


def _template_row_read(flow: Flow, meta: TemplateMetadata | None) -> TemplateMetadataRowRead:
    return TemplateMetadataRowRead(
        flow_id=flow.id,
        flow_name=flow.name,
        flow_description=getattr(flow, "description", None),
        is_starter=True,
        metadata=(
            TemplateMetadataRead(
                agent_usage_notes=meta.agent_usage_notes,
                agent_summary=meta.agent_summary,
                updated_by=meta.updated_by,
                updated_at=meta.updated_at,
            )
            if meta is not None
            else None
        ),
    )


# ---------------- Templates ----------------

@router.get(
    "/templates",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[TemplateMetadataRowRead],
)
async def list_template_metadata(*, session: DbSession) -> list[TemplateMetadataRowRead]:
    """List all starter-project flows and their metadata (nullable)."""
    starter_folders = (await session.exec(
        select(Folder).where(Folder.name == STARTER_FOLDER_NAME)
    )).all()
    if not starter_folders:
        return []
    folder_ids = {f.id for f in starter_folders}
    flows = (await session.exec(
        select(Flow).where(Flow.folder_id.in_(folder_ids))
    )).all()
    if not flows:
        return []
    flow_ids = [f.id for f in flows]
    metas = (await session.exec(
        select(TemplateMetadata).where(TemplateMetadata.flow_id.in_(flow_ids))
    )).all()
    meta_by_flow = {m.flow_id: m for m in metas}
    return [_template_row_read(f, meta_by_flow.get(f.id)) for f in flows]


@router.get(
    "/templates/{flow_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TemplateMetadataRowRead,
)
async def get_template_metadata(
    flow_id: UUID, *, session: DbSession
) -> TemplateMetadataRowRead:
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    meta = (await session.exec(
        select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
    )).one_or_none()
    row = _template_row_read(flow, meta)
    # Re-derive is_starter accurately for single-flow reads
    row.is_starter = is_flow_a_starter_project(flow, session)
    return row
```

- [ ] **Step 6.5: Register the admin router**

Edit `src/backend/base/langflow/api/v1/__init__.py` — add the import (alphabetical between `Admin` imports or at the top of the imports if there are none):

```python
from langflow.api.v1.admin import admin_metadata_router
```

and `"admin_metadata_router",` to `__all__`.

Then find the FastAPI app factory where other routers are `include_router`'d (search for `assistant_router`) and add:

```python
app.include_router(admin_metadata_router, prefix="/api/v1")
```

(Or follow whatever local convention the surrounding `include_router` calls use.)

- [ ] **Step 6.6: Re-run tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py -v`
Expected: 4 tests PASS.

- [ ] **Step 6.7: Pause for commit**

Proposed message: `feat(api): admin GET endpoints for template metadata`.

---

## Task 7: Template metadata PUT + DELETE endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/metadata.py`
- Modify: `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`

- [ ] **Step 7.1: Write failing tests**

Append to `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`:

```python
@pytest.mark.asyncio
async def test_put_template_creates_metadata_row(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, session
):
    response = await client.put(
        f"/api/v1/admin/metadata/templates/{starter_flow.id}",
        headers=logged_in_headers_super_user,
        json={
            "agent_usage_notes": "Use for Slack onboarding.",
            "agent_summary": "Onboarding notifier.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_summary"] == "Onboarding notifier."

    row = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow.id)
        )
    ).one_or_none()
    assert row is not None
    assert row.agent_usage_notes == "Use for Slack onboarding."


@pytest.mark.asyncio
async def test_put_template_updates_existing_row(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, active_super_user, session
):
    session.add(
        TemplateMetadata(
            flow_id=starter_flow.id,
            agent_summary="Old",
            updated_by=active_super_user.id,
        )
    )
    session.commit()

    response = await client.put(
        f"/api/v1/admin/metadata/templates/{starter_flow.id}",
        headers=logged_in_headers_super_user,
        json={"agent_summary": "New"},
    )
    assert response.status_code == 200
    assert response.json()["agent_summary"] == "New"

    rows = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].agent_summary == "New"


@pytest.mark.asyncio
async def test_delete_template_removes_row_but_keeps_flow(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, active_super_user, session
):
    session.add(TemplateMetadata(flow_id=starter_flow.id, updated_by=active_super_user.id))
    session.commit()

    response = await client.delete(
        f"/api/v1/admin/metadata/templates/{starter_flow.id}",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 204

    meta_rows = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow.id)
        )
    ).all()
    assert meta_rows == []

    flow_still_there = (
        await session.exec(select(Flow).where(Flow.id == starter_flow.id))
    ).one_or_none()
    assert flow_still_there is not None
```

Add `from sqlmodel import select` and `from langflow.services.database.models import TemplateMetadata, Flow` to the imports at the top of the test file if they're not already there.

- [ ] **Step 7.2: Run to verify failures**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py -v -k "put or delete"`
Expected: 405 Method Not Allowed.

- [ ] **Step 7.3: Implement PUT + DELETE**

Append to `src/backend/base/langflow/api/v1/admin/metadata.py`:

```python
@router.put(
    "/templates/{flow_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TemplateMetadataRead,
)
async def upsert_template_metadata(
    flow_id: UUID,
    body: TemplateMetadataWrite,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> TemplateMetadataRead:
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")

    row = (await session.exec(
        select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
    )).one_or_none()
    if row is None:
        row = TemplateMetadata(
            flow_id=flow_id,
            agent_usage_notes=body.agent_usage_notes,
            agent_summary=body.agent_summary,
            updated_by=current_user.id,
        )
    else:
        row.agent_usage_notes = body.agent_usage_notes
        row.agent_summary = body.agent_summary
        row.updated_by = current_user.id

    session.add(row)
    await session.commit()
    await session.refresh(row)

    return TemplateMetadataRead(
        agent_usage_notes=row.agent_usage_notes,
        agent_summary=row.agent_summary,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.delete(
    "/templates/{flow_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_metadata(flow_id: UUID, *, session: DbSession) -> None:
    row = (await session.exec(
        select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
    )).one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return None
```

- [ ] **Step 7.4: Re-run**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py -v`
Expected: all tests PASS.

- [ ] **Step 7.5: Pause for commit**

Proposed message: `feat(api): admin PUT/DELETE for template metadata`.

---

## Task 8: Component metadata endpoints (GET list, GET one, PUT, DELETE)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/metadata.py`
- Create: `src/backend/tests/unit/api/v1/test_admin_component_metadata_api.py`

- [ ] **Step 8.1: Write failing tests**

Create `src/backend/tests/unit/api/v1/test_admin_component_metadata_api.py`:

```python
"""Integration tests for admin component metadata endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import ComponentMetadata


@pytest.mark.asyncio
async def test_list_components_includes_live_and_orphan_rows(
    client: AsyncClient, logged_in_headers_super_user, active_super_user, session
):
    session.add(
        ComponentMetadata(
            component_name="DoesNotExistYet",
            agent_summary="Staged.",
            updated_by=active_super_user.id,
        )
    )
    session.commit()

    response = await client.get(
        "/api/v1/admin/metadata/components", headers=logged_in_headers_super_user
    )
    assert response.status_code == 200
    rows = response.json()
    by_name = {r["component_name"]: r for r in rows}

    # Live component (one that ships with the catalog)
    assert "Webhook" in by_name, "Live catalog must include Webhook"
    assert by_name["Webhook"]["is_orphan"] is False
    assert by_name["Webhook"]["display_name"] is not None

    # Orphan row
    assert "DoesNotExistYet" in by_name
    assert by_name["DoesNotExistYet"]["is_orphan"] is True


@pytest.mark.asyncio
async def test_put_component_creates_row(
    client: AsyncClient, logged_in_headers_super_user, session
):
    response = await client.put(
        "/api/v1/admin/metadata/components/Webhook",
        headers=logged_in_headers_super_user,
        json={"agent_summary": "Inbound webhook receiver.", "agent_usage_notes": "..."},
    )
    assert response.status_code == 200
    assert response.json()["agent_summary"] == "Inbound webhook receiver."

    row = (
        await session.exec(
            select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
        )
    ).one_or_none()
    assert row is not None


@pytest.mark.asyncio
async def test_delete_component_removes_orphan(
    client: AsyncClient, logged_in_headers_super_user, active_super_user, session
):
    session.add(
        ComponentMetadata(component_name="DeadName", updated_by=active_super_user.id)
    )
    session.commit()

    response = await client.delete(
        "/api/v1/admin/metadata/components/DeadName",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 204
    rows = (
        await session.exec(
            select(ComponentMetadata).where(ComponentMetadata.component_name == "DeadName")
        )
    ).all()
    assert rows == []


@pytest.mark.asyncio
async def test_components_endpoint_requires_superuser(
    client: AsyncClient, logged_in_headers
):
    response = await client.get(
        "/api/v1/admin/metadata/components", headers=logged_in_headers
    )
    assert response.status_code == 403
```

- [ ] **Step 8.2: Run to verify failures**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_component_metadata_api.py -v`
Expected: 404 on all endpoints (routes not implemented).

- [ ] **Step 8.3: Implement the component endpoints**

Append to `src/backend/base/langflow/api/v1/admin/metadata.py`:

```python
# ---------------- Components ----------------


async def _live_component_index() -> dict[str, dict]:
    """Return {component_name: {display_name, category, icon}} from the live catalog."""
    from langflow.agentic.utils.component_search import list_all_components

    items = await list_all_components()
    return {
        item["name"]: {
            "display_name": item.get("display_name"),
            "category": item.get("type"),
            "icon": item.get("icon"),
        }
        for item in items
    }


def _component_row_read(
    name: str, live: dict | None, meta: ComponentMetadata | None
) -> ComponentMetadataRowRead:
    return ComponentMetadataRowRead(
        component_name=name,
        display_name=(live or {}).get("display_name"),
        category=(live or {}).get("category"),
        icon=(live or {}).get("icon"),
        is_orphan=(live is None and meta is not None),
        metadata=(
            ComponentMetadataRead(
                agent_usage_notes=meta.agent_usage_notes,
                agent_summary=meta.agent_summary,
                updated_by=meta.updated_by,
                updated_at=meta.updated_at,
            )
            if meta is not None
            else None
        ),
    )


@router.get(
    "/components",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[ComponentMetadataRowRead],
)
async def list_component_metadata(
    *, session: DbSession
) -> list[ComponentMetadataRowRead]:
    live = await _live_component_index()
    meta_rows = (await session.exec(select(ComponentMetadata))).all()
    meta_by_name = {m.component_name: m for m in meta_rows}

    all_names = set(live.keys()) | set(meta_by_name.keys())
    rows = [
        _component_row_read(name, live.get(name), meta_by_name.get(name))
        for name in sorted(all_names)
    ]
    return rows


@router.get(
    "/components/{component_name}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ComponentMetadataRowRead,
)
async def get_component_metadata(
    component_name: str, *, session: DbSession
) -> ComponentMetadataRowRead:
    live = (await _live_component_index()).get(component_name)
    meta = (await session.exec(
        select(ComponentMetadata).where(ComponentMetadata.component_name == component_name)
    )).one_or_none()
    if live is None and meta is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return _component_row_read(component_name, live, meta)


@router.put(
    "/components/{component_name}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ComponentMetadataRead,
)
async def upsert_component_metadata(
    component_name: str,
    body: ComponentMetadataWrite,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> ComponentMetadataRead:
    row = (await session.exec(
        select(ComponentMetadata).where(ComponentMetadata.component_name == component_name)
    )).one_or_none()
    if row is None:
        row = ComponentMetadata(
            component_name=component_name,
            agent_usage_notes=body.agent_usage_notes,
            agent_summary=body.agent_summary,
            updated_by=current_user.id,
        )
    else:
        row.agent_usage_notes = body.agent_usage_notes
        row.agent_summary = body.agent_summary
        row.updated_by = current_user.id
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return ComponentMetadataRead(
        agent_usage_notes=row.agent_usage_notes,
        agent_summary=row.agent_summary,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.delete(
    "/components/{component_name}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_component_metadata(
    component_name: str, *, session: DbSession
) -> None:
    row = (await session.exec(
        select(ComponentMetadata).where(ComponentMetadata.component_name == component_name)
    )).one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return None
```

- [ ] **Step 8.4: Run tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_admin_component_metadata_api.py -v`
Expected: all PASS.

- [ ] **Step 8.5: Pause for commit**

Proposed message: `feat(api): admin CRUD for component metadata`.

---

## Task 9: Inline-merge metadata into `search_components`

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/catalog.py`
- Create: `src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py`

- [ ] **Step 9.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py`:

```python
"""search_components and get_component_schema must merge metadata rows."""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.catalog import (
    get_component_schema,
    search_components,
)
from langflow.services.database.models import ComponentMetadata


@pytest.mark.asyncio
async def test_search_components_includes_agent_summary_when_metadata_exists(
    session, active_super_user
):
    session.add(
        ComponentMetadata(
            component_name="Webhook",
            agent_summary="Inbound HTTP entry.",
            updated_by=active_super_user.id,
        )
    )
    session.commit()

    results = await search_components(query="webhook")
    hit = next((r for r in results if r["name"] == "Webhook"), None)
    assert hit is not None
    assert hit["agent_summary"] == "Inbound HTTP entry."


@pytest.mark.asyncio
async def test_search_components_returns_null_agent_summary_when_no_metadata():
    results = await search_components(query="webhook")
    hit = next((r for r in results if r["name"] == "Webhook"), None)
    assert hit is not None
    assert hit.get("agent_summary") is None


@pytest.mark.asyncio
async def test_get_component_schema_merges_agent_usage_notes(
    session, active_super_user
):
    session.add(
        ComponentMetadata(
            component_name="Webhook",
            agent_usage_notes="Configure event types before wiring downstream.",
            updated_by=active_super_user.id,
        )
    )
    session.commit()

    schema = await get_component_schema("Webhook")
    assert schema is not None
    assert schema["agent_usage_notes"] == "Configure event types before wiring downstream."


@pytest.mark.asyncio
async def test_get_component_schema_returns_null_usage_notes_when_absent():
    schema = await get_component_schema("Webhook")
    assert schema is not None
    assert schema.get("agent_usage_notes") is None
```

- [ ] **Step 9.2: Run to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py -v`
Expected: KeyError or None for `agent_summary`/`agent_usage_notes`.

- [ ] **Step 9.3: Add a small helper for metadata reads**

Create `src/backend/base/langflow/services/assistant/tools/metadata_lookup.py`:

```python
"""Shared metadata lookup helpers for assistant tools."""

from __future__ import annotations

from sqlmodel import select

from langflow.services.database.models import ComponentMetadata, TemplateMetadata
from langflow.services.deps import session_getter


async def fetch_component_summaries(names: list[str]) -> dict[str, str | None]:
    """Return {component_name: agent_summary} for the given names (absent → None)."""
    if not names:
        return {}
    async with session_getter() as session:
        rows = (await session.exec(
            select(ComponentMetadata).where(ComponentMetadata.component_name.in_(names))
        )).all()
    return {r.component_name: r.agent_summary for r in rows}


async def fetch_component_usage_notes(component_name: str) -> str | None:
    async with session_getter() as session:
        row = (await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == component_name
            )
        )).one_or_none()
    return row.agent_usage_notes if row else None


async def fetch_template_summaries() -> list[dict]:
    """Return rows with (flow_id, flow_name, agent_summary) for system-prompt injection."""
    from langflow.services.database.models import Flow

    async with session_getter() as session:
        metas = (await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.agent_summary.is_not(None))
        )).all()
        if not metas:
            return []
        flow_ids = [m.flow_id for m in metas]
        flows = (await session.exec(select(Flow).where(Flow.id.in_(flow_ids)))).all()
    flow_by_id = {f.id: f for f in flows}
    out = []
    for m in metas:
        flow = flow_by_id.get(m.flow_id)
        if flow is None:
            continue
        out.append({
            "flow_id": str(flow.id),
            "flow_name": flow.name,
            "agent_summary": m.agent_summary,
        })
    out.sort(key=lambda r: r["flow_name"])
    return out


async def fetch_template_usage_notes(flow_id: str) -> dict | None:
    """Return {flow_id, flow_name, agent_usage_notes} for a single template."""
    from uuid import UUID

    from langflow.services.database.models import Flow

    try:
        parsed = UUID(flow_id)
    except ValueError:
        return None
    async with session_getter() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == parsed))).one_or_none()
        if flow is None:
            return None
        meta = (await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == parsed)
        )).one_or_none()
    return {
        "flow_id": flow_id,
        "flow_name": flow.name,
        "agent_usage_notes": meta.agent_usage_notes if meta else None,
    }
```

> **Note:** If `session_getter` is not importable from `langflow.services.deps`, grep for the actual async-session context manager (`get_session`, `session_scope`, etc.) and use that. The rest of the module stays unchanged.

- [ ] **Step 9.4: Modify `search_components` to merge**

Edit `src/backend/base/langflow/services/assistant/tools/catalog.py` — add the import:

```python
from langflow.services.assistant.tools.metadata_lookup import (
    fetch_component_summaries,
    fetch_component_usage_notes,
)
```

And extend `search_components` to merge after building its base list. Replace the existing `return` with:

```python
    summaries = await fetch_component_summaries([r["name"] for r in results])
    for r in results:
        r["agent_summary"] = summaries.get(r["name"])
    return results
```

(If the current `search_components` body names the list something other than `results`, preserve the existing name; just iterate it to splice in `agent_summary`.)

- [ ] **Step 9.5: Modify `get_component_schema` to merge**

In the same file, at the end of `get_component_schema`, before the final `return`:

```python
    if schema is not None:
        schema["agent_usage_notes"] = await fetch_component_usage_notes(component_name)
    return schema
```

- [ ] **Step 9.6: Run the tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py -v`
Expected: all PASS.

- [ ] **Step 9.7: Pause for commit**

Proposed message: `feat(assistant): merge component metadata into catalog tool results`.

---

## Task 10: `get_template_instructions` tool

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/template_metadata.py`
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py`
- Create: `src/backend/tests/unit/services/assistant/tools/test_get_template_instructions_tool.py`

- [ ] **Step 10.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/tools/test_get_template_instructions_tool.py`:

```python
"""Unit tests for get_template_instructions tool."""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.template_metadata import get_template_instructions
from langflow.services.database.models import Flow, Folder, TemplateMetadata


@pytest.mark.asyncio
async def test_returns_usage_notes_when_metadata_exists(
    session, active_super_user
):
    folder = Folder(name="Starter Projects", user_id=active_super_user.id)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    flow = Flow(name="Onboard", user_id=active_super_user.id, folder_id=folder.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    session.add(
        TemplateMetadata(
            flow_id=flow.id,
            agent_usage_notes="Ask for Slack channel, then wire it.",
            updated_by=active_super_user.id,
        )
    )
    session.commit()

    result = await get_template_instructions(str(flow.id))
    assert result is not None
    assert result["flow_id"] == str(flow.id)
    assert result["flow_name"] == "Onboard"
    assert result["agent_usage_notes"] == "Ask for Slack channel, then wire it."


@pytest.mark.asyncio
async def test_returns_null_notes_when_metadata_absent(session, active_super_user):
    folder = Folder(name="Starter Projects", user_id=active_super_user.id)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    flow = Flow(name="Onboard2", user_id=active_super_user.id, folder_id=folder.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)

    result = await get_template_instructions(str(flow.id))
    assert result is not None
    assert result["agent_usage_notes"] is None


@pytest.mark.asyncio
async def test_returns_none_when_flow_missing():
    result = await get_template_instructions("00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_flow_id_unparseable():
    result = await get_template_instructions("not-a-uuid")
    assert result is None
```

- [ ] **Step 10.2: Run to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_get_template_instructions_tool.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 10.3: Implement the tool**

Create `src/backend/base/langflow/services/assistant/tools/template_metadata.py`:

```python
"""Tool: get_template_instructions — on-demand fetch of a template's usage notes."""

from __future__ import annotations

from typing import Any

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def get_template_instructions(flow_id: str) -> dict[str, Any] | None:
    """Return the agent_usage_notes for a template, keyed by its flow id.

    Returns None when the flow doesn't exist or the id is malformed.
    Returns {"flow_id", "flow_name", "agent_usage_notes"} otherwise;
    agent_usage_notes is None when the metadata row is absent.
    """
    return await fetch_template_usage_notes(flow_id)
```

- [ ] **Step 10.4: Register the tool**

Edit `src/backend/base/langflow/services/assistant/tools/registry.py` — append to `CATALOG_TOOLS` a new entry:

```python
{
    "name": "get_template_instructions",
    "description": (
        "Fetch the full admin-authored usage notes for a starter-project "
        "template, keyed by flow_id. Call this after matching a template "
        "from the Available Templates list in the system prompt, before "
        "mutating the flow. Returns {flow_id, flow_name, agent_usage_notes}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "flow_id": {
                "type": "string",
                "description": "UUID of the template's flow.",
            },
        },
        "required": ["flow_id"],
    },
},
```

Then, in whichever tool-dispatch function maps tool names → callables (usually at the bottom of `registry.py` or inside `service.py`), add:

```python
from langflow.services.assistant.tools.template_metadata import get_template_instructions
# and add "get_template_instructions": get_template_instructions to the dispatch dict
```

Confirm the dispatch dict name by grep'ing `registry.py` for the existing `search_components` mapping and following its pattern.

- [ ] **Step 10.5: Re-run**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_get_template_instructions_tool.py -v`
Expected: 4 tests PASS.

- [ ] **Step 10.6: Pause for commit**

Proposed message: `feat(assistant): add get_template_instructions tool`.

---

## Task 11: Template-summary system prompt block

**Files:**
- Create: `src/backend/base/langflow/services/assistant/template_prompt.py`
- Modify: `src/backend/base/langflow/services/assistant/service.py`
- Create: `src/backend/tests/unit/services/assistant/test_template_prompt_block.py`

- [ ] **Step 11.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_template_prompt_block.py`:

```python
"""Unit tests for template-summary system-prompt block."""

from __future__ import annotations

import pytest

from langflow.services.assistant.template_prompt import build_available_templates_block
from langflow.services.database.models import Flow, Folder, TemplateMetadata


@pytest.mark.asyncio
async def test_empty_when_no_summaries(session):
    text = await build_available_templates_block()
    assert text == ""


@pytest.mark.asyncio
async def test_block_lists_flows_with_summaries_sorted(session, active_super_user):
    folder = Folder(name="Starter Projects", user_id=active_super_user.id)
    session.add(folder)
    session.commit()
    session.refresh(folder)

    def _flow(name: str) -> Flow:
        f = Flow(name=name, user_id=active_super_user.id, folder_id=folder.id)
        session.add(f)
        session.commit()
        session.refresh(f)
        return f

    f1 = _flow("Zeta Flow")
    f2 = _flow("Alpha Flow")
    session.add_all([
        TemplateMetadata(
            flow_id=f1.id,
            agent_summary="Zeta summary.",
            updated_by=active_super_user.id,
        ),
        TemplateMetadata(
            flow_id=f2.id,
            agent_summary="Alpha summary.",
            updated_by=active_super_user.id,
        ),
    ])
    session.commit()

    text = await build_available_templates_block()
    assert "## Available Templates" in text
    # Sorted by flow name -> Alpha before Zeta
    assert text.index("Alpha Flow") < text.index("Zeta Flow")
    assert "Alpha summary." in text
    assert "Zeta summary." in text
    # Uses flow_id-style reference
    assert str(f1.id) in text
    assert str(f2.id) in text


@pytest.mark.asyncio
async def test_block_excludes_flows_with_null_summary(session, active_super_user):
    folder = Folder(name="Starter Projects", user_id=active_super_user.id)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    flow = Flow(name="SilentFlow", user_id=active_super_user.id, folder_id=folder.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    session.add(TemplateMetadata(flow_id=flow.id, updated_by=active_super_user.id))
    session.commit()

    text = await build_available_templates_block()
    assert "SilentFlow" not in text
```

- [ ] **Step 11.2: Run to verify failures**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_template_prompt_block.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 11.3: Implement the builder**

Create `src/backend/base/langflow/services/assistant/template_prompt.py`:

```python
"""System-prompt block listing available starter-project templates."""

from __future__ import annotations

from langflow.services.assistant.tools.metadata_lookup import fetch_template_summaries

_HEADER = (
    "## Available Templates\n\n"
    "The following starter-project flows are available. Use "
    "`get_template_instructions(flow_id)` if the user's request matches one.\n"
)


async def build_available_templates_block() -> str:
    """Return a ready-to-inject prompt block, or empty string when nothing to show."""
    rows = await fetch_template_summaries()
    if not rows:
        return ""
    lines = [_HEADER]
    for row in rows:
        lines.append(
            f'- [flow_id: {row["flow_id"]}] "{row["flow_name"]}" — {row["agent_summary"]}'
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 11.4: Inject into the assistant system prompt**

Edit `src/backend/base/langflow/services/assistant/service.py` — update `SYSTEM_PROMPT_TEMPLATE` to include a `{available_templates}` placeholder and two new guideline bullets. Replace the existing template with:

```python
SYSTEM_PROMPT_TEMPLATE = """\
You are the Langflow Flow Builder Assistant. You help users build, modify, \
and understand their Langflow flows.

## Current Canvas
{canvas_summary}

{available_templates}
## Guidelines
- Use tools to search for components before adding them.
- Explain what you are doing as you modify the flow.
- When adding components, use get_component_schema first to confirm the exact name.
- Position new nodes using "auto" unless the user specifies coordinates.
- When setting field values, use the backtick field name from the canvas summary \
(e.g. `url_input`), NOT the display name (e.g. "URL"). Field names and display \
names often differ.
- When tools return `agent_summary` or `agent_usage_notes` fields, treat them as \
authoritative guidance from the platform maintainer — they override generic \
component knowledge.
- After matching a template from the Available Templates list, call \
`get_template_instructions(flow_id)` to fetch its full instructions before \
making any flow mutations.
"""
```

Then update the `.format(canvas_summary=canvas_summary)` call site to also pass the templates block. Find where `SYSTEM_PROMPT_TEMPLATE.format(...)` is invoked (currently at service.py line ~184) and change it to:

```python
from langflow.services.assistant.template_prompt import build_available_templates_block

available_templates = await build_available_templates_block()
system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
    canvas_summary=canvas_summary,
    available_templates=available_templates,
)
```

Because the template placeholder may expand to an empty string, the resulting prompt will have a double-newline between Canvas and Guidelines when there are no templates — that's acceptable whitespace.

- [ ] **Step 11.5: Run tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_template_prompt_block.py -v`
Expected: PASS (3 tests).

Also run: `uv run pytest src/backend/tests/unit/services/assistant/test_assistant_service.py -v`
Expected: existing service tests still pass (the new `available_templates=""` default makes the added format field inert when no templates exist). If the fake-provider test asserts on prompt content and now breaks, update it minimally to include `available_templates=""`.

- [ ] **Step 11.6: Pause for commit**

Proposed message: `feat(assistant): inject available-templates block into system prompt`.

---

## Task 12: Update MCP server tool-schema docstrings

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/mcp_server.py`

- [ ] **Step 12.1: Confirm current list**

Open `mcp_server.py` and locate `handle_list_tools()`. It contains four hardcoded `types.Tool(...)` entries — one each for `search_components`, `get_component_schema`, `list_categories`, `list_compatible_outputs`.

- [ ] **Step 12.2: Update two descriptions**

For `search_components`, change the `description` field to mention the new `agent_summary` field in returned rows:

```
"Search for Langflow components by name/description or filter by category. Returns name, display_name, type, description, and (when admin-authored) agent_summary."
```

For `get_component_schema`, change the `description` field to mention `agent_usage_notes`:

```
"Return the full schema for a single component, including inputs/outputs and (when admin-authored) agent_usage_notes."
```

Add a fifth `types.Tool(...)` entry mirroring the registry-level tool:

```python
types.Tool(
    name="get_template_instructions",
    description=(
        "Fetch the admin-authored usage notes for a starter-project template, "
        "keyed by flow_id. Returns {flow_id, flow_name, agent_usage_notes}."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "flow_id": {
                "type": "string",
                "description": "UUID of the template's flow.",
            },
        },
        "required": ["flow_id"],
    },
),
```

Also update `handle_call_tool()` to dispatch `get_template_instructions` — find the existing `elif name == "search_components":` block and add:

```python
elif name == "get_template_instructions":
    from langflow.services.assistant.tools.template_metadata import (
        get_template_instructions,
    )
    result = await get_template_instructions(**arguments)
```

- [ ] **Step 12.3: Smoke-test MCP exposure**

Run: `uv run pytest src/backend/tests/unit/services/assistant -k mcp -v`
Expected: any existing MCP tests still pass. If none exist, skip — the manual verification checklist covers this end-to-end.

- [ ] **Step 12.4: Pause for commit**

Proposed message: `feat(assistant): expose metadata-enriched catalog tools via MCP`.

---

## Task 13: Frontend superuser route guard

**Files:**
- Create: `src/frontend/src/components/authorization/authSuperuserGuard/index.tsx`

- [ ] **Step 13.1: Create the guard**

Create `src/frontend/src/components/authorization/authSuperuserGuard/index.tsx`:

```tsx
import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { useAuthStore } from "@/stores/authStore";
import CustomNavigate from "@/customization/components/custom-navigate";
import LoadingPage from "@/pages/LoadingPage";

type Props = { children: React.ReactNode };

export const ProtectedSuperuserRoute = ({ children }: Props) => {
  const { userData } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const autoLogin = useAuthStore((s) => s.autoLogin);

  if (!isAuthenticated) {
    return <LoadingPage />;
  }
  if (!userData?.is_superuser || autoLogin) {
    return <CustomNavigate to="/" replace />;
  }
  return <>{children}</>;
};
```

- [ ] **Step 13.2: No tests in this task**

Unit-testing a guard in isolation is low-value; the route-level test in Task 18 exercises it. Proceed.

- [ ] **Step 13.3: Pause for commit**

Proposed message: `feat(frontend): add ProtectedSuperuserRoute guard`.

---

## Task 14: Frontend types + API base URL constants

**Files:**
- Create: `src/frontend/src/types/metadata/index.ts`
- Modify: `src/frontend/src/controllers/API/helpers/constants.ts`

- [ ] **Step 14.1: Create the TS types**

Create `src/frontend/src/types/metadata/index.ts`:

```typescript
export type TemplateMetadataRead = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
  updated_by: string;
  updated_at: string;
};

export type TemplateMetadataRow = {
  flow_id: string;
  flow_name: string;
  flow_description: string | null;
  is_starter: boolean;
  metadata: TemplateMetadataRead | null;
};

export type TemplateMetadataWrite = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
};

export type ComponentMetadataRead = TemplateMetadataRead;

export type ComponentMetadataRow = {
  component_name: string;
  display_name: string | null;
  category: string | null;
  icon: string | null;
  is_orphan: boolean;
  metadata: ComponentMetadataRead | null;
};

export type ComponentMetadataWrite = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
};
```

- [ ] **Step 14.2: Add base URL constants**

Edit `src/frontend/src/controllers/API/helpers/constants.ts` — locate the URL map (search for `TRACES` or `ASSISTANT`) and add:

```ts
METADATA_TEMPLATES: `/api/v1/admin/metadata/templates`,
METADATA_COMPONENTS: `/api/v1/admin/metadata/components`,
```

(Or `getURL("METADATA_TEMPLATES")` depending on the existing helper style — match the surrounding pattern.)

- [ ] **Step 14.3: Pause for commit**

Proposed message: `feat(frontend): add metadata TS types and API URL constants`.

---

## Task 15: Frontend query hooks for templates

**Files:**
- Create: `src/frontend/src/controllers/API/queries/metadata/index.ts`
- Create: `src/frontend/src/controllers/API/queries/metadata/use-template-metadata.ts`

- [ ] **Step 15.1: Create the hook module**

Create `src/frontend/src/controllers/API/queries/metadata/use-template-metadata.ts`:

```typescript
import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  TemplateMetadataRead,
  TemplateMetadataRow,
  TemplateMetadataWrite,
} from "@/types/metadata";

const BASE = getURL("METADATA_TEMPLATES");

export function useListTemplateMetadata() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateMetadataRow[]> => {
    const res = await api.get<TemplateMetadataRow[]>(BASE);
    return res.data;
  };
  return query(["metadata", "templates", "list"], fn, {
    placeholderData: keepPreviousData,
  });
}

export function useUpsertTemplateMetadata() {
  const { mutate } = UseRequestProcessor();
  const fn = async ({
    flowId,
    body,
  }: {
    flowId: string;
    body: TemplateMetadataWrite;
  }): Promise<TemplateMetadataRead> => {
    const res = await api.put<TemplateMetadataRead>(`${BASE}/${flowId}`, body);
    return res.data;
  };
  return mutate(["metadata", "templates", "upsert"], fn, {
    invalidates: [["metadata", "templates", "list"]],
  });
}

export function useDeleteTemplateMetadata() {
  const { mutate } = UseRequestProcessor();
  const fn = async ({ flowId }: { flowId: string }): Promise<void> => {
    await api.delete(`${BASE}/${flowId}`);
  };
  return mutate(["metadata", "templates", "delete"], fn, {
    invalidates: [["metadata", "templates", "list"]],
  });
}
```

> **Note:** `UseRequestProcessor().mutate(...)` may have a different signature in this codebase. Match the pattern from any other `use-*.ts` in `controllers/API/queries/` that already declares a mutation. The important parts: invalidate the `["metadata","templates","list"]` cache key on success.

- [ ] **Step 15.2: Re-export**

Create `src/frontend/src/controllers/API/queries/metadata/index.ts`:

```typescript
export * from "./use-template-metadata";
```

- [ ] **Step 15.3: Pause for commit**

Proposed message: `feat(frontend): template metadata query hooks`.

---

## Task 16: Frontend query hooks for components

**Files:**
- Create: `src/frontend/src/controllers/API/queries/metadata/use-component-metadata.ts`
- Modify: `src/frontend/src/controllers/API/queries/metadata/index.ts`

- [ ] **Step 16.1: Create the hook module**

Create `src/frontend/src/controllers/API/queries/metadata/use-component-metadata.ts`:

```typescript
import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  ComponentMetadataRead,
  ComponentMetadataRow,
  ComponentMetadataWrite,
} from "@/types/metadata";

const BASE = getURL("METADATA_COMPONENTS");

export function useListComponentMetadata() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<ComponentMetadataRow[]> => {
    const res = await api.get<ComponentMetadataRow[]>(BASE);
    return res.data;
  };
  return query(["metadata", "components", "list"], fn, {
    placeholderData: keepPreviousData,
  });
}

export function useUpsertComponentMetadata() {
  const { mutate } = UseRequestProcessor();
  const fn = async ({
    componentName,
    body,
  }: {
    componentName: string;
    body: ComponentMetadataWrite;
  }): Promise<ComponentMetadataRead> => {
    const res = await api.put<ComponentMetadataRead>(
      `${BASE}/${encodeURIComponent(componentName)}`,
      body,
    );
    return res.data;
  };
  return mutate(["metadata", "components", "upsert"], fn, {
    invalidates: [["metadata", "components", "list"]],
  });
}

export function useDeleteComponentMetadata() {
  const { mutate } = UseRequestProcessor();
  const fn = async ({ componentName }: { componentName: string }): Promise<void> => {
    await api.delete(`${BASE}/${encodeURIComponent(componentName)}`);
  };
  return mutate(["metadata", "components", "delete"], fn, {
    invalidates: [["metadata", "components", "list"]],
  });
}
```

- [ ] **Step 16.2: Re-export**

Edit `src/frontend/src/controllers/API/queries/metadata/index.ts`:

```typescript
export * from "./use-template-metadata";
export * from "./use-component-metadata";
```

- [ ] **Step 16.3: Pause for commit**

Proposed message: `feat(frontend): component metadata query hooks`.

---

## Task 17: Metadata edit form component (shared between tabs)

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/metadata-edit-form.tsx`
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/metadata-edit-form.test.tsx`

- [ ] **Step 17.1: Write the failing test**

Create the test file at `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/metadata-edit-form.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { MetadataEditForm } from "../metadata-edit-form";

describe("MetadataEditForm", () => {
  it("renders two textareas labeled 'Agent summary' and 'Agent usage notes'", () => {
    render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/agent summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/agent usage notes/i)).toBeInTheDocument();
  });

  it("submits the entered values", () => {
    const onSave = jest.fn();
    render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={onSave}
        onCancel={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/agent summary/i), {
      target: { value: "Short summary" },
    });
    fireEvent.change(screen.getByLabelText(/agent usage notes/i), {
      target: { value: "Detailed notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(onSave).toHaveBeenCalledWith({
      agent_summary: "Short summary",
      agent_usage_notes: "Detailed notes",
    });
  });

  it("shows a Delete button only when the row already exists", () => {
    const { rerender } = render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /delete metadata/i })).toBeNull();

    rerender(
      <MetadataEditForm
        initial={{ agent_summary: "s", agent_usage_notes: "n" }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /delete metadata/i }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 17.2: Run to verify failure**

Run: `npm test -- metadata-edit-form`
Expected: `Cannot find module '../metadata-edit-form'`.

- [ ] **Step 17.3: Implement the form**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/metadata-edit-form.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type Initial = {
  agent_summary: string | null;
  agent_usage_notes: string | null;
};

type Payload = {
  agent_summary: string | null;
  agent_usage_notes: string | null;
};

type Props = {
  initial: Initial;
  onSave: (payload: Payload) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function MetadataEditForm({ initial, onSave, onCancel, onDelete }: Props) {
  const [summary, setSummary] = useState(initial.agent_summary ?? "");
  const [notes, setNotes] = useState(initial.agent_usage_notes ?? "");

  const hasExistingRow = initial.agent_summary !== null || initial.agent_usage_notes !== null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave({
          agent_summary: summary || null,
          agent_usage_notes: notes || null,
        });
      }}
      className="flex flex-col gap-4"
    >
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Agent summary</span>
        <Textarea
          aria-label="Agent summary"
          placeholder="Short AI-facing description used for matching and search."
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Agent usage notes</span>
        <Textarea
          aria-label="Agent usage notes"
          placeholder="Full free-form guidance for the assistant."
          rows={8}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        {hasExistingRow && onDelete ? (
          <Button type="button" variant="destructive" onClick={onDelete}>
            Delete metadata
          </Button>
        ) : null}
        <Button type="submit">Save</Button>
      </div>
    </form>
  );
}
```

- [ ] **Step 17.4: Run tests**

Run: `npm test -- metadata-edit-form`
Expected: all tests PASS.

- [ ] **Step 17.5: Pause for commit**

Proposed message: `feat(frontend): metadata edit form`.

---

## Task 18: Metadata page shell + route + sidebar nav

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx`
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/components-tab.tsx`
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/orphan-badge.tsx`
- Modify: `src/frontend/src/routes.tsx`
- Modify: `src/frontend/src/pages/SettingsPage/index.tsx`

- [ ] **Step 18.1: Create the orphan badge**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/orphan-badge.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";

export function OrphanBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
      <ForwardedIconComponent name="AlertTriangle" className="w-3 h-3" />
      Orphan
    </span>
  );
}
```

- [ ] **Step 18.2: Create the Flows tab**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import useAlertStore from "@/stores/alertStore";
import {
  useListTemplateMetadata,
  useUpsertTemplateMetadata,
  useDeleteTemplateMetadata,
} from "@/controllers/API/queries/metadata";
import { MetadataEditForm } from "./metadata-edit-form";
import type { TemplateMetadataRow } from "@/types/metadata";

export function FlowsTab() {
  const { data: rows = [], isLoading } = useListTemplateMetadata();
  const upsert = useUpsertTemplateMetadata();
  const del = useDeleteTemplateMetadata();
  const [editing, setEditing] = useState<TemplateMetadataRow | null>(null);
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  if (isLoading) return <div>Loading flows…</div>;

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row) => (
        <div
          key={row.flow_id}
          className="flex items-center justify-between border rounded-md p-3"
        >
          <div className="flex flex-col">
            <span className="font-medium">{row.flow_name}</span>
            <span className="text-xs text-muted-foreground">
              {row.metadata ? "has metadata" : "no metadata"}
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => setEditing(row)}>
            {row.metadata ? "Edit" : "Add"}
          </Button>
        </div>
      ))}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogTitle>{editing?.flow_name ?? ""}</DialogTitle>
          {editing ? (
            <MetadataEditForm
              initial={{
                agent_summary: editing.metadata?.agent_summary ?? null,
                agent_usage_notes: editing.metadata?.agent_usage_notes ?? null,
              }}
              onCancel={() => setEditing(null)}
              onSave={(body) =>
                upsert.mutate(
                  { flowId: editing.flow_id, body },
                  {
                    onSuccess: () => {
                      setSuccess({ title: "Flow metadata saved" });
                      setEditing(null);
                    },
                    onError: (e) => setError({ title: "Save failed", list: [String(e)] }),
                  },
                )
              }
              onDelete={
                editing.metadata
                  ? () =>
                      del.mutate(
                        { flowId: editing.flow_id },
                        {
                          onSuccess: () => {
                            setSuccess({ title: "Flow metadata deleted" });
                            setEditing(null);
                          },
                        },
                      )
                  : undefined
              }
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
```

- [ ] **Step 18.3: Create the Components tab**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/components-tab.tsx`:

```tsx
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import useAlertStore from "@/stores/alertStore";
import {
  useListComponentMetadata,
  useUpsertComponentMetadata,
  useDeleteComponentMetadata,
} from "@/controllers/API/queries/metadata";
import { MetadataEditForm } from "./metadata-edit-form";
import { OrphanBadge } from "./orphan-badge";
import type { ComponentMetadataRow } from "@/types/metadata";

export function ComponentsTab() {
  const { data: rows = [], isLoading } = useListComponentMetadata();
  const upsert = useUpsertComponentMetadata();
  const del = useDeleteComponentMetadata();
  const [editing, setEditing] = useState<ComponentMetadataRow | null>(null);
  const [filter, setFilter] = useState("");
  const setSuccess = useAlertStore((s) => s.setSuccessData);

  const visible = useMemo(
    () =>
      rows.filter((r) =>
        (r.component_name + " " + (r.display_name ?? ""))
          .toLowerCase()
          .includes(filter.toLowerCase()),
      ),
    [rows, filter],
  );

  if (isLoading) return <div>Loading components…</div>;

  return (
    <div className="flex flex-col gap-2">
      <input
        className="border rounded-md px-2 py-1 text-sm"
        placeholder="Filter…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {visible.map((row) => (
        <div
          key={row.component_name}
          className="flex items-center justify-between border rounded-md p-3"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">
              {row.display_name ?? row.component_name}
            </span>
            {row.category ? (
              <span className="text-xs text-muted-foreground">({row.category})</span>
            ) : null}
            {row.is_orphan ? <OrphanBadge /> : null}
          </div>
          <div className="flex gap-2">
            {row.is_orphan ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() =>
                  del.mutate(
                    { componentName: row.component_name },
                    { onSuccess: () => setSuccess({ title: "Orphan removed" }) },
                  )
                }
              >
                Remove orphan
              </Button>
            ) : null}
            <Button variant="outline" size="sm" onClick={() => setEditing(row)}>
              {row.metadata ? "Edit" : "Add"}
            </Button>
          </div>
        </div>
      ))}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogTitle>{editing?.display_name ?? editing?.component_name ?? ""}</DialogTitle>
          {editing ? (
            <MetadataEditForm
              initial={{
                agent_summary: editing.metadata?.agent_summary ?? null,
                agent_usage_notes: editing.metadata?.agent_usage_notes ?? null,
              }}
              onCancel={() => setEditing(null)}
              onSave={(body) =>
                upsert.mutate(
                  { componentName: editing.component_name, body },
                  {
                    onSuccess: () => {
                      setSuccess({ title: "Component metadata saved" });
                      setEditing(null);
                    },
                  },
                )
              }
              onDelete={
                editing.metadata
                  ? () =>
                      del.mutate(
                        { componentName: editing.component_name },
                        {
                          onSuccess: () => {
                            setSuccess({ title: "Component metadata deleted" });
                            setEditing(null);
                          },
                        },
                      )
                  : undefined
              }
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
```

- [ ] **Step 18.4: Create the page shell with tabs**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx`:

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FlowsTab } from "./flows-tab";
import { ComponentsTab } from "./components-tab";

export default function MetadataPage() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Flow and Component Management</h1>
      <Tabs defaultValue="flows">
        <TabsList>
          <TabsTrigger value="flows">Flows</TabsTrigger>
          <TabsTrigger value="components">Components</TabsTrigger>
        </TabsList>
        <TabsContent value="flows">
          <FlowsTab />
        </TabsContent>
        <TabsContent value="components">
          <ComponentsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 18.5: Register the route**

Edit `src/frontend/src/routes.tsx` — add inside the `path="settings"` route block, next to the other settings routes:

```tsx
<Route
  path="metadata"
  element={
    <ProtectedSuperuserRoute>
      <MetadataPage />
    </ProtectedSuperuserRoute>
  }
/>
```

Add the two imports at the top:

```tsx
import MetadataPage from "@/pages/SettingsPage/pages/MetadataPage";
import { ProtectedSuperuserRoute } from "@/components/authorization/authSuperuserGuard";
```

- [ ] **Step 18.6: Add sidebar nav entry**

Edit `src/frontend/src/pages/SettingsPage/index.tsx` — in the `sidebarNavItems.push(...)` block, add:

```tsx
{
  title: "Flow and Component Management",
  href: "/settings/metadata",
  icon: (
    <ForwardedIconComponent
      name="Database"
      className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
    />
  ),
},
```

(Optionally wrap in `if (userData?.is_superuser) { sidebarNavItems.push({ ... }); }` so non-superusers don't even see the link — cleaner UX.)

- [ ] **Step 18.7: Run frontend type-check**

Run: `npm run typecheck` (or `npx tsc --noEmit` if no script exists)
Expected: no errors in the new files.

- [ ] **Step 18.8: Run frontend tests**

Run: `npm test`
Expected: all tests including `metadata-edit-form.test.tsx` PASS.

- [ ] **Step 18.9: Pause for commit**

Proposed message: `feat(frontend): Flow and Component Management admin page`.

---

## Task 19: Frontend test for components tab orphan behavior

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/components-tab.test.tsx`

- [ ] **Step 19.1: Write the test**

Create the test file:

```tsx
import { render, screen } from "@testing-library/react";
import { ComponentsTab } from "../components-tab";

jest.mock("@/controllers/API/queries/metadata", () => ({
  useListComponentMetadata: () => ({
    data: [
      {
        component_name: "Webhook",
        display_name: "Webhook",
        category: "input_output",
        icon: "webhook",
        is_orphan: false,
        metadata: null,
      },
      {
        component_name: "StaleComponent",
        display_name: null,
        category: null,
        icon: null,
        is_orphan: true,
        metadata: {
          agent_summary: "Old",
          agent_usage_notes: null,
          updated_by: "user-1",
          updated_at: "2026-04-18T00:00:00Z",
        },
      },
    ],
    isLoading: false,
  }),
  useUpsertComponentMetadata: () => ({ mutate: jest.fn() }),
  useDeleteComponentMetadata: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ setSuccessData: jest.fn(), setErrorData: jest.fn() }),
}));

describe("ComponentsTab", () => {
  it("renders live components without orphan badge, orphans with badge", () => {
    render(<ComponentsTab />);
    expect(screen.getByText("Webhook")).toBeInTheDocument();
    expect(screen.getByText("StaleComponent")).toBeInTheDocument();
    expect(screen.getAllByText(/orphan/i)).toHaveLength(1);
    expect(screen.getByRole("button", { name: /remove orphan/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 19.2: Run to verify pass**

Run: `npm test -- components-tab`
Expected: PASS.

- [ ] **Step 19.3: Pause for commit**

Proposed message: `test(frontend): components tab orphan rendering`.

---

## Task 20: End-to-end manual verification

After all automated tests pass, walk through this checklist. **Do not commit in this task** — it's a validation gate.

- [ ] **Step 20.1: Dev server boots**

Start both backend and frontend using your normal dev command. Confirm no import or migration errors.

- [ ] **Step 20.2: Superuser route access**

Log in as a user with `is_superuser=True`. Navigate to `/settings/metadata`. Confirm:
- Page renders with title "Flow and Component Management"
- Two tabs visible: **Flows** and **Components**
- Flows tab lists starter-project flows only
- Components tab lists every component from the live catalog plus any rows previously authored

- [ ] **Step 20.3: Non-superuser is blocked**

Log in as a non-superuser. Navigate to `/settings/metadata`. Confirm:
- Redirected away from the page (to `/`)
- Sidebar nav entry is hidden (if the superuser-gate was added per Task 18.6)

Hit `GET /api/v1/admin/metadata/templates` with a non-superuser token directly — expect HTTP 403.

- [ ] **Step 20.4: Template metadata round-trip**

In the Flows tab, click **Add** on a starter-project flow. Fill both textareas. Click **Save**. Confirm:
- Success toast appears
- List row updates to show "has metadata"
- Reopening the row shows the saved values
- Clicking **Delete metadata** removes the row and the list flips back to "no metadata"

- [ ] **Step 20.5: Component metadata round-trip**

Same round-trip on the Components tab (e.g., for `Webhook`).

- [ ] **Step 20.6: Orphan creation + removal**

In the Components tab, use the filter box and the UI flow described in Task 18.3 to author metadata for a made-up name (e.g., `"UpcomingFeatureComponent"`). Confirm it appears with the orphan badge and a **Remove orphan** button. Click it; row goes away.

- [ ] **Step 20.7: System-prompt injection**

Author metadata for at least one starter template. Start a new ADP Assist conversation. Inspect the debug log (or add a print statement temporarily — remove before commit) for the assembled system prompt. Confirm the `## Available Templates` section lists the template with its summary.

- [ ] **Step 20.8: `get_template_instructions` tool end-to-end**

In the same conversation, prompt the LLM: "Use the [Template Name] template." Confirm the LLM calls `get_template_instructions(flow_id=...)` and the result contains the full `agent_usage_notes` you authored.

- [ ] **Step 20.9: Component metadata in catalog tools**

Author metadata for `Webhook`. In the assistant conversation, ask: "What components do we have for receiving webhooks?" Confirm the LLM's reasoning references the `agent_summary` you authored (either in its reply or via a tool-call trace).

- [ ] **Step 20.10: Flow delete cascades metadata**

Delete a starter-project flow via the existing UI. Inspect the `template_metadata` table directly (e.g., `psql` or `sqlite3`) — the row for that flow should be gone.

- [ ] **Step 20.11: Report findings**

Summarize the manual verification (pass/fail per step) back to the user. Do not mark the overall plan complete until every step passes.

---

## Acceptance Criteria

The plan is complete when:

1. All pytest backend tests in `src/backend/tests/unit/services/database/models/test_template_metadata_model.py`, `test_component_metadata_model.py`, `test_flow_starter_helper.py`, `src/backend/tests/unit/api/v1/test_admin_template_metadata_api.py`, `test_admin_component_metadata_api.py`, and `src/backend/tests/unit/services/assistant/tools/test_catalog_merges_metadata.py`, `test_get_template_instructions_tool.py`, `test_template_prompt_block.py` pass.
2. All Jest frontend tests (new + existing) pass via `npm test`.
3. `npm run typecheck` (or equivalent) is clean for new files.
4. Alembic migration applies and rolls back cleanly (`make alembic-upgrade` / `make alembic-downgrade`).
5. Manual verification (Task 20) passes end-to-end.
6. No changes to the ADP Trigger plan (`2026-04-18-adp-trigger.md`) or to unrelated components.
7. Every commit in this plan was explicitly approved by the user per the no-auto-commit rule.

## Out of Scope

- Org-scoped metadata — reserved for a future additive `organization_id` nullable column.
- Versioning / audit log beyond `updated_by` / `updated_at`.
- Bulk edit, import/export, markdown preview.
- TTL caching on the catalog merge.
- Metadata injection into `list_categories` or `list_compatible_outputs`.
- Any ADP Trigger, assistant-fullscreen, or pipeline-view changes.

## Open Items Flagged During Implementation

- **Session context manager name** (`session_getter` vs `get_session` vs `session_scope`) — resolve in Task 9 by grep; the plan's code uses `session_getter` as a placeholder.
- **Starter folder name constant** — resolve in Task 5 by grep; `"Starter Projects"` used as a reasonable default based on test conftest references.
- **Existing mutate/query hook signature** in `UseRequestProcessor()` — Task 15/16 match a representative existing hook. If the local signature differs, pattern-match it.
- **Dispatch dict name** in `services/assistant/tools/registry.py` — resolve in Task 10 by reading the file and following the existing pattern for `search_components`.
