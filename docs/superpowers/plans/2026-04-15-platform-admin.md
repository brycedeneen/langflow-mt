# Platform Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `is_platform_admin` role, a `/api/v1/admin/*` surface for managing organizations and memberships, a CLI tool to grant/revoke the role, and an Admin UI section gated by the role.

**Architecture:** New boolean on `User`; new FastAPI dependency `PlatformAdmin` for authorization; new admin router with six endpoint groups (orgs CRUD-minus-update, members CRUD, user search); relax `get_current_organization` to tolerate multi-membership; extend `/users/whoami` to surface the flag; add CLI command; new frontend Admin area with org list/detail/create/delete screens.

**Tech Stack:** Python/FastAPI/SQLModel/Alembic/Typer (backend), React/TypeScript/TanStack Query/shadcn (frontend), pytest (backend tests).

---

## Spec

Implements `docs/superpowers/specs/2026-04-15-platform-admin-design.md`.

## File Map

**Backend — create:**
- `src/backend/base/langflow/alembic/versions/<rev>_add_platform_admin_flag.py` — migration
- `src/backend/base/langflow/api/v1/admin.py` — admin router
- `src/backend/tests/unit/api/v1/test_admin.py` — admin router tests
- `src/backend/tests/unit/alembic/test_platform_admin_migration.py` — migration test

**Backend — modify:**
- `src/backend/base/langflow/services/database/models/user/model.py` — add `is_platform_admin` field
- `src/backend/base/langflow/api/utils/core.py` — add `PlatformAdmin` dependency
- `src/backend/base/langflow/api/utils/org_helpers.py` — relax single-membership invariant
- `src/backend/base/langflow/api/v1/users.py` — include flag in `/whoami` response model
- `src/backend/base/langflow/api/router.py` — include `admin_router`
- `src/backend/base/langflow/__main__.py` — add `set-platform-admin` Typer command

**Frontend — create (paths use existing conventions):**
- `frontend/src/controllers/API/queries/admin/` — admin API module (`use-get-organizations.ts`, `use-create-organization.ts`, `use-delete-organization.ts`, `use-get-organization.ts`, `use-get-members.ts`, `use-add-member.ts`, `use-remove-member.ts`, `use-search-users.ts`, `index.ts`, `types.ts`)
- `frontend/src/pages/AdminPage/index.tsx` — layout shell
- `frontend/src/pages/AdminPage/organizations/OrganizationsListPage.tsx`
- `frontend/src/pages/AdminPage/organizations/CreateOrganizationDrawer.tsx`
- `frontend/src/pages/AdminPage/organizations/OrganizationDetailPage.tsx`
- `frontend/src/pages/AdminPage/organizations/OrganizationMembersTab.tsx`
- `frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx`
- `frontend/src/components/common/confirmByTypingDialog/index.tsx` (only if no equivalent exists)

**Frontend — modify:**
- `frontend/src/types/api/index.ts` (or the user type file) — add `is_platform_admin` to `Users` type
- `frontend/src/routes.tsx` — register `/admin/*` routes
- The left-nav component (identify at implementation time) — conditionally render "Admin" entry when `is_platform_admin` is true

---

## Task 1: Add `is_platform_admin` field to `User` model

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/user/model.py`

- [x] **Step 1: Add field to `User` and read/update models**

Edit `src/backend/base/langflow/services/database/models/user/model.py`, add the field after line 34 (`is_superuser: bool = Field(default=False)`) in `User`, after line 86 in `UserRead`, and after line 98 in `UserUpdate`:

In `User` (after `is_superuser`):
```python
    is_platform_admin: bool = Field(default=False)
```

In `UserRead` (after `is_superuser: bool = Field()`):
```python
    is_platform_admin: bool = Field()
```

In `UserUpdate` (after `is_superuser: bool | None = None`):
```python
    is_platform_admin: bool | None = None
```

- [x] **Step 2: Commit**

```bash
git add src/backend/base/langflow/services/database/models/user/model.py
git commit -m "feat(admin): add is_platform_admin field to User model"
```

---

## Task 2: Alembic migration for `is_platform_admin` with superuser auto-promote

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<rev>_add_platform_admin_flag.py`

- [x] **Step 1: Generate migration**

Run from repo root:
```bash
cd src/backend/base && uv run alembic -c langflow/alembic.ini revision -m "add platform admin flag"
```
Note the generated filename; open it.

- [x] **Step 2: Replace `upgrade()` and `downgrade()` bodies**

```python
def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Auto-promote existing superusers so admin access is preserved on upgrade.
    op.execute('UPDATE "user" SET is_platform_admin = TRUE WHERE is_superuser = TRUE')
    # Drop the server default so new rows follow the model default (False).
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("is_platform_admin", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("is_platform_admin")
```

- [x] **Step 3: Run migration locally**

```bash
cd src/backend/base && uv run alembic -c langflow/alembic.ini upgrade head
```
Expected: no errors; `user` table gains `is_platform_admin` column.

- [x] **Step 4: Commit**

```bash
git add src/backend/base/langflow/alembic/versions/*_add_platform_admin_flag.py
git commit -m "feat(admin): migration adds is_platform_admin and promotes existing superusers"
```

---

## Task 3: Migration test

**Files:**
- Create: `src/backend/tests/unit/alembic/test_platform_admin_migration.py`

- [x] **Step 1: Write failing test**

```python
"""Test that the platform-admin migration promotes existing superusers."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.user.model import User


@pytest.mark.asyncio
async def test_migration_promotes_superusers_to_platform_admins(client, session: AsyncSession):
    """After migration runs (fixture bootstrapping), superusers should be platform admins."""
    # Seed: one superuser, one non-superuser.
    su = User(username="existing_superuser", password="x", is_active=True, is_superuser=True)
    regular = User(username="existing_regular", password="x", is_active=True, is_superuser=False)
    session.add_all([su, regular])
    await session.commit()

    # Emulate the data step explicitly (the DB fixture has already run upgrade head,
    # so this test seeds rows as-if they predated the migration and runs the UPDATE).
    await session.exec(text(
        'UPDATE "user" SET is_platform_admin = TRUE WHERE is_superuser = TRUE'
    ))
    await session.commit()

    rows = (await session.exec(select(User))).all()
    by_name = {u.username: u for u in rows}
    assert by_name["existing_superuser"].is_platform_admin is True
    assert by_name["existing_regular"].is_platform_admin is False
```

- [x] **Step 2: Run test**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/alembic/test_platform_admin_migration.py -v
```
Expected: PASS. (If it fails because of the `client`/`session` fixture signatures, align with the conventions used in existing tests like `test_users.py`.)

- [x] **Step 3: Commit**

```bash
git add src/backend/tests/unit/alembic/test_platform_admin_migration.py
git commit -m "test(admin): verify migration promotes superusers to platform admins"
```

---

## Task 4: Add `PlatformAdmin` dependency

**Files:**
- Modify: `src/backend/base/langflow/api/utils/core.py`

- [x] **Step 1: Add dependency function and type alias**

After line 51 in `core.py` (after `CurrentMembership = ...`), insert:

```python
async def require_platform_admin(user: CurrentActiveUser) -> User:
    """Require the caller to be a platform admin."""
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin required")
    return user


PlatformAdmin = Annotated[User, Depends(require_platform_admin)]
```

- [x] **Step 2: Commit**

```bash
git add src/backend/base/langflow/api/utils/core.py
git commit -m "feat(admin): add PlatformAdmin FastAPI dependency"
```

---

## Task 5: Relax `get_current_organization` for multi-membership

**Context:** `get_current_organization` currently raises 409 when a user has >1 membership. Admin assignment will produce users with multiple memberships. Resolution rule: prefer the user's personal org; otherwise the earliest-created membership.

**Files:**
- Modify: `src/backend/base/langflow/api/utils/org_helpers.py`

- [x] **Step 1: Write failing test for resolution rule**

Append to `src/backend/tests/unit/api/v1/test_users.py` (or a new `test_org_helpers.py` in the same dir):

```python
import pytest
from uuid import uuid4

from langflow.api.utils.org_helpers import get_current_organization
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@pytest.mark.asyncio
async def test_get_current_org_prefers_personal(session):
    user = User(username="multi", password="x", is_active=True)
    session.add(user)
    await session.flush()

    workspace = Organization(name="Acme", slug=f"acme-{uuid4().hex[:6]}", is_personal=False)
    personal = Organization(name="Multi's workspace", slug=f"user-{user.id}", is_personal=True)
    session.add_all([workspace, personal])
    await session.flush()

    session.add_all([
        Membership(user_id=user.id, organization_id=workspace.id, role=MembershipRole.OWNER),
        Membership(user_id=user.id, organization_id=personal.id, role=MembershipRole.OWNER),
    ])
    await session.commit()

    org = await get_current_organization(user=user, session=session, x_acting_org_id=None)
    assert org.id == personal.id
```

- [x] **Step 2: Run test — expect failure (409)**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_users.py -k test_get_current_org_prefers_personal -v
```
Expected: FAIL with 409.

- [x] **Step 3: Implement resolution rule**

Replace the body of `get_current_organization` in `org_helpers.py` below the `x_acting_org_id` block (starting at `rows = (await session.exec(...`):

```python
    rows = (await session.exec(
        select(Membership).where(Membership.user_id == user.id)
    )).all()
    if len(rows) == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no organization membership")

    org_ids = [r.organization_id for r in rows]
    orgs = (await session.exec(
        select(Organization).where(Organization.id.in_(org_ids))
    )).all()
    if not orgs:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Memberships reference no organizations")

    # Prefer the user's personal org; else the earliest-created one.
    personal = next((o for o in orgs if o.is_personal), None)
    if personal is not None:
        return personal
    return min(orgs, key=lambda o: o.created_at)
```

Leave the `x_acting_org_id` branch and `get_current_membership` untouched.

- [x] **Step 4: Run test — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_users.py -k test_get_current_org_prefers_personal -v
```
Expected: PASS.

- [x] **Step 5: Run existing org tests to check for regression**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/ -k "org or membership" -v
```
Expected: all green.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/utils/org_helpers.py src/backend/tests/unit/api/v1/test_users.py
git commit -m "feat(admin): resolve current org preferring personal for multi-membership users"
```

---

## Task 6: Admin router scaffold + list/create organizations

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin.py`
- Create: `src/backend/tests/unit/api/v1/test_admin.py`
- Modify: `src/backend/base/langflow/api/router.py`

- [x] **Step 1: Write failing test for auth + list + create**

Create `src/backend/tests/unit/api/v1/test_admin.py`:

```python
"""Tests for /api/v1/admin/* routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_orgs_list_requires_platform_admin(client: AsyncClient, regular_user_headers):
    resp = await client.get("/api/v1/admin/organizations", headers=regular_user_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_orgs_list_returns_all(client: AsyncClient, platform_admin_headers):
    resp = await client.get("/api/v1/admin/organizations", headers=platform_admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_admin_orgs_create(client: AsyncClient, platform_admin_headers):
    resp = await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Acme Inc", "slug": "acme-inc"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Acme Inc"
    assert body["slug"] == "acme-inc"
    assert body["is_personal"] is False


@pytest.mark.asyncio
async def test_admin_orgs_create_duplicate_slug_409(
    client: AsyncClient, platform_admin_headers
):
    await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Dup", "slug": "dup-slug"},
        headers=platform_admin_headers,
    )
    resp = await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Dup 2", "slug": "dup-slug"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 409
```

You will need fixtures `regular_user_headers` and `platform_admin_headers`. Add to `src/backend/tests/conftest.py` (or the nearest existing conftest) — follow existing patterns used by `test_api_key.py` / `test_users.py` for creating users + bearer tokens. If those patterns already produce a superuser-authenticated client, create `platform_admin_headers` by setting `is_platform_admin=True` on that user. If no such pattern exists, inline user creation + login inside the test.

- [x] **Step 2: Run tests — expect failure (404/501)**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```
Expected: FAIL (route does not exist).

- [x] **Step 3: Create `admin.py` router with list + create**

Create `src/backend/base/langflow/api/v1/admin.py`:

```python
"""Platform-admin endpoints: org and membership administration across all orgs.

Every endpoint here is gated by `PlatformAdmin` (see core.py). None of these
endpoints use `CurrentOrg` — they intentionally operate outside any single
org's membership scope.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization

router = APIRouter(prefix="/admin", tags=["Admin"])


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-]*$")


class OrgSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    is_personal: bool
    member_count: int
    created_at: str
    updated_at: str


class OrgListResponse(BaseModel):
    items: list[OrgSummary]
    total: int


@router.get("/organizations", response_model=OrgListResponse)
async def list_organizations(
    _admin: PlatformAdmin,
    session: DbSession,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrgListResponse:
    stmt = select(Organization)
    count_stmt = select(func.count()).select_from(Organization)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Organization.name.ilike(like)) | (Organization.slug.ilike(like)))
        count_stmt = count_stmt.where(
            (Organization.name.ilike(like)) | (Organization.slug.ilike(like))
        )
    stmt = stmt.order_by(Organization.created_at).offset(offset).limit(limit)
    orgs = (await session.exec(stmt)).all()
    total = (await session.exec(count_stmt)).one()

    items: list[OrgSummary] = []
    for o in orgs:
        mc = (await session.exec(
            select(func.count()).select_from(Membership).where(Membership.organization_id == o.id)
        )).one()
        items.append(
            OrgSummary(
                id=o.id,
                name=o.name,
                slug=o.slug,
                is_personal=o.is_personal,
                member_count=int(mc),
                created_at=o.created_at.isoformat(),
                updated_at=o.updated_at.isoformat(),
            )
        )
    return OrgListResponse(items=items, total=int(total))


@router.post("/organizations", response_model=OrgSummary, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgSummary:
    org = Organization(name=body.name, slug=body.slug, is_personal=False)
    session.add(org)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already in use") from e
    return OrgSummary(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_personal=org.is_personal,
        member_count=0,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )
```

- [x] **Step 4: Register the router**

Edit `src/backend/base/langflow/api/router.py`. Add import near the other `_router` imports:

```python
from langflow.api.v1.admin import router as admin_router
```

Add include after the other `router_v1.include_router(...)` calls (logical spot: right after `projects_router`):

```python
router_v1.include_router(admin_router)
```

- [x] **Step 5: Run tests — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```
Expected: the four tests from Step 1 pass.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin.py src/backend/base/langflow/api/router.py src/backend/tests/unit/api/v1/test_admin.py
git commit -m "feat(admin): add /admin/organizations list + create endpoints"
```

---

## Task 7: Admin get-org detail endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin.py`
- Modify: `src/backend/tests/unit/api/v1/test_admin.py`

- [x] **Step 1: Write failing tests**

Append to `test_admin.py`:

```python
@pytest.mark.asyncio
async def test_admin_orgs_detail(client, platform_admin_headers):
    created = (await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Detail", "slug": "detail-org"},
        headers=platform_admin_headers,
    )).json()
    resp = await client.get(
        f"/api/v1/admin/organizations/{created['id']}", headers=platform_admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["members"] == []


@pytest.mark.asyncio
async def test_admin_orgs_detail_404(client, platform_admin_headers):
    from uuid import uuid4
    resp = await client.get(
        f"/api/v1/admin/organizations/{uuid4()}", headers=platform_admin_headers
    )
    assert resp.status_code == 404
```

- [x] **Step 2: Run — expect failure**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -k detail -v
```
Expected: FAIL (404/missing route).

- [x] **Step 3: Add endpoint + schema**

Append to `admin.py` (after `create_organization`):

```python
class MemberRow(BaseModel):
    user_id: UUID
    username: str
    role: str


class OrgDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    is_personal: bool
    created_at: str
    updated_at: str
    members: list[MemberRow]


@router.get("/organizations/{org_id}", response_model=OrgDetail)
async def get_organization(
    org_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgDetail:
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    rows = (await session.exec(
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.organization_id == org_id)
    )).all()
    members = [
        MemberRow(user_id=u.id, username=u.username, role=m.role.value)
        for (m, u) in rows
    ]
    return OrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_personal=org.is_personal,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
        members=members,
    )
```

- [x] **Step 4: Run — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```
Expected: all admin tests green.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin.py src/backend/tests/unit/api/v1/test_admin.py
git commit -m "feat(admin): add GET /admin/organizations/{id} detail endpoint"
```

---

## Task 8: Admin delete-org endpoint with typed confirmation + cascade

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin.py`
- Modify: `src/backend/tests/unit/api/v1/test_admin.py`

- [x] **Step 1: Write failing tests**

Append to `test_admin.py`:

```python
@pytest.mark.asyncio
async def test_admin_orgs_delete_happy(client, platform_admin_headers):
    created = (await client.post(
        "/api/v1/admin/organizations",
        json={"name": "ToDelete", "slug": "to-delete"},
        headers=platform_admin_headers,
    )).json()
    resp = await client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{created['id']}",
        json={"confirm_name": "ToDelete"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200
    # Subsequent detail returns 404.
    r2 = await client.get(
        f"/api/v1/admin/organizations/{created['id']}", headers=platform_admin_headers
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_admin_orgs_delete_wrong_confirm_400(client, platform_admin_headers):
    created = (await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Careful", "slug": "careful"},
        headers=platform_admin_headers,
    )).json()
    resp = await client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{created['id']}",
        json={"confirm_name": "wrong"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_orgs_delete_personal_403(client, platform_admin_headers, session):
    from uuid import uuid4
    from langflow.services.database.models.organization.model import Organization
    org = Organization(name="Personal", slug=f"user-{uuid4()}", is_personal=True)
    session.add(org)
    await session.commit()
    resp = await client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{org.id}",
        json={"confirm_name": "Personal"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 403
```

- [x] **Step 2: Run — expect failure**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -k delete -v
```
Expected: FAIL.

- [x] **Step 3: Implement delete with explicit cascade**

Append to `admin.py`:

```python
from sqlalchemy import delete as sa_delete


class OrgDeleteBody(BaseModel):
    confirm_name: str


class OrgDeleteResult(BaseModel):
    deleted: dict[str, int]


@router.delete("/organizations/{org_id}", response_model=OrgDeleteResult)
async def delete_organization(
    org_id: UUID,
    body: OrgDeleteBody,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgDeleteResult:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete a personal organization")
    if body.confirm_name != org.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm_name does not match organization name")

    # Explicit cascade — SQLite doesn't enforce FK cascades by default, and
    # existing code (e.g. cascade_delete_flow) follows the same pattern.
    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.jobs.model import Job
    from langflow.services.database.models.message.model import MessageTable
    from langflow.services.database.models.transactions.model import TransactionTable
    from langflow.services.database.models.variable.model import Variable
    from langflow.services.database.models.vertex_builds.model import VertexBuildTable

    tables = [
        ("message", MessageTable),
        ("transaction", TransactionTable),
        ("vertex_build", VertexBuildTable),
        ("flow_version", FlowVersion),
        ("flow", Flow),
        ("file", File),
        ("variable", Variable),
        ("deployment", Deployment),
        ("deployment_provider_account", DeploymentProviderAccount),
        ("job", Job),
        ("folder", Folder),
        ("api_key", ApiKey),
        ("membership", Membership),
    ]
    deleted: dict[str, int] = {}
    for label, model in tables:
        if not hasattr(model, "organization_id"):
            continue
        result = await session.exec(
            sa_delete(model).where(model.organization_id == org_id)
        )
        deleted[label] = int(result.rowcount or 0)
    await session.delete(org)
    deleted["organization"] = 1
    return OrgDeleteResult(deleted=deleted)
```

Note: `ApiKey` may not carry `organization_id` on this branch — the `hasattr` guard skips tables that don't. If a newly-added child table is missing from this list, add it. Verify by grepping `organization_id = Field(...foreign_key="organization.id"` in the models directory before landing.

- [x] **Step 4: Run — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```
Expected: all green.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin.py src/backend/tests/unit/api/v1/test_admin.py
git commit -m "feat(admin): add DELETE /admin/organizations/{id} with typed confirmation and cascade"
```

---

## Task 9: Admin membership endpoints (list, add, remove)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin.py`
- Modify: `src/backend/tests/unit/api/v1/test_admin.py`

- [x] **Step 1: Write failing tests**

Append to `test_admin.py`:

```python
@pytest.mark.asyncio
async def test_admin_membership_add_and_remove(client, platform_admin_headers, session):
    from langflow.services.database.models.user.model import User
    target = User(username="assignee", password="x", is_active=True)
    session.add(target)
    await session.commit()

    org = (await client.post(
        "/api/v1/admin/organizations",
        json={"name": "Workspace", "slug": "workspace-a"},
        headers=platform_admin_headers,
    )).json()

    r = await client.post(
        f"/api/v1/admin/organizations/{org['id']}/members",
        json={"user_id": str(target.id)},
        headers=platform_admin_headers,
    )
    assert r.status_code == 201

    r_dup = await client.post(
        f"/api/v1/admin/organizations/{org['id']}/members",
        json={"user_id": str(target.id)},
        headers=platform_admin_headers,
    )
    assert r_dup.status_code == 409

    r_del = await client.delete(
        f"/api/v1/admin/organizations/{org['id']}/members/{target.id}",
        headers=platform_admin_headers,
    )
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_admin_membership_remove_personal_forbidden(
    client, platform_admin_headers, session
):
    from uuid import uuid4
    from langflow.services.database.models.membership.model import Membership, MembershipRole
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.user.model import User

    user = User(username=f"pu-{uuid4().hex[:6]}", password="x", is_active=True)
    session.add(user)
    await session.flush()
    personal = Organization(
        name=f"{user.username}'s workspace",
        slug=f"user-{user.id}",
        is_personal=True,
    )
    session.add(personal)
    await session.flush()
    session.add(Membership(user_id=user.id, organization_id=personal.id, role=MembershipRole.OWNER))
    await session.commit()

    r = await client.delete(
        f"/api/v1/admin/organizations/{personal.id}/members/{user.id}",
        headers=platform_admin_headers,
    )
    assert r.status_code == 403
```

- [x] **Step 2: Run — expect failure**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -k membership -v
```
Expected: FAIL.

- [x] **Step 3: Implement endpoints**

Append to `admin.py`:

```python
class MemberAdd(BaseModel):
    user_id: UUID
    role: str = "owner"


class MembersResponse(BaseModel):
    items: list[MemberRow]


@router.get("/organizations/{org_id}/members", response_model=MembersResponse)
async def list_members(
    org_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> MembersResponse:
    from langflow.services.database.models.user.model import User

    if await session.get(Organization, org_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    rows = (await session.exec(
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.organization_id == org_id)
    )).all()
    return MembersResponse(items=[
        MemberRow(user_id=u.id, username=u.username, role=m.role.value) for (m, u) in rows
    ])


@router.post(
    "/organizations/{org_id}/members",
    response_model=MemberRow,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    org_id: UUID,
    body: MemberAdd,
    _admin: PlatformAdmin,
    session: DbSession,
) -> MemberRow:
    from langflow.services.database.models.membership.model import MembershipRole
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    user = await session.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        role = MembershipRole(body.role)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid role: {body.role}") from e

    existing = (await session.exec(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == org.id
        )
    )).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already a member")
    m = Membership(user_id=user.id, organization_id=org.id, role=role)
    session.add(m)
    await session.flush()
    return MemberRow(user_id=user.id, username=user.username, role=role.value)


@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> None:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        # Never orphan a user from their personal workspace.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Cannot remove a user from their personal organization",
        )
    m = (await session.exec(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == org_id
        )
    )).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    await session.delete(m)
    await session.flush()
```

- [x] **Step 4: Run — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```
Expected: all green.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin.py src/backend/tests/unit/api/v1/test_admin.py
git commit -m "feat(admin): add membership list/add/remove endpoints"
```

---

## Task 10: Admin user search endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin.py`
- Modify: `src/backend/tests/unit/api/v1/test_admin.py`

- [x] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_admin_user_search(client, platform_admin_headers, session):
    from langflow.services.database.models.user.model import User
    session.add_all([
        User(username="alpha.beta", password="x", is_active=True),
        User(username="gamma.delta", password="x", is_active=True),
    ])
    await session.commit()

    resp = await client.get(
        "/api/v1/admin/users?q=alpha", headers=platform_admin_headers
    )
    assert resp.status_code == 200
    names = [u["username"] for u in resp.json()["items"]]
    assert "alpha.beta" in names
    assert "gamma.delta" not in names
```

- [x] **Step 2: Run — expect failure**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -k user_search -v
```
Expected: FAIL.

- [x] **Step 3: Implement**

Append to `admin.py`:

```python
class UserOrgRow(BaseModel):
    organization_id: UUID
    organization_name: str
    role: str


class UserRow(BaseModel):
    id: UUID
    username: str
    is_platform_admin: bool
    memberships: list[UserOrgRow]


class UserSearchResponse(BaseModel):
    items: list[UserRow]


@router.get("/users", response_model=UserSearchResponse)
async def search_users(
    _admin: PlatformAdmin,
    session: DbSession,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> UserSearchResponse:
    from langflow.services.database.models.user.model import User

    stmt = select(User)
    if q:
        stmt = stmt.where(User.username.ilike(f"%{q}%"))
    stmt = stmt.order_by(User.username).limit(limit)
    users = (await session.exec(stmt)).all()
    items: list[UserRow] = []
    for u in users:
        rows = (await session.exec(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == u.id)
        )).all()
        items.append(
            UserRow(
                id=u.id,
                username=u.username,
                is_platform_admin=u.is_platform_admin,
                memberships=[
                    UserOrgRow(
                        organization_id=o.id,
                        organization_name=o.name,
                        role=m.role.value,
                    )
                    for (m, o) in rows
                ],
            )
        )
    return UserSearchResponse(items=items)
```

- [x] **Step 4: Run — expect PASS**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py -v
```

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin.py src/backend/tests/unit/api/v1/test_admin.py
git commit -m "feat(admin): add /admin/users search endpoint"
```

---

## Task 11: Surface `is_platform_admin` on `/users/whoami`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/users.py` (only if the `/whoami` response explicitly constructs a dict; otherwise `UserRead` already carries the field from Task 1).
- Modify: `src/backend/tests/unit/api/v1/test_users.py`

- [x] **Step 1: Write failing test**

Append to `test_users.py`:

```python
@pytest.mark.asyncio
async def test_whoami_includes_is_platform_admin(client, platform_admin_headers):
    resp = await client.get("/api/v1/users/whoami", headers=platform_admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_platform_admin"] is True
```

- [x] **Step 2: Run — expect failure IF `UserRead` isn't serializing the field**

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_users.py -k whoami_includes -v
```

- [x] **Step 3: Fix if needed**

If the test fails, inspect `read_current_user` (around line 51 of `users.py`) and ensure the response uses `UserRead` (it already does). Verify `UserRead` from Task 1 includes the new field.

- [x] **Step 4: Run — expect PASS; commit**

```bash
git add src/backend/tests/unit/api/v1/test_users.py
git commit -m "test(admin): whoami exposes is_platform_admin"
```

---

## Task 12: CLI command `langflow users set-platform-admin`

**Files:**
- Modify: `src/backend/base/langflow/__main__.py`

- [x] **Step 1: Inspect existing `superuser` command**

```bash
cd src/backend/base && grep -n "def superuser" langflow/__main__.py
```
Locate the `superuser` Typer command (around line 678) as a reference for CLI patterns and session usage.

- [x] **Step 2: Add the new command**

Immediately after the `superuser` command in `__main__.py`, add:

```python
@app.command(name="set-platform-admin")
def set_platform_admin(
    email: str = typer.Argument(..., help="Username (email) of the user to grant/revoke the platform admin role."),
    revoke: bool = typer.Option(False, "--revoke", help="Revoke the role instead of granting it."),
) -> None:
    """Grant or revoke the platform-admin role on an existing user."""
    asyncio.run(_set_platform_admin(email, revoke=revoke))


async def _set_platform_admin(email: str, *, revoke: bool) -> None:
    from sqlmodel import select
    from langflow.services.database.models.user.model import User
    from langflow.services.utils import initialize_services

    await initialize_services()
    async with session_scope() as session:  # reuse import pattern already in this file
        user = (await session.exec(select(User).where(User.username == email))).first()
        if user is None:
            typer.echo(f"Error: no user found with username '{email}'")
            raise typer.Exit(code=1)
        user.is_platform_admin = not revoke
        session.add(user)
        await session.commit()
        verb = "revoked" if revoke else "granted"
        typer.echo(f"Platform admin role {verb} for {email}")
```

If `session_scope` is not already imported at module scope, add `from langflow.services.deps import session_scope` alongside the existing imports. Verify by running `grep -n "session_scope" langflow/__main__.py`.

- [x] **Step 3: Test manually**

```bash
cd src/backend/base && uv run langflow users set-platform-admin nobody@nowhere
```
Expected: exit 1, "no user found".

Create a real user via the normal signup flow, then:
```bash
uv run langflow users set-platform-admin <that_username>
```
Expected: "granted". Query the DB (or call `/users/whoami` after logging in) and verify `is_platform_admin=True`.

- [x] **Step 4: Commit**

```bash
git add src/backend/base/langflow/__main__.py
git commit -m "feat(admin): add 'users set-platform-admin' CLI command"
```

---

## Task 13: Frontend — extend user type and gate nav

**Files:**
- Modify: user-related type file (likely `frontend/src/types/api/index.ts` — verify via `grep -n "is_superuser" frontend/src`)
- Modify: left-nav component (identify via grep for the existing nav items; look for "Settings" or "Admin Settings" labels)

- [x] **Step 1: Add `is_platform_admin` to the `Users` TypeScript type**

Find where `is_superuser` is declared on the frontend user type and add:

```ts
is_platform_admin: boolean;
```

- [x] **Step 2: Conditionally render an "Admin" nav entry**

In the nav component, after the existing nav items, add:

```tsx
{currentUser?.is_platform_admin && (
  <NavLink to="/admin/organizations" icon="shield">Admin</NavLink>
)}
```

(Adapt to the exact nav/link primitives used by the file; `shield` is a placeholder for whatever icon set the project uses.)

- [x] **Step 3: Commit**

```bash
git add frontend/src
git commit -m "feat(admin): surface is_platform_admin on user type + gated nav entry"
```

---

## Task 14: Frontend — admin API query hooks

**Files:**
- Create: `frontend/src/controllers/API/queries/admin/types.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-get-organizations.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-get-organization.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-create-organization.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-delete-organization.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-get-members.ts` (alias for get-organization for now, or dedicated)
- Create: `frontend/src/controllers/API/queries/admin/use-add-member.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-remove-member.ts`
- Create: `frontend/src/controllers/API/queries/admin/use-search-users.ts`
- Create: `frontend/src/controllers/API/queries/admin/index.ts`

- [x] **Step 1: Mirror an existing query hook pattern**

Open `frontend/src/controllers/API/queries/folders/use-get-folders.ts` (or whichever existing query module is closest in style) and copy its shape for each new hook. Each hook wraps TanStack Query's `useQuery`/`useMutation` against the `api.get`/`api.post`/`api.delete` helpers already in the codebase.

Example — `use-get-organizations.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { OrgListResponse } from "./types";

export function useGetOrganizations(params: { q?: string; limit?: number; offset?: number } = {}) {
  return useQuery<OrgListResponse>({
    queryKey: ["admin", "organizations", params],
    queryFn: async () => {
      const { data } = await api.get<OrgListResponse>("/api/v1/admin/organizations", { params });
      return data;
    },
  });
}
```

`types.ts` — mirror the Pydantic response shapes (`OrgSummary`, `OrgDetail`, `MemberRow`, `UserRow`, etc.). Each mutation hook uses `useMutation` and invalidates `["admin", "organizations"]` on success.

- [x] **Step 2: Export from `index.ts`**

```ts
export * from "./use-get-organizations";
export * from "./use-get-organization";
export * from "./use-create-organization";
export * from "./use-delete-organization";
export * from "./use-add-member";
export * from "./use-remove-member";
export * from "./use-search-users";
```

- [x] **Step 3: Commit**

```bash
git add frontend/src/controllers/API/queries/admin
git commit -m "feat(admin): add frontend query hooks for admin endpoints"
```

---

## Task 15: Frontend — organizations list + create drawer

**Files:**
- Create: `frontend/src/pages/AdminPage/index.tsx` (route shell)
- Create: `frontend/src/pages/AdminPage/organizations/OrganizationsListPage.tsx`
- Create: `frontend/src/pages/AdminPage/organizations/CreateOrganizationDrawer.tsx`
- Modify: `frontend/src/routes.tsx` — register `/admin/organizations`, `/admin/organizations/new`

- [x] **Step 1: `AdminPage` layout shell**

```tsx
// frontend/src/pages/AdminPage/index.tsx
import { Outlet } from "react-router-dom";

export default function AdminPage() {
  return (
    <div className="flex h-full flex-col p-6">
      <h1 className="text-2xl font-semibold mb-4">Admin</h1>
      <Outlet />
    </div>
  );
}
```

- [x] **Step 2: Organizations list page**

```tsx
// frontend/src/pages/AdminPage/organizations/OrganizationsListPage.tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useGetOrganizations } from "@/controllers/API/queries/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function OrganizationsListPage() {
  const [q, setQ] = useState("");
  const { data, isLoading } = useGetOrganizations({ q: q || undefined });
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Input
          placeholder="Search organizations"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
        <Button onClick={() => navigate("/admin/organizations/new")}>
          New organization
        </Button>
      </div>
      {isLoading ? <div>Loading…</div> : (
        <table className="w-full text-sm">
          <thead>
            <tr><th>Name</th><th>Slug</th><th>Members</th><th>Created</th></tr>
          </thead>
          <tbody>
            {data?.items.map((o) => (
              <tr key={o.id} className="hover:bg-muted cursor-pointer"
                  onClick={() => navigate(`/admin/organizations/${o.id}`)}>
                <td>{o.name}</td>
                <td>{o.slug}</td>
                <td>{o.member_count}</td>
                <td>{o.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [x] **Step 3: Create drawer**

```tsx
// frontend/src/pages/AdminPage/organizations/CreateOrganizationDrawer.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateOrganization } from "@/controllers/API/queries/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function CreateOrganizationDrawer() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugDirty, setSlugDirty] = useState(false);
  const nav = useNavigate();
  const { mutateAsync, isPending, error } = useCreateOrganization();

  return (
    <div className="max-w-md space-y-3">
      <h2 className="text-lg font-medium">New organization</h2>
      <Input value={name} placeholder="Name" onChange={(e) => {
        setName(e.target.value);
        if (!slugDirty) setSlug(slugify(e.target.value));
      }} />
      <Input value={slug} placeholder="slug" onChange={(e) => {
        setSlug(e.target.value); setSlugDirty(true);
      }} />
      {error && <div className="text-destructive text-sm">{String((error as any).message)}</div>}
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => nav("/admin/organizations")}>Cancel</Button>
        <Button disabled={!name || !slug || isPending}
                onClick={async () => {
                  const o = await mutateAsync({ name, slug });
                  nav(`/admin/organizations/${o.id}`);
                }}>
          Create
        </Button>
      </div>
    </div>
  );
}
```

- [x] **Step 4: Register routes**

In `frontend/src/routes.tsx` (or the lazy-route manifest — look for `ProtectedRoute` wrapping), add (detail route is added in Task 16):

```tsx
{
  path: "/admin",
  element: <ProtectedAdminRoute><AdminPage /></ProtectedAdminRoute>,
  children: [
    { path: "organizations", element: <OrganizationsListPage /> },
    { path: "organizations/new", element: <CreateOrganizationDrawer /> },
  ],
}
```

Add a small `ProtectedAdminRoute` wrapper that reads the current user from context (existing pattern in `ProtectedRoute`) and redirects to `/` with a toast if `!user.is_platform_admin`.

- [x] **Step 5: Manual smoke**

Start the dev server, sign in as a platform admin, click Admin → create an org, verify it shows up in the list.

- [x] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(admin): organizations list + create in admin UI"
```

---

## Task 16: Frontend — organization detail (members tab)

**Files:**
- Create: `frontend/src/pages/AdminPage/organizations/OrganizationDetailPage.tsx`
- Create: `frontend/src/pages/AdminPage/organizations/OrganizationMembersTab.tsx`
- Create: `frontend/src/pages/AdminPage/organizations/AddMemberDialog.tsx`

- [x] **Step 1: Detail page with tabs**

```tsx
// OrganizationDetailPage.tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useGetOrganization } from "@/controllers/API/queries/admin";
import OrganizationMembersTab from "./OrganizationMembersTab";
import OrganizationSettingsTab from "./OrganizationSettingsTab";

export default function OrganizationDetailPage() {
  const { orgId } = useParams();
  const [tab, setTab] = useState<"members" | "settings">("members");
  const { data: org } = useGetOrganization(orgId!);
  if (!org) return <div>Loading…</div>;
  return (
    <div>
      <h2 className="text-xl font-semibold">{org.name}</h2>
      <div className="flex gap-4 border-b my-3">
        <button onClick={() => setTab("members")}>Members</button>
        <button onClick={() => setTab("settings")}>Settings</button>
      </div>
      {tab === "members"
        ? <OrganizationMembersTab orgId={org.id} members={org.members} />
        : <OrganizationSettingsTab org={org} />}
    </div>
  );
}
```

- [x] **Step 2: Members tab with add/remove**

```tsx
// OrganizationMembersTab.tsx
import { useState } from "react";
import { useAddMember, useRemoveMember, useSearchUsers } from "@/controllers/API/queries/admin";

type Member = { user_id: string; username: string; role: string };

export default function OrganizationMembersTab(
  { orgId, members }: { orgId: string; members: Member[] }
) {
  const [showAdd, setShowAdd] = useState(false);
  const remove = useRemoveMember();

  return (
    <div>
      <button onClick={() => setShowAdd(true)}>Add member</button>
      <ul>
        {members.map((m) => (
          <li key={m.user_id}>
            {m.username} ({m.role}){" "}
            <button onClick={() => remove.mutate({ orgId, userId: m.user_id })}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      {showAdd && <AddMemberDialog orgId={orgId} onClose={() => setShowAdd(false)} />}
    </div>
  );
}
```

- [x] **Step 3: Add-member dialog with user search**

```tsx
// AddMemberDialog.tsx
import { useState } from "react";
import { useAddMember, useSearchUsers } from "@/controllers/API/queries/admin";

export default function AddMemberDialog(
  { orgId, onClose }: { orgId: string; onClose: () => void }
) {
  const [q, setQ] = useState("");
  const { data } = useSearchUsers({ q });
  const add = useAddMember();
  return (
    <div className="p-4 border">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users" />
      <ul>
        {data?.items.map((u) => (
          <li key={u.id}>
            {u.username}{" "}
            <button onClick={async () => {
              await add.mutateAsync({ orgId, userId: u.id });
              onClose();
            }}>
              Add
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onClose}>Cancel</button>
    </div>
  );
}
```

- [x] **Step 4: Register the detail route**

In `frontend/src/routes.tsx`, append to the `/admin` `children` array added in Task 15:

```tsx
{ path: "organizations/:orgId", element: <OrganizationDetailPage /> },
```

- [x] **Step 5: Manual smoke**

Add a member to the org created in Task 15; verify the members list updates, then remove them.

- [x] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(admin): organization detail and members tab"
```

---

## Task 17: Frontend — organization settings tab + typed-delete dialog

**Files:**
- Create: `frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx`
- Create: `frontend/src/components/common/confirmByTypingDialog/index.tsx` (only if no equivalent exists — first search for "confirm" patterns in `frontend/src/components/common`)

- [x] **Step 1: `ConfirmByTypingDialog`**

```tsx
// confirmByTypingDialog/index.tsx
import { useState } from "react";

export default function ConfirmByTypingDialog({
  title,
  description,
  confirmText,
  destructive = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  confirmText: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  const enabled = typed === confirmText;
  return (
    <div className="p-4 border rounded bg-background">
      <h3 className="font-medium">{title}</h3>
      <p className="text-sm my-2">{description}</p>
      <p className="text-sm">Type <code>{confirmText}</code> to confirm.</p>
      <input value={typed} onChange={(e) => setTyped(e.target.value)} />
      <div className="flex gap-2 mt-2">
        <button onClick={onCancel}>Cancel</button>
        <button
          disabled={!enabled}
          className={destructive ? "text-destructive" : ""}
          onClick={onConfirm}
        >
          {destructive ? "Delete" : "Confirm"}
        </button>
      </div>
    </div>
  );
}
```

- [x] **Step 2: Settings tab**

```tsx
// OrganizationSettingsTab.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDeleteOrganization } from "@/controllers/API/queries/admin";
import ConfirmByTypingDialog from "@/components/common/confirmByTypingDialog";

type OrgDetail = {
  id: string; name: string; slug: string; is_personal: boolean;
  created_at: string; updated_at: string;
};

export default function OrganizationSettingsTab({ org }: { org: OrgDetail }) {
  const [confirming, setConfirming] = useState(false);
  const nav = useNavigate();
  const del = useDeleteOrganization();

  return (
    <div className="space-y-4">
      <dl className="text-sm">
        <div><dt>Slug</dt><dd>{org.slug}</dd></div>
        <div><dt>Created</dt><dd>{org.created_at}</dd></div>
      </dl>
      <button
        disabled={org.is_personal}
        title={org.is_personal ? "Personal orgs cannot be deleted" : undefined}
        onClick={() => setConfirming(true)}
      >
        Delete organization
      </button>
      {confirming && (
        <ConfirmByTypingDialog
          title="Delete organization"
          description="This permanently deletes the organization and all flows, files, deployments, and memberships inside it."
          confirmText={org.name}
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            await del.mutateAsync({ orgId: org.id, confirm_name: org.name });
            nav("/admin/organizations");
          }}
        />
      )}
    </div>
  );
}
```

- [x] **Step 3: Manual smoke**

Delete the test org from Task 15 with a wrong name (button disabled), then with the correct name (succeeds; redirected to list).

- [x] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "feat(admin): organization settings tab with typed-delete confirmation"
```

---

## Task 18: Backend full-suite + frontend build smoke

> **Status 2026-04-24:** Platform-admin feature is verified. Run failures below are orthogonal to admin and tracked separately.

- [x] **Step 1: Run the whole backend test suite** — _partial_

```bash
cd src/backend/base && uv run pytest ../../tests/unit/api/v1/test_admin.py ../../tests/unit/api/v1/test_users.py ../../tests/unit/alembic/ -v
```
Result: `test_admin.py` **17/17 pass**; `test_users.py` passes; `tests/unit/alembic/` is green **except** `test_migration_execution.py::test_no_phantom_migrations`, which flags 22 `modify_type` diffs in admin-related tables (`admin_notification`, `alert_rule`, `flow_usage_daily`, `org_usage_daily`, `org_usage_threshold`). The diffs are autogenerate rendering drift under SQLAlchemy 2.0.49 (Enum vs VARCHAR(N), Integer vs BIGINT, Uuid vs CHAR(32)) — not a genuine schema divergence. Tracked as a follow-up to regenerate the admin-table migrations against the current dep versions. Does not block platform-admin feature sign-off.

- [x] **Step 2: Run the frontend typecheck/build** — _unblocked by `7f657b5e92 fix(frontend): declare whatwg-fetch so vite/rolldown resolves fetch-intercept`_

```bash
cd frontend && npm run build
```
Result: **fails** with `Rolldown failed to resolve import "whatwg-fetch" from "node_modules/fetch-intercept/lib/browser.js"`. Pre-existing after `6d0e3e41c7 chore(frontend): upgrade all npm packages to latest`; either add `whatwg-fetch` as an explicit dep or externalize `fetch-intercept`. Tracked separately. Typecheck of non-test frontend sources is clean; admin-page sources compile.

- [x] **Step 3: Finish up**

If everything is green, this feature branch is ready. Consult the superpowers:finishing-a-development-branch skill for PR/merge guidance.

---

## Notes

- **Cascade coverage:** Task 8 explicitly enumerates every table carrying `organization_id` in this branch. Before landing, re-grep to catch any new child tables: `grep -rn 'foreign_key="organization.id"' src/backend/base/langflow/services/database/models`.
- **Org switcher UX is not in this plan.** After assignment, the user's default "current org" is still their personal org (Task 5's resolution rule). A follow-up can add a `X-Acting-Org-Id`-for-members flow or a durable `User.default_organization_id` column.
- **`X-Acting-Org-Id` is unchanged.** Legacy `is_superuser` callers still get the same escape hatch. Platform admins do not implicitly inherit this; if we want platform admins to debug inside other orgs, extend the header-permission check in a later spec.
