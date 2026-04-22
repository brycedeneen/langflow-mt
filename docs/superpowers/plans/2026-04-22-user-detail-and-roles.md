# User Detail Page & Role Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Commit protocol:** This user requires explicit permission for every `git commit`. Commit steps say "propose commit" — ask the user for go-ahead before running `git add` / `git commit`. Do not commit proactively.

**Goal:** Implement the User Detail Page, expand `MembershipRole` to a five-tier hierarchy (Owner/Admin/Member/Operator/Viewer), add role-based authorization to flow/folder CRUD and execution, and ship the UI surfaces that let platform admins and org Owners/Admins manage users and roles.

**Architecture:** Single-plan, seven-phase rollout matching the spec's deploy order — backend foundation (enum + helpers + migrations) first, then new admin endpoints, then frontend shared components, then detail pages, then existing-page updates, then the flow/folder ownership transition, then end-to-end verification. Each phase ends at a checkpoint the engineer can pause at.

**Tech Stack:** FastAPI + SQLModel + Alembic (Postgres/SQLite); React + TanStack Query v5 + Zustand v5 + Jest; existing repo conventions in `src/backend/base/langflow/` and `src/frontend/src/`.

**Source spec:** [`docs/superpowers/specs/2026-04-22-user-detail-and-roles-design.md`](../specs/2026-04-22-user-detail-and-roles-design.md)

---

## File Structure

**Backend — new files**
- `src/backend/base/langflow/api/v1/admin/users.py` — platform-admin user-scoped endpoints (`GET /admin/users/{user_id}`)
- `src/backend/base/langflow/api/utils/authz.py` — `ROLE_ORDER`, `require_org_role`, `assert_org_role`
- `src/backend/base/langflow/alembic/versions/<hash>_extend_membership_role_enum.py`
- `src/backend/base/langflow/alembic/versions/<hash>_flow_folder_user_id_set_null.py`
- `src/backend/tests/unit/api/utils/test_authz.py`
- `src/backend/tests/unit/api/v1/admin/test_users.py`
- `src/backend/tests/unit/api/v1/admin/test_role_changes.py`
- `src/backend/tests/unit/api/v1/test_flow_role_enforcement.py`

**Backend — modified files**
- `src/backend/base/langflow/services/database/models/membership/model.py` — enum extension
- `src/backend/base/langflow/services/database/models/flow/model.py` — FK change docstring (no column rename)
- `src/backend/base/langflow/services/database/models/folder/model.py` — FK change (matching Flow)
- `src/backend/base/langflow/api/v1/admin/orgs.py` — new PATCH role endpoint, relaxed gates on add/remove, `is_active` on `MemberRow`
- `src/backend/base/langflow/api/v1/__init__.py` — wire the new `admin/users.py` router
- Flow and folder endpoint modules — replace `user_id == current_user.id` checks with `assert_org_role`

**Frontend — new files**
- `src/frontend/src/constants/roles.ts` — `MembershipRole`, `ROLE_METADATA`, `ROLE_ORDER`
- `src/frontend/src/components/common/roleBadge.tsx` + `__tests__/`
- `src/frontend/src/components/common/rolePicker.tsx` + `__tests__/`
- `src/frontend/src/controllers/API/queries/admin/use-get-user.ts`
- `src/frontend/src/controllers/API/queries/admin/use-update-member-role.ts`
- `src/frontend/src/pages/AdminPage/UserDetailPage/index.tsx` + child files (`AccountTab.tsx`, `MembershipsTab.tsx`, `AddToOrganizationDialog.tsx`)
- `src/frontend/src/pages/AdminPage/organizations/OrgMemberDetailPage.tsx`
- Corresponding `__tests__/` directories

**Frontend — modified files**
- `src/frontend/src/routes.tsx` — two new routes
- `src/frontend/src/pages/AdminPage/UsersPage.tsx` — rows navigate to detail
- `src/frontend/src/pages/AdminPage/organizations/OrganizationMembersTab.tsx` — `RoleBadge` column; rows navigate to scoped detail

---

## Phase 1 — Backend Foundation

### Task 1: Extend `MembershipRole` enum

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/membership/model.py:14-16`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/models/test_membership_role_enum.py`:

```python
from langflow.services.database.models.membership.model import MembershipRole


def test_membership_role_contains_all_five_tiers():
    assert {r.value for r in MembershipRole} == {
        "owner", "admin", "member", "operator", "viewer"
    }


def test_membership_role_owner_value_unchanged():
    # Backward compatibility — existing rows use this string.
    assert MembershipRole.OWNER.value == "owner"
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/models/test_membership_role_enum.py -v
```
Expected: fails on `test_membership_role_contains_all_five_tiers` (only `OWNER` exists).

- [ ] **Step 3: Extend the enum**

Edit `src/backend/base/langflow/services/database/models/membership/model.py`:

```python
class MembershipRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    OPERATOR = "operator"
    VIEWER = "viewer"
```

- [ ] **Step 4: Rerun — all pass**

```bash
uv run pytest src/backend/tests/unit/models/test_membership_role_enum.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Propose commit**

```bash
git add src/backend/base/langflow/services/database/models/membership/model.py \
  src/backend/tests/unit/models/test_membership_role_enum.py
# Ask user for commit go-ahead.
git commit -m "feat(membership): extend role enum to owner/admin/member/operator/viewer"
```

---

### Task 2: Alembic migration — enum extension

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<hash>_extend_membership_role_enum.py`

- [ ] **Step 1: Generate a revision**

```bash
cd src/backend/base/langflow
uv run alembic revision -m "extend membership role enum"
```
Expected: prints new revision path. Note the filename `<hash>_extend_membership_role_enum.py`.

- [ ] **Step 2: Write the migration**

Replace the generated body with:

```python
"""extend membership role enum

Revision ID: <generated>
Revises: <previous head — alembic filled this in>
Create Date: 2026-04-22
"""
from alembic import op

revision = "<generated>"
down_revision = "<previous>"
branch_labels = None
depends_on = None

NEW_VALUES = ("admin", "member", "operator", "viewer")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE membership_role_enum ADD VALUE IF NOT EXISTS '{value}'")
    # SQLite uses a CHECK constraint derived from the Python enum; no DDL needed —
    # SQLAlchemy rebuilds it on next connection.


def downgrade() -> None:
    # Postgres does not support ALTER TYPE ... DROP VALUE. Rolling back requires
    # either dropping and recreating the enum (data-destructive) or a forward-fix
    # deploy. Intentional no-op; forward-only migration.
    pass
```

- [ ] **Step 3: Dry-run on a disposable Postgres**

```bash
uv run alembic upgrade head --sql > /tmp/upgrade.sql
grep "membership_role_enum" /tmp/upgrade.sql
```
Expected: four `ALTER TYPE ... ADD VALUE` lines for admin/member/operator/viewer.

- [ ] **Step 4: Run live upgrade**

```bash
uv run alembic upgrade head
```
Expected: no errors; `alembic current` prints the new revision.

- [ ] **Step 5: Smoke-test enum insert**

```bash
uv run python -c "
import asyncio
from langflow.services.database.models.membership.model import Membership, MembershipRole
from lfx.services.deps import session_scope
from uuid import uuid4
async def main():
    async with session_scope() as s:
        m = Membership(user_id=uuid4(), organization_id=uuid4(), role=MembershipRole.VIEWER)
        # don't actually commit — just validate the enum cast
        print(m.role.value)
asyncio.run(main())
"
```
Expected: prints `viewer`.

- [ ] **Step 6: Propose commit**

```bash
git add src/backend/base/langflow/alembic/versions/<hash>_extend_membership_role_enum.py
# Ask user first.
git commit -m "feat(db): alembic migration extending membership_role_enum"
```

---

### Task 3: Alembic migration — flow/folder `user_id` FK to `ON DELETE SET NULL`

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<hash>_flow_folder_user_id_set_null.py`

- [ ] **Step 1: Inspect current FK behavior**

Read `src/backend/base/langflow/services/database/models/flow/model.py:213` and `folder/model.py` to confirm current FK `ondelete`. Record the existing constraint name (check Alembic history or run `\d flow` against a dev DB) — you need the old name to drop it.

- [ ] **Step 2: Generate revision**

```bash
uv run alembic revision -m "flow folder user_id on delete set null"
```

- [ ] **Step 3: Write the migration**

```python
"""flow folder user_id ON DELETE SET NULL

Revision ID: <generated>
Revises: <extend_membership_role_enum>
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<extend_membership_role_enum>"
branch_labels = None
depends_on = None


def _alter_user_fk(table: str, old_constraint: str, new_constraint: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(old_constraint, table, type_="foreignkey")
        op.create_foreign_key(
            new_constraint, table, "user",
            ["user_id"], ["id"], ondelete="SET NULL",
        )
    elif bind.dialect.name == "sqlite":
        # SQLite can't ALTER constraints; use batch_alter_table.
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.drop_constraint(old_constraint, type_="foreignkey")
            batch_op.create_foreign_key(
                new_constraint, "user",
                ["user_id"], ["id"], ondelete="SET NULL",
            )


def upgrade() -> None:
    # Column must already be nullable; if not, make it so.
    with op.batch_alter_table("flow") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)
    with op.batch_alter_table("folder") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)

    _alter_user_fk("flow", "flow_user_id_fkey", "flow_user_id_fkey")
    _alter_user_fk("folder", "folder_user_id_fkey", "folder_user_id_fkey")


def downgrade() -> None:
    _alter_user_fk("folder", "folder_user_id_fkey", "folder_user_id_fkey_old")
    _alter_user_fk("flow", "flow_user_id_fkey", "flow_user_id_fkey_old")
```

> **Constraint names:** the placeholders above assume Postgres default naming. Confirm with `psql -c "\d flow"` before committing — names may differ (e.g. `fk_flow_user_id_user`). Update the migration accordingly.

- [ ] **Step 4: Run upgrade**

```bash
uv run alembic upgrade head
```
Expected: clean apply.

- [ ] **Step 5: Verify FK behavior**

```bash
uv run python - <<'PY'
import asyncio
from sqlalchemy import text
from lfx.services.deps import session_scope
async def main():
    async with session_scope() as s:
        r = await s.exec(text(
            "select confdeltype from pg_constraint "
            "where conname = 'flow_user_id_fkey'"
        ))
        print(r.first())
asyncio.run(main())
PY
```
Expected (Postgres): prints `('n',)` — FK delete action `n` = SET NULL.

- [ ] **Step 6: Propose commit**

```bash
git add src/backend/base/langflow/alembic/versions/<hash>_flow_folder_user_id_set_null.py
git commit -m "feat(db): flow/folder user_id ON DELETE SET NULL"
```

---

### Task 4: Authorization helpers — `ROLE_ORDER`, `require_org_role`, `assert_org_role`

**Files:**
- Create: `src/backend/base/langflow/api/utils/authz.py`
- Create: `src/backend/tests/unit/api/utils/test_authz.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/backend/tests/unit/api/utils/test_authz.py
import pytest
from fastapi import HTTPException

from langflow.api.utils.authz import ROLE_ORDER, assert_org_role
from langflow.services.database.models.membership.model import MembershipRole


def _fake_user(is_platform_admin: bool = False):
    class U:
        id = "u"
        is_platform_admin = is_platform_admin
    return U()


@pytest.mark.parametrize(
    "role,min_role,allowed",
    [
        (MembershipRole.OWNER,    MembershipRole.VIEWER,   True),
        (MembershipRole.VIEWER,   MembershipRole.OWNER,    False),
        (MembershipRole.MEMBER,   MembershipRole.MEMBER,   True),
        (MembershipRole.OPERATOR, MembershipRole.MEMBER,   False),
        (MembershipRole.OPERATOR, MembershipRole.OPERATOR, True),
        (MembershipRole.ADMIN,    MembershipRole.MEMBER,   True),
    ],
)
def test_role_order_threshold(role, min_role, allowed):
    assert (ROLE_ORDER[role] >= ROLE_ORDER[min_role]) is allowed


async def test_assert_org_role_403_when_no_membership(mocker):
    mocker.patch(
        "langflow.api.utils.authz._load_membership",
        return_value=None,
    )
    with pytest.raises(HTTPException) as exc:
        await assert_org_role(_fake_user(), "org-1", MembershipRole.VIEWER, session=object())
    assert exc.value.status_code == 403


async def test_assert_org_role_bypasses_for_platform_admin(mocker):
    mocker.patch(
        "langflow.api.utils.authz._load_membership",
        return_value=None,
    )
    # Platform admins bypass even when no membership exists.
    result = await assert_org_role(
        _fake_user(is_platform_admin=True),
        "org-1",
        MembershipRole.OWNER,
        session=object(),
    )
    assert result is None


async def test_assert_org_role_returns_membership_on_success(mocker):
    class M:
        role = MembershipRole.ADMIN
    mocker.patch("langflow.api.utils.authz._load_membership", return_value=M())
    result = await assert_org_role(_fake_user(), "org-1", MembershipRole.MEMBER, session=object())
    assert result.role == MembershipRole.ADMIN


async def test_assert_org_role_403_when_role_too_low(mocker):
    class M:
        role = MembershipRole.VIEWER
    mocker.patch("langflow.api.utils.authz._load_membership", return_value=M())
    with pytest.raises(HTTPException) as exc:
        await assert_org_role(_fake_user(), "org-1", MembershipRole.MEMBER, session=object())
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest src/backend/tests/unit/api/utils/test_authz.py -v
```
Expected: import error — `authz` module doesn't exist yet.

- [ ] **Step 3: Implement the helpers**

```python
# src/backend/base/langflow/api/utils/authz.py
"""Org-scoped role authorization helpers.

Two entry points:
    - `require_org_role(min_role)` — FastAPI dependency factory for endpoints
      where the caller has an `org_id` path param.
    - `assert_org_role(user, org_id, min_role, session)` — imperative check,
      used by resource endpoints that resolve org_id from the resource itself.
"""
from __future__ import annotations

from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Path
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.user.model import User


ROLE_ORDER: dict[MembershipRole, int] = {
    MembershipRole.OWNER: 5,
    MembershipRole.ADMIN: 4,
    MembershipRole.MEMBER: 3,
    MembershipRole.OPERATOR: 2,
    MembershipRole.VIEWER: 1,
}


async def _load_membership(
    session: AsyncSession, user_id: UUID, org_id: UUID
) -> Membership | None:
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.organization_id == org_id,
    )
    return (await session.exec(stmt)).first()


async def assert_org_role(
    user: User,
    org_id: UUID,
    min_role: MembershipRole,
    *,
    session: AsyncSession,
) -> Membership | None:
    """Raise 403 unless caller has at least `min_role` in `org_id`.
    Platform admins bypass and receive None.
    """
    if user.is_platform_admin:
        return None
    membership = await _load_membership(session, user.id, org_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    if ROLE_ORDER[membership.role] < ROLE_ORDER[min_role]:
        raise HTTPException(status_code=403, detail=f"Requires role {min_role.value} or higher")
    return membership


def require_org_role(min_role: MembershipRole) -> Callable:
    """Dep factory: FastAPI dep that reads `org_id` from the path and enforces
    `min_role`. Returns the caller's Membership (or None for platform-admin bypass).
    """
    async def _dep(
        org_id: Annotated[UUID, Path(...)],
        user: CurrentActiveUser,
        session: DbSession,
    ) -> Membership | None:
        return await assert_org_role(user, org_id, min_role, session=session)
    return _dep


OrgRoleOwner    = Annotated[Membership | None, Depends(require_org_role(MembershipRole.OWNER))]
OrgRoleAdmin    = Annotated[Membership | None, Depends(require_org_role(MembershipRole.ADMIN))]
OrgRoleMember   = Annotated[Membership | None, Depends(require_org_role(MembershipRole.MEMBER))]
OrgRoleOperator = Annotated[Membership | None, Depends(require_org_role(MembershipRole.OPERATOR))]
OrgRoleViewer   = Annotated[Membership | None, Depends(require_org_role(MembershipRole.VIEWER))]
```

- [ ] **Step 4: Rerun — all pass**

```bash
uv run pytest src/backend/tests/unit/api/utils/test_authz.py -v
```
Expected: 9 passed (6 parametrized + 4 async).

- [ ] **Step 5: Propose commit**

```bash
git add src/backend/base/langflow/api/utils/authz.py \
  src/backend/tests/unit/api/utils/test_authz.py
git commit -m "feat(authz): add ROLE_ORDER, require_org_role, assert_org_role"
```

**Phase 1 checkpoint** — enum extended, migrations applied, authz helpers landed. Run the full backend test suite before moving on:

```bash
uv run pytest src/backend/tests/unit/ -q
```
Expected: pre-existing tests still pass.

---

## Phase 2 — Admin API

### Task 5: `GET /api/v1/admin/users/{user_id}` — new endpoint

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/users.py`
- Modify: `src/backend/base/langflow/api/v1/__init__.py` (register router)
- Create: `src/backend/tests/unit/api/v1/admin/test_users.py`

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/api/v1/admin/test_users.py
import pytest
from httpx import AsyncClient


async def test_get_user_detail_platform_admin_success(
    client: AsyncClient, platform_admin_token: str, seeded_user_with_memberships
):
    uid = seeded_user_with_memberships["id"]
    r = await client.get(f"/api/v1/admin/users/{uid}",
                         headers={"Authorization": f"Bearer {platform_admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(uid)
    assert body["username"] == seeded_user_with_memberships["username"]
    assert body["is_active"] is True
    assert body["is_platform_admin"] is False
    assert len(body["memberships"]) == 2
    # personal org sorts first
    assert body["memberships"][0]["is_personal"] is True


async def test_get_user_detail_404_when_missing(client: AsyncClient, platform_admin_token: str):
    r = await client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
                         headers={"Authorization": f"Bearer {platform_admin_token}"})
    assert r.status_code == 404


async def test_get_user_detail_403_for_non_platform_admin(
    client: AsyncClient, logged_in_token: str, seeded_user_with_memberships
):
    uid = seeded_user_with_memberships["id"]
    r = await client.get(f"/api/v1/admin/users/{uid}",
                         headers={"Authorization": f"Bearer {logged_in_token}"})
    assert r.status_code == 403
```

You may need to add a `seeded_user_with_memberships` fixture to `conftest.py` — check for an existing pattern in `src/backend/tests/unit/api/v1/` first and mirror it.

- [ ] **Step 2: Run — fails (endpoint does not exist)**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/test_users.py -v
```
Expected: 404 on all three (route not registered).

- [ ] **Step 3: Implement the router**

```python
# src/backend/base/langflow/api/v1/admin/users.py
"""Platform-admin user-scoped endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User

router = APIRouter(tags=["Admin"])


class UserMembership(BaseModel):
    organization_id: UUID
    organization_name: str
    is_personal: bool
    role: str
    joined_at: datetime


class UserDetail(BaseModel):
    id: UUID
    username: str
    is_active: bool
    is_platform_admin: bool
    is_superuser: bool
    create_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    memberships: list[UserMembership]


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    rows = (await session.exec(
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
    )).all()
    # Personal org first, then alphabetical by org name.
    rows_sorted = sorted(rows, key=lambda r: (not r[1].is_personal, r[1].name.lower()))
    memberships = [
        UserMembership(
            organization_id=o.id,
            organization_name=o.name,
            is_personal=o.is_personal,
            role=m.role.value,
            joined_at=m.created_at,
        )
        for (m, o) in rows_sorted
    ]
    return UserDetail(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        is_superuser=user.is_superuser,
        create_at=getattr(user, "create_at", None),
        updated_at=getattr(user, "updated_at", None),
        last_login_at=getattr(user, "last_login_at", None),
        memberships=memberships,
    )
```

- [ ] **Step 4: Register the router**

Open `src/backend/base/langflow/api/v1/__init__.py`. Find where the existing admin routers (`admin/orgs.py`) are wired; add the new router next to it:

```python
from langflow.api.v1.admin import orgs as admin_orgs, users as admin_users

# wherever router.include_router(admin_orgs.router, prefix="/admin") lives:
router.include_router(admin_users.router, prefix="/admin")
```

- [ ] **Step 5: Rerun — all pass**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/test_users.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/admin/users.py \
  src/backend/base/langflow/api/v1/__init__.py \
  src/backend/tests/unit/api/v1/admin/test_users.py
git commit -m "feat(admin): add GET /admin/users/{user_id} endpoint"
```

---

### Task 6: `PATCH /admin/organizations/{org_id}/members/{user_id}` — change role

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/orgs.py` (add endpoint)
- Create: `src/backend/tests/unit/api/v1/admin/test_role_changes.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/backend/tests/unit/api/v1/admin/test_role_changes.py
import pytest
from httpx import AsyncClient


class TestPatchMemberRole:
    async def test_platform_admin_can_promote_to_admin(
        self, client: AsyncClient, platform_admin_token: str, org_with_member
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={"role": "admin"},
        )
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    async def test_org_admin_cannot_promote_to_admin(
        self, client: AsyncClient, org_admin_token: str, org_with_member
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
            headers={"Authorization": f"Bearer {org_admin_token}"},
            json={"role": "admin"},
        )
        assert r.status_code == 403

    async def test_org_admin_can_promote_member_to_operator(
        self, client: AsyncClient, org_admin_token: str, org_with_member
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
            headers={"Authorization": f"Bearer {org_admin_token}"},
            json={"role": "operator"},
        )
        assert r.status_code == 200

    async def test_cannot_demote_last_owner(
        self, client: AsyncClient, platform_admin_token: str, sole_owner_org
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{sole_owner_org.org_id}/members/{sole_owner_org.owner_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={"role": "admin"},
        )
        assert r.status_code == 409
        assert "last owner" in r.json()["detail"].lower()

    async def test_personal_org_locked(
        self, client: AsyncClient, platform_admin_token: str, personal_org
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{personal_org.org_id}/members/{personal_org.user_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={"role": "admin"},
        )
        assert r.status_code == 409

    async def test_viewer_caller_forbidden(
        self, client: AsyncClient, viewer_token: str, org_with_member
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"role": "member"},
        )
        assert r.status_code == 403

    async def test_invalid_role_rejected(
        self, client: AsyncClient, platform_admin_token: str, org_with_member
    ):
        r = await client.patch(
            f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={"role": "banana"},
        )
        assert r.status_code == 400
```

Fixtures `org_with_member`, `org_admin_token`, `viewer_token`, `sole_owner_org`, `personal_org` — add to `conftest.py` beside the existing `platform_admin_token` fixture.

- [ ] **Step 2: Run — all fail**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/test_role_changes.py -v
```

- [ ] **Step 3: Implement PATCH endpoint**

Append to `src/backend/base/langflow/api/v1/admin/orgs.py`:

```python
from langflow.api.utils.authz import ROLE_ORDER, assert_org_role
from langflow.services.database.models.membership.model import MembershipRole


class MemberRolePatch(BaseModel):
    role: str


def _check_role_change_allowed(
    caller_role: MembershipRole | None,  # None = platform admin
    current_target_role: MembershipRole,
    new_target_role: MembershipRole,
) -> None:
    """Escalation guard. Raises HTTPException(403) if disallowed."""
    if caller_role is None:  # platform admin bypass
        return
    if caller_role == MembershipRole.OWNER:
        return
    # Admin: both source and target role must be Member/Operator/Viewer.
    below_admin = {MembershipRole.MEMBER, MembershipRole.OPERATOR, MembershipRole.VIEWER}
    if caller_role == MembershipRole.ADMIN:
        if current_target_role not in below_admin or new_target_role not in below_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Admins cannot change Admin or Owner roles",
            )
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role to change memberships")


@router.patch("/organizations/{org_id}/members/{user_id}", response_model=MemberRow)
async def patch_member_role(
    org_id: UUID,
    user_id: UUID,
    body: MemberRolePatch,
    user: CurrentActiveUser,
    session: DbSession,
) -> MemberRow:
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        raise HTTPException(status.HTTP_409_CONFLICT, "Personal-org memberships cannot be changed")

    try:
        new_role = MembershipRole(body.role)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid role: {body.role}") from e

    caller_membership = await assert_org_role(user, org_id, MembershipRole.ADMIN, session=session)
    caller_role = caller_membership.role if caller_membership is not None else None

    m = (await session.exec(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == org_id
        )
    )).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    _check_role_change_allowed(caller_role, m.role, new_role)

    # Last-Owner guard: if demoting an Owner, at least one other Owner must remain.
    if m.role == MembershipRole.OWNER and new_role != MembershipRole.OWNER:
        owner_count = (await session.exec(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == org_id,
                Membership.role == MembershipRole.OWNER,
            )
        )).one()
        if int(owner_count) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot demote the last Owner")

    m.role = new_role
    await session.flush()

    target_user = await session.get(User, user_id)
    return MemberRow(user_id=user_id, username=target_user.username, role=new_role.value, is_active=target_user.is_active)
```

(The `is_active` field on `MemberRow` lands in Task 8 — leave the line and expect a TypeError until then, OR implement Task 8 concurrently. If sequencing strictly, omit `is_active=` from this return until Task 8 extends the model.)

- [ ] **Step 4: Import `CurrentActiveUser`**

At the top of `orgs.py`, ensure:
```python
from langflow.api.utils.core import CurrentActiveUser, DbSession, PlatformAdmin
```

- [ ] **Step 5: Rerun — all pass**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/test_role_changes.py -v
```

- [ ] **Step 6: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/admin/orgs.py \
  src/backend/tests/unit/api/v1/admin/test_role_changes.py
git commit -m "feat(admin): PATCH member role with escalation + last-owner guards"
```

---

### Task 7: Relax gates on `POST` / `DELETE` member endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/orgs.py:246-311`
- Create: `src/backend/tests/unit/api/v1/admin/test_member_gate_relaxed.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_member_gate_relaxed.py
import pytest
from httpx import AsyncClient


async def test_org_admin_can_add_member(client, org_admin_token, another_user, org_admin_org):
    r = await client.post(
        f"/api/v1/admin/organizations/{org_admin_org.org_id}/members",
        headers={"Authorization": f"Bearer {org_admin_token}"},
        json={"user_id": str(another_user.id), "role": "member"},
    )
    assert r.status_code == 201


async def test_org_admin_cannot_add_admin_or_owner(client, org_admin_token, another_user, org_admin_org):
    for role in ("admin", "owner"):
        r = await client.post(
            f"/api/v1/admin/organizations/{org_admin_org.org_id}/members",
            headers={"Authorization": f"Bearer {org_admin_token}"},
            json={"user_id": str(another_user.id), "role": role},
        )
        assert r.status_code == 403, f"unexpected success for role={role}"


async def test_member_cannot_add_anyone(client, member_token, another_user, org_admin_org):
    r = await client.post(
        f"/api/v1/admin/organizations/{org_admin_org.org_id}/members",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"user_id": str(another_user.id), "role": "viewer"},
    )
    assert r.status_code == 403


async def test_org_admin_can_remove_member(client, org_admin_token, org_with_member):
    r = await client.delete(
        f"/api/v1/admin/organizations/{org_with_member.org_id}/members/{org_with_member.user_id}",
        headers={"Authorization": f"Bearer {org_admin_token}"},
    )
    assert r.status_code == 204


async def test_cannot_remove_last_owner(client, platform_admin_token, sole_owner_org):
    r = await client.delete(
        f"/api/v1/admin/organizations/{sole_owner_org.org_id}/members/{sole_owner_org.owner_id}",
        headers={"Authorization": f"Bearer {platform_admin_token}"},
    )
    assert r.status_code == 409
```

- [ ] **Step 2: Run — all fail**

- [ ] **Step 3: Modify `add_member`**

Replace the existing `add_member` endpoint in `orgs.py`:

```python
@router.post(
    "/organizations/{org_id}/members",
    response_model=MemberRow,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    org_id: UUID,
    body: MemberAdd,
    user: CurrentActiveUser,
    session: DbSession,
) -> MemberRow:
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    target = await session.get(User, body.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        new_role = MembershipRole(body.role)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid role: {body.role}") from e

    caller_membership = await assert_org_role(user, org_id, MembershipRole.ADMIN, session=session)
    caller_role = caller_membership.role if caller_membership is not None else None
    # Reuse the escalation guard: treat "no prior row" as the target role being
    # added fresh; admins can only assign Member/Operator/Viewer.
    if caller_role == MembershipRole.ADMIN and new_role not in {
        MembershipRole.MEMBER, MembershipRole.OPERATOR, MembershipRole.VIEWER,
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins cannot assign Admin or Owner")

    existing = (await session.exec(
        select(Membership).where(
            Membership.user_id == target.id, Membership.organization_id == org.id
        )
    )).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already a member")
    m = Membership(user_id=target.id, organization_id=org.id, role=new_role)
    session.add(m)
    await session.flush()
    return MemberRow(
        user_id=target.id, username=target.username, role=new_role.value,
        is_active=target.is_active,
    )
```

- [ ] **Step 4: Modify `remove_member`**

```python
@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> None:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Cannot remove a user from their personal organization",
        )

    await assert_org_role(user, org_id, MembershipRole.ADMIN, session=session)

    m = (await session.exec(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == org_id
        )
    )).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    if m.role == MembershipRole.OWNER:
        owner_count = (await session.exec(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == org_id,
                Membership.role == MembershipRole.OWNER,
            )
        )).one()
        if int(owner_count) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot remove the last Owner")

    await session.delete(m)
    await session.flush()
```

- [ ] **Step 5: Rerun — all pass**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/test_member_gate_relaxed.py -v
uv run pytest src/backend/tests/unit/api/v1/admin/ -v   # existing tests still pass
```

- [ ] **Step 6: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/admin/orgs.py \
  src/backend/tests/unit/api/v1/admin/test_member_gate_relaxed.py
git commit -m "feat(admin): relax add/remove member gates; last-owner guard"
```

---

### Task 8: Extend `MemberRow` with `is_active`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/orgs.py:84-87` (MemberRow definition)
- Update every `MemberRow(...)` construction site in the file to pass `is_active`

- [ ] **Step 1: Write the failing test**

```python
# append to test_role_changes.py or a new file
async def test_org_detail_members_include_is_active(
    client, platform_admin_token, org_with_inactive_member
):
    r = await client.get(
        f"/api/v1/admin/organizations/{org_with_inactive_member.org_id}",
        headers={"Authorization": f"Bearer {platform_admin_token}"},
    )
    body = r.json()
    inactive = next(m for m in body["members"] if m["user_id"] == str(org_with_inactive_member.inactive_user_id))
    assert inactive["is_active"] is False
```

- [ ] **Step 2: Extend `MemberRow` model**

```python
class MemberRow(BaseModel):
    user_id: UUID
    username: str
    role: str
    is_active: bool
```

- [ ] **Step 3: Update every construction site in `orgs.py`**

Search for `MemberRow(` and add `is_active=u.is_active` (or the equivalent source) to each. Sites as of this task:
- `get_organization` (line ~117) — `MemberRow(user_id=u.id, username=u.username, role=m.role.value, is_active=u.is_active)`
- `list_members` (line ~242) — same pattern
- `add_member` (end) — `is_active=target.is_active`
- `patch_member_role` (end) — `is_active=target_user.is_active`

- [ ] **Step 4: Run tests**

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/ -v
```

- [ ] **Step 5: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/admin/orgs.py \
  src/backend/tests/unit/api/v1/admin/test_role_changes.py
git commit -m "feat(admin): include is_active on MemberRow"
```

---

### Task 9: Verify `PATCH /api/v1/users/{user_id}` accepts `is_platform_admin`

**Files:**
- Read: `src/backend/base/langflow/services/database/models/user/model.py` (UserUpdate schema)
- Read: `src/backend/base/langflow/services/database/models/user/crud.py` (update_user)
- Modify only if needed.

- [ ] **Step 1: Confirm `UserUpdate` accepts `is_platform_admin`**

```bash
grep -n "is_platform_admin" src/backend/base/langflow/services/database/models/user/model.py
```

If `UserUpdate` does not include `is_platform_admin`, add it:

```python
# in UserUpdate class
is_platform_admin: bool | None = None
```

- [ ] **Step 2: Confirm `update_user` copies through the field**

Check `src/backend/base/langflow/services/database/models/user/crud.py` — the `update_user` function should assign every UserUpdate field. If there's an explicit per-field allowlist that excludes `is_platform_admin`, add it.

- [ ] **Step 3: Add a test**

```python
# src/backend/tests/unit/api/v1/test_users_patch_platform_admin.py
async def test_platform_admin_flag_can_be_set_via_patch(
    client, platform_admin_token, other_user_id
):
    r = await client.patch(
        f"/api/v1/users/{other_user_id}",
        headers={"Authorization": f"Bearer {platform_admin_token}"},
        json={"is_platform_admin": True},
    )
    assert r.status_code == 200
    assert r.json()["is_platform_admin"] is True


async def test_non_superuser_cannot_set_platform_admin(client, logged_in_token, other_user_id):
    r = await client.patch(
        f"/api/v1/users/{other_user_id}",
        headers={"Authorization": f"Bearer {logged_in_token}"},
        json={"is_platform_admin": True},
    )
    assert r.status_code == 403
```

Note: the existing `PATCH /users/{user_id}` uses `is_superuser` as its privilege gate. Because Task 1 of the platform-admin spec auto-promoted superusers to platform admins, in practice these sets overlap for most installs. If stricter is_platform_admin-only gating is desired, add that check alongside the existing is_superuser check. This task's minimum is: verify the field round-trips.

- [ ] **Step 4: Run**

```bash
uv run pytest src/backend/tests/unit/api/v1/test_users_patch_platform_admin.py -v
```

- [ ] **Step 5: Propose commit**

```bash
git add src/backend/base/langflow/services/database/models/user/model.py \
  src/backend/base/langflow/services/database/models/user/crud.py \
  src/backend/tests/unit/api/v1/test_users_patch_platform_admin.py
git commit -m "feat(users): PATCH accepts is_platform_admin"
```

**Phase 2 checkpoint** — full admin API complete:

```bash
uv run pytest src/backend/tests/unit/api/v1/admin/ -v
```

---

## Phase 3 — Frontend Shared Components

### Task 10: Role constants and metadata

**Files:**
- Create: `src/frontend/src/constants/roles.ts`
- Create: `src/frontend/src/constants/__tests__/roles.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/frontend/src/constants/__tests__/roles.test.ts
import { MembershipRole, ROLE_METADATA, ROLE_ORDER, canAssignRole } from "../roles";

describe("ROLE_METADATA", () => {
  it("has an entry for every role", () => {
    const roles: MembershipRole[] = ["owner", "admin", "member", "operator", "viewer"];
    roles.forEach(r => expect(ROLE_METADATA[r]).toBeDefined());
  });

  it("orders roles owner > admin > member > operator > viewer", () => {
    expect(ROLE_ORDER.owner).toBeGreaterThan(ROLE_ORDER.admin);
    expect(ROLE_ORDER.admin).toBeGreaterThan(ROLE_ORDER.member);
    expect(ROLE_ORDER.member).toBeGreaterThan(ROLE_ORDER.operator);
    expect(ROLE_ORDER.operator).toBeGreaterThan(ROLE_ORDER.viewer);
  });
});

describe("canAssignRole (mirrors backend escalation guard)", () => {
  it("allows owner to assign any role", () => {
    (["owner","admin","member","operator","viewer"] as MembershipRole[]).forEach(target => {
      expect(canAssignRole({ caller: "owner", current: "member", next: target })).toBe(true);
    });
  });

  it("blocks admin from assigning admin or owner", () => {
    expect(canAssignRole({ caller: "admin", current: "member", next: "admin" })).toBe(false);
    expect(canAssignRole({ caller: "admin", current: "member", next: "owner" })).toBe(false);
  });

  it("blocks admin from changing an owner/admin row", () => {
    expect(canAssignRole({ caller: "admin", current: "admin", next: "member" })).toBe(false);
    expect(canAssignRole({ caller: "admin", current: "owner", next: "member" })).toBe(false);
  });

  it("allows admin to move among member/operator/viewer", () => {
    expect(canAssignRole({ caller: "admin", current: "member", next: "viewer" })).toBe(true);
    expect(canAssignRole({ caller: "admin", current: "viewer", next: "operator" })).toBe(true);
  });

  it("blocks member and below from assigning anything", () => {
    (["member","operator","viewer"] as MembershipRole[]).forEach(caller => {
      expect(canAssignRole({ caller, current: "viewer", next: "member" })).toBe(false);
    });
  });
});
```

- [ ] **Step 2: Run — fails**

```bash
cd src/frontend && npm test -- constants/__tests__/roles.test.ts
```

- [ ] **Step 3: Implement**

```ts
// src/frontend/src/constants/roles.ts
export type MembershipRole = "owner" | "admin" | "member" | "operator" | "viewer";

export const ROLE_ORDER: Record<MembershipRole, number> = {
  owner: 5,
  admin: 4,
  member: 3,
  operator: 2,
  viewer: 1,
};

export const ROLE_METADATA: Record<MembershipRole, {
  label: string;
  description: string;
  color: string;
}> = {
  owner: {
    label: "Owner",
    description: "Full access. Manages members and org settings. Can delete the organization.",
    color: "text-purple-700 bg-purple-50",
  },
  admin: {
    label: "Admin",
    description: "Manages members and org settings. Cannot delete the organization or create other Admins or Owners.",
    color: "text-blue-700 bg-blue-50",
  },
  member: {
    label: "Member",
    description: "Creates, edits, and runs flows. Cannot manage members or org settings.",
    color: "text-emerald-700 bg-emerald-50",
  },
  operator: {
    label: "Operator",
    description: "Runs flows and views results. Cannot edit flows or manage the organization.",
    color: "text-amber-700 bg-amber-50",
  },
  viewer: {
    label: "Viewer",
    description: "Views flows and their configuration. Cannot run or edit anything.",
    color: "text-slate-700 bg-slate-100",
  },
};

export function canAssignRole(args: {
  caller: MembershipRole | "platform_admin";
  current: MembershipRole;
  next: MembershipRole;
}): boolean {
  const { caller, current, next } = args;
  if (caller === "platform_admin" || caller === "owner") return true;
  if (caller === "admin") {
    const below: MembershipRole[] = ["member", "operator", "viewer"];
    return below.includes(current) && below.includes(next);
  }
  return false;
}
```

- [ ] **Step 4: Rerun — pass**

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/constants/roles.ts \
  src/frontend/src/constants/__tests__/roles.test.ts
git commit -m "feat(frontend): add ROLE_METADATA + canAssignRole guard"
```

---

### Task 11: `RoleBadge` component

**Files:**
- Create: `src/frontend/src/components/common/roleBadge.tsx`
- Create: `src/frontend/src/components/common/__tests__/roleBadge.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// src/frontend/src/components/common/__tests__/roleBadge.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoleBadge from "../roleBadge";

describe("RoleBadge", () => {
  it("renders the role label", () => {
    render(<RoleBadge role="admin" />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows the description in a tooltip on hover", async () => {
    render(<RoleBadge role="viewer" />);
    await userEvent.hover(screen.getByText("Viewer"));
    // Tooltip content — adjust selector to match project tooltip impl.
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/views flows/i);
  });
});
```

- [ ] **Step 2: Run — fails**

- [ ] **Step 3: Implement**

```tsx
// src/frontend/src/components/common/roleBadge.tsx
import { MembershipRole, ROLE_METADATA } from "@/constants/roles";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  role: MembershipRole;
  className?: string;
}

export default function RoleBadge({ role, className = "" }: Props) {
  const meta = ROLE_METADATA[role];
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta.color} ${className}`}
            data-testid={`role-badge-${role}`}
          >
            {meta.label}
          </span>
        </TooltipTrigger>
        <TooltipContent>{meta.description}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
```

(Use the exact `Tooltip` imports already used elsewhere in the project — check an existing component for the correct path if `@/components/ui/tooltip` is not it.)

- [ ] **Step 4: Rerun — pass**

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/components/common/roleBadge.tsx \
  src/frontend/src/components/common/__tests__/roleBadge.test.tsx
git commit -m "feat(frontend): RoleBadge shared component"
```

---

### Task 12: `RolePicker` component

**Files:**
- Create: `src/frontend/src/components/common/rolePicker.tsx`
- Create: `src/frontend/src/components/common/__tests__/rolePicker.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// rolePicker.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RolePicker from "../rolePicker";

describe("RolePicker", () => {
  it("disables admin/owner options when caller is admin", async () => {
    render(<RolePicker caller="admin" current="member" onSelect={() => {}} />);
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    expect(screen.getByTestId("role-option-admin")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("role-option-owner")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("role-option-member")).not.toHaveAttribute("aria-disabled", "true");
  });

  it("enables all options when caller is owner", async () => {
    render(<RolePicker caller="owner" current="member" onSelect={() => {}} />);
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    for (const role of ["owner","admin","member","operator","viewer"]) {
      expect(screen.getByTestId(`role-option-${role}`)).not.toHaveAttribute("aria-disabled", "true");
    }
  });

  it("calls onSelect when a role is chosen", async () => {
    const onSelect = jest.fn();
    render(<RolePicker caller="platform_admin" current="viewer" onSelect={onSelect} />);
    await userEvent.click(screen.getByTestId("role-picker-trigger"));
    await userEvent.click(screen.getByTestId("role-option-member"));
    expect(onSelect).toHaveBeenCalledWith("member");
  });

  it("is read-only when caller = 'viewer-only'", () => {
    render(<RolePicker caller="viewer" current="viewer" onSelect={() => {}} />);
    // Trigger exists but is disabled.
    expect(screen.getByTestId("role-picker-trigger")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run — fails**

- [ ] **Step 3: Implement**

```tsx
// rolePicker.tsx
import { MembershipRole, ROLE_METADATA, canAssignRole } from "@/constants/roles";
import {
  Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem,
} from "@/components/ui/select";

interface Props {
  caller: MembershipRole | "platform_admin";
  current: MembershipRole;
  onSelect: (next: MembershipRole) => void;
  disabled?: boolean;
}

const ALL_ROLES: MembershipRole[] = ["owner", "admin", "member", "operator", "viewer"];

export default function RolePicker({ caller, current, onSelect, disabled }: Props) {
  const readOnly = disabled || (caller !== "platform_admin" && caller !== "owner" && caller !== "admin");
  return (
    <Select value={current} onValueChange={(v) => onSelect(v as MembershipRole)} disabled={readOnly}>
      <SelectTrigger data-testid="role-picker-trigger" disabled={readOnly}>
        <SelectValue>{ROLE_METADATA[current].label}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {ALL_ROLES.map((role) => {
          const allowed = canAssignRole({ caller, current, next: role });
          return (
            <SelectItem
              key={role}
              value={role}
              disabled={!allowed}
              aria-disabled={!allowed}
              data-testid={`role-option-${role}`}
            >
              <div className="flex flex-col">
                <span className="font-medium">{ROLE_METADATA[role].label}</span>
                <span className="text-xs text-muted-foreground">{ROLE_METADATA[role].description}</span>
              </div>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
```

(Adjust the import path for `Select` to match existing usage in the codebase. `@/components/ui/select` is the most likely path — confirm with a grep before committing.)

- [ ] **Step 4: Rerun — pass**

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/components/common/rolePicker.tsx \
  src/frontend/src/components/common/__tests__/rolePicker.test.tsx
git commit -m "feat(frontend): RolePicker with escalation guard"
```

---

### Task 13: API hook — `useGetUser`

**Files:**
- Create: `src/frontend/src/controllers/API/queries/admin/use-get-user.ts`

- [ ] **Step 1: Read existing admin hook**

```bash
ls src/frontend/src/controllers/API/queries/admin/
```

Mirror the file layout and export style of an existing hook (e.g. `use-get-organization.ts`).

- [ ] **Step 2: Implement**

```ts
// use-get-user.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";   // confirm path in siblings
import type { MembershipRole } from "@/constants/roles";

export interface UserMembership {
  organization_id: string;
  organization_name: string;
  is_personal: boolean;
  role: MembershipRole;
  joined_at: string;
}

export interface UserDetail {
  id: string;
  username: string;
  is_active: boolean;
  is_platform_admin: boolean;
  is_superuser: boolean;
  create_at: string | null;
  updated_at: string | null;
  last_login_at: string | null;
  memberships: UserMembership[];
}

export function useGetUser(userId: string) {
  return useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: async (): Promise<UserDetail> => {
      const res = await api.get(`/api/v1/admin/users/${userId}`);
      return res.data;
    },
  });
}
```

- [ ] **Step 3: Smoke test in browser**

Manual — run the dev server, log in as a platform admin, open devtools network, call `/api/v1/admin/users/<your-id>` and confirm shape.

- [ ] **Step 4: Propose commit**

```bash
git add src/frontend/src/controllers/API/queries/admin/use-get-user.ts
git commit -m "feat(frontend): useGetUser hook"
```

---

### Task 14: API hook — `useUpdateMemberRole`

**Files:**
- Create: `src/frontend/src/controllers/API/queries/admin/use-update-member-role.ts`

- [ ] **Step 1: Implement**

```ts
// use-update-member-role.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { MembershipRole } from "@/constants/roles";

interface Args {
  orgId: string;
  userId: string;
  role: MembershipRole;
}

export function useUpdateMemberRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ orgId, userId, role }: Args) => {
      const res = await api.patch(
        `/api/v1/admin/organizations/${orgId}/members/${userId}`,
        { role },
      );
      return res.data;
    },
    onSuccess: (_data, { userId, orgId }) => {
      qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
      qc.invalidateQueries({ queryKey: ["admin", "organization", orgId] });
    },
  });
}
```

- [ ] **Step 2: Propose commit**

```bash
git add src/frontend/src/controllers/API/queries/admin/use-update-member-role.ts
git commit -m "feat(frontend): useUpdateMemberRole hook"
```

**Phase 3 checkpoint** — shared components and data-access ready. Next phase builds UI atop them.

---

## Phase 4 — Detail Pages

### Task 15: `UserDetailPage` shell + routing

**Files:**
- Create: `src/frontend/src/pages/AdminPage/UserDetailPage/index.tsx`
- Modify: `src/frontend/src/routes.tsx` (add route)

- [ ] **Step 1: Add the route**

Open `src/frontend/src/routes.tsx`. Find the route block for `/settings/organizations/:orgId`. Add, near existing `/admin/users` or `/settings/users` patterns:

```tsx
{
  path: "admin/users/:userId",
  element: <UserDetailPage />,
}
```

Wire `UserDetailPage` import: `import UserDetailPage from "@/pages/AdminPage/UserDetailPage";`

The route must be gated on `is_platform_admin` — mirror whatever gate the existing `/admin/**` routes use. If none, wrap in an `<AdminGuard>` component consistent with neighboring pages.

- [ ] **Step 2: Implement the page shell**

```tsx
// src/frontend/src/pages/AdminPage/UserDetailPage/index.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useGetUser } from "@/controllers/API/queries/admin/use-get-user";
import RoleBadge from "@/components/common/roleBadge";
import CustomLoader from "@/customization/components/custom-loader";
import AccountTab from "./AccountTab";
import MembershipsTab from "./MembershipsTab";

export default function UserDetailPage() {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const { data: user, isPending, error } = useGetUser(userId);
  const [tab, setTab] = useState<"account" | "memberships">("account");

  if (isPending) return <CustomLoader remSize={12} />;
  if (error || !user) return <div className="p-6">User not found.</div>;

  return (
    <div className="flex flex-col h-full w-full">
      {/* Breadcrumb */}
      <div className="px-6 py-3 text-sm text-muted-foreground border-b">
        <button className="hover:underline" onClick={() => navigate("/admin/users")}>
          Users
        </button>
        <span className="mx-2">/</span>
        <span>{user.username}</span>
      </div>

      {/* Identity header */}
      <div className="flex items-center gap-4 p-6 border-b bg-muted/30">
        <div className="w-14 h-14 rounded-full bg-primary flex items-center justify-center text-lg font-semibold text-primary-foreground">
          {user.username.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="text-xl font-semibold">{user.username}</div>
          <div className="text-sm text-muted-foreground font-mono">{user.id}</div>
        </div>
        <div className="flex gap-2">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
            user.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
          }`}>
            ● {user.is_active ? "Active" : "Inactive"}
          </span>
          {user.is_platform_admin && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
              Platform Admin
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-6 border-b">
        <TabButton active={tab === "account"} onClick={() => setTab("account")}>Account</TabButton>
        <TabButton active={tab === "memberships"} onClick={() => setTab("memberships")}>
          Memberships · {user.memberships.length}
        </TabButton>
      </div>

      <div className="p-6 flex-1 overflow-auto">
        {tab === "account" ? <AccountTab user={user} /> : <MembershipsTab user={user} />}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-3 font-medium border-b-2 ${
        active ? "border-primary text-foreground" : "border-transparent text-muted-foreground"
      }`}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 3: Create stub tab files so the build passes**

```tsx
// src/frontend/src/pages/AdminPage/UserDetailPage/AccountTab.tsx
import type { UserDetail } from "@/controllers/API/queries/admin/use-get-user";
export default function AccountTab(_: { user: UserDetail }) {
  return <div>Account (stub — see next task)</div>;
}
```

```tsx
// src/frontend/src/pages/AdminPage/UserDetailPage/MembershipsTab.tsx
import type { UserDetail } from "@/controllers/API/queries/admin/use-get-user";
export default function MembershipsTab(_: { user: UserDetail }) {
  return <div>Memberships (stub — see next task)</div>;
}
```

- [ ] **Step 4: Verify build**

```bash
cd src/frontend && npm run build
```
Expected: no TypeScript errors.

- [ ] **Step 5: Manual smoke**

Run dev server; navigate to `/admin/users/<your-user-id>` logged in as a platform admin. Header + tab bar render.

- [ ] **Step 6: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/UserDetailPage/ \
  src/frontend/src/routes.tsx
git commit -m "feat(frontend): UserDetailPage shell + route"
```

---

### Task 16: `AccountTab`

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/UserDetailPage/AccountTab.tsx`
- Create: `src/frontend/src/pages/AdminPage/UserDetailPage/__tests__/AccountTab.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// AccountTab.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountTab from "../AccountTab";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

jest.mock("@/controllers/API/queries/auth", () => ({
  useUpdateUser: () => ({ mutate: jest.fn() }),
  useDeleteUsers: () => ({ mutate: jest.fn() }),
}));

const qc = new QueryClient();
const wrap = (ui: React.ReactElement) => <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;

const userFixture = {
  id: "u1", username: "ava.chen",
  is_active: true, is_platform_admin: false, is_superuser: false,
  create_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-02-01T00:00:00Z",
  last_login_at: "2026-04-22T09:00:00Z",
  memberships: [],
};

describe("AccountTab", () => {
  it("renders identity facts", () => {
    render(wrap(<AccountTab user={userFixture} />));
    expect(screen.getByText("ava.chen")).toBeInTheDocument();
    expect(screen.getByText(/2025-01-01/)).toBeInTheDocument();
  });

  it("shows active toggle in correct state", () => {
    render(wrap(<AccountTab user={userFixture} />));
    expect(screen.getByTestId("active-toggle")).toBeChecked();
  });

  it("shows platform-admin toggle in correct state", () => {
    render(wrap(<AccountTab user={userFixture} />));
    expect(screen.getByTestId("platform-admin-toggle")).not.toBeChecked();
  });

  it("confirms before deleting user", async () => {
    render(wrap(<AccountTab user={userFixture} />));
    await userEvent.click(screen.getByRole("button", { name: /delete user/i }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — fails**

- [ ] **Step 3: Implement**

```tsx
// AccountTab.tsx
import { useUpdateUser, useDeleteUsers } from "@/controllers/API/queries/auth";
import useAlertStore from "@/stores/alertStore";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import ConfirmationModal from "@/modals/confirmationModal";
import { useNavigate } from "react-router-dom";
import type { UserDetail } from "@/controllers/API/queries/admin/use-get-user";

export default function AccountTab({ user }: { user: UserDetail }) {
  const navigate = useNavigate();
  const { mutate: updateUser } = useUpdateUser();
  const { mutate: deleteUser } = useDeleteUsers();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const patch = (fields: Record<string, unknown>) =>
    updateUser(
      { user_id: user.id, user: fields } as any,
      {
        onSuccess: () => setSuccess({ title: "User updated" }),
        onError: (e: any) => setError({ title: "Update failed", list: [e?.response?.data?.detail ?? String(e)] }),
      },
    );

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <section>
        <h3 className="text-lg font-semibold mb-3">Status</h3>
        <div className="grid grid-cols-2 gap-4">
          <ToggleRow
            testId="active-toggle"
            label="Active"
            description="Can log in and access the system"
            checked={user.is_active}
            onChange={(v) => patch({ is_active: v })}
          />
          <ToggleRow
            testId="platform-admin-toggle"
            label="Platform admin"
            description="Access to /admin/* console"
            checked={user.is_platform_admin}
            onChange={(v) => patch({ is_platform_admin: v })}
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-3">Identity</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Facts label="Username" value={user.username} />
          <Facts label="User ID" value={<span className="font-mono">{user.id}</span>} />
          <Facts label="Created" value={user.create_at?.slice(0, 10) ?? "—"} />
          <Facts label="Last login" value={user.last_login_at?.slice(0, 16) ?? "—"} />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold text-red-600 mb-3">Danger zone</h3>
        <div className="border border-red-200 rounded-md p-4 flex items-center justify-between">
          <div>
            <div className="font-semibold">Delete user</div>
            <div className="text-sm text-muted-foreground">
              Permanent. Removes the account and their personal organization.
            </div>
          </div>
          <ConfirmationModal
            size="x-small"
            title="Delete user"
            titleHeader="Delete user"
            modalContentTitle="Attention!"
            cancelText="Cancel"
            confirmationText="Delete"
            icon="UserMinus2"
            data={user}
            index={0}
            onConfirm={() =>
              deleteUser(
                { user_id: user.id },
                {
                  onSuccess: () => { setSuccess({ title: "User deleted" }); navigate("/admin/users"); },
                  onError: (e: any) => setError({ title: "Delete failed", list: [e?.response?.data?.detail ?? String(e)] }),
                },
              )
            }
          >
            <ConfirmationModal.Content>
              Are you sure you want to delete this user? This cannot be undone.
            </ConfirmationModal.Content>
            <ConfirmationModal.Trigger>
              <Button variant="destructive">Delete user</Button>
            </ConfirmationModal.Trigger>
          </ConfirmationModal>
        </div>
      </section>
    </div>
  );
}

function ToggleRow({ testId, label, description, checked, onChange }: {
  testId: string; label: string; description: string;
  checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="border rounded-md p-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{label}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
        <Switch checked={checked} onCheckedChange={onChange} data-testid={testId} />
      </div>
    </div>
  );
}

function Facts({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div>{value}</div>
    </div>
  );
}
```

- [ ] **Step 4: Rerun — pass**

```bash
cd src/frontend && npm test -- UserDetailPage/__tests__/AccountTab.test.tsx
```

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/UserDetailPage/AccountTab.tsx \
  src/frontend/src/pages/AdminPage/UserDetailPage/__tests__/AccountTab.test.tsx
git commit -m "feat(frontend): UserDetailPage AccountTab"
```

---

### Task 17: `MembershipsTab` + `AddToOrganizationDialog`

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/UserDetailPage/MembershipsTab.tsx`
- Create: `src/frontend/src/pages/AdminPage/UserDetailPage/AddToOrganizationDialog.tsx`
- Create: `src/frontend/src/pages/AdminPage/UserDetailPage/__tests__/MembershipsTab.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// MembershipsTab.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MembershipsTab from "../MembershipsTab";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockUpdateRole = jest.fn();
const mockRemoveMember = jest.fn();
jest.mock("@/controllers/API/queries/admin/use-update-member-role", () => ({
  useUpdateMemberRole: () => ({ mutate: mockUpdateRole, isPending: false }),
}));
jest.mock("@/controllers/API/queries/admin/use-remove-member", () => ({
  useRemoveMember: () => ({ mutate: mockRemoveMember, isPending: false }),
}));

const qc = new QueryClient();
const wrap = (ui: React.ReactElement) => <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;

const user = {
  id: "u1", username: "ava", is_active: true, is_platform_admin: true,
  is_superuser: false, create_at: null, updated_at: null, last_login_at: null,
  memberships: [
    { organization_id: "org-personal", organization_name: "ava's org", is_personal: true, role: "owner" as const, joined_at: "2024-01-01" },
    { organization_id: "org-team",     organization_name: "Team",       is_personal: false, role: "admin" as const, joined_at: "2025-06-01" },
  ],
};

describe("MembershipsTab", () => {
  it("renders rows for each membership", () => {
    render(wrap(<MembershipsTab user={user} />));
    expect(screen.getByText("ava's org")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
  });

  it("marks personal org as locked", () => {
    render(wrap(<MembershipsTab user={user} />));
    const personalRow = screen.getByTestId("membership-row-org-personal");
    expect(personalRow).toHaveTextContent(/personal/i);
    expect(personalRow).toHaveTextContent(/locked/i);
  });

  it("calls updateRole when role changes", async () => {
    render(wrap(<MembershipsTab user={user} />));
    await userEvent.click(screen.getByTestId("role-picker-trigger-org-team"));
    await userEvent.click(screen.getByTestId("role-option-viewer"));
    expect(mockUpdateRole).toHaveBeenCalledWith(
      expect.objectContaining({ orgId: "org-team", userId: "u1", role: "viewer" }),
      expect.anything(),
    );
  });

  it("confirms and removes when Remove clicked", async () => {
    render(wrap(<MembershipsTab user={user} />));
    await userEvent.click(screen.getByTestId("remove-org-team"));
    await userEvent.click(await screen.findByRole("button", { name: /confirm/i }));
    expect(mockRemoveMember).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run — fails**

- [ ] **Step 3: Implement**

```tsx
// MembershipsTab.tsx
import { useState } from "react";
import type { UserDetail } from "@/controllers/API/queries/admin/use-get-user";
import RolePicker from "@/components/common/rolePicker";
import { useUpdateMemberRole } from "@/controllers/API/queries/admin/use-update-member-role";
import { useRemoveMember } from "@/controllers/API/queries/admin/use-remove-member";  // existing hook
import { Button } from "@/components/ui/button";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import AddToOrganizationDialog from "./AddToOrganizationDialog";
import type { MembershipRole } from "@/constants/roles";

export default function MembershipsTab({ user }: { user: UserDetail }) {
  const [addOpen, setAddOpen] = useState(false);
  const { mutate: updateRole } = useUpdateMemberRole();
  const { mutate: removeMember } = useRemoveMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);
  // Platform admins viewing this page always have platform_admin-level authority.
  const callerRole = user.is_platform_admin ? "platform_admin" as const : "platform_admin" as const;
  // (The page is platform-admin-gated, so we can assume platform_admin.)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Organizations this user belongs to
        </span>
        <Button onClick={() => setAddOpen(true)}>+ Add to organization</Button>
      </div>
      <div className="border rounded-md overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50 text-left text-sm">
            <tr>
              <th className="px-3 py-2">Organization</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Joined</th>
              <th className="px-3 py-2 w-28" />
            </tr>
          </thead>
          <tbody>
            {user.memberships.map((m) => (
              <tr
                key={m.organization_id}
                className="border-t text-sm"
                data-testid={`membership-row-${m.organization_id}`}
              >
                <td className="px-3 py-2">
                  {m.organization_name}
                  {m.is_personal && (
                    <span className="ml-2 text-xs text-muted-foreground">(personal)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {m.is_personal ? (
                    <span>Owner <span className="text-muted-foreground text-xs">(locked)</span></span>
                  ) : (
                    <div data-testid-wrapper={`role-picker-${m.organization_id}`}>
                      <RolePicker
                        caller={callerRole}
                        current={m.role as MembershipRole}
                        onSelect={(next) =>
                          updateRole(
                            { orgId: m.organization_id, userId: user.id, role: next },
                            {
                              onSuccess: () => setSuccess({ title: "Role updated" }),
                              onError: (e: any) =>
                                setError({ title: "Role change failed",
                                           list: [e?.response?.data?.detail ?? String(e)] }),
                            },
                          )
                        }
                      />
                    </div>
                  )}
                </td>
                <td className="px-3 py-2">{m.joined_at?.slice(0, 10)}</td>
                <td className="px-3 py-2 text-right">
                  {m.is_personal ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    <ConfirmationModal
                      size="x-small"
                      title="Remove"
                      titleHeader="Remove from organization"
                      cancelText="Cancel"
                      confirmationText="Confirm"
                      icon="Trash2"
                      data={m}
                      index={0}
                      onConfirm={() =>
                        removeMember(
                          { orgId: m.organization_id, userId: user.id } as any,
                          {
                            onSuccess: () => setSuccess({ title: "Member removed" }),
                            onError: (e: any) =>
                              setError({ title: "Remove failed",
                                         list: [e?.response?.data?.detail ?? String(e)] }),
                          },
                        )
                      }
                    >
                      <ConfirmationModal.Content>
                        Remove this user from {m.organization_name}?
                      </ConfirmationModal.Content>
                      <ConfirmationModal.Trigger>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600"
                          data-testid={`remove-${m.organization_id}`}
                        >
                          Remove
                        </Button>
                      </ConfirmationModal.Trigger>
                    </ConfirmationModal>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <AddToOrganizationDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        user={user}
      />
    </div>
  );
}
```

```tsx
// AddToOrganizationDialog.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAddMember } from "@/controllers/API/queries/admin/use-add-member"; // existing
import RolePicker from "@/components/common/rolePicker";
import useAlertStore from "@/stores/alertStore";
import type { MembershipRole } from "@/constants/roles";
import type { UserDetail } from "@/controllers/API/queries/admin/use-get-user";

export default function AddToOrganizationDialog({
  open, onClose, user,
}: {
  open: boolean; onClose: () => void; user: UserDetail;
}) {
  const [q, setQ] = useState("");
  const [selectedOrg, setSelectedOrg] = useState<{ id: string; name: string } | null>(null);
  const [role, setRole] = useState<MembershipRole>("member");

  const existingOrgIds = new Set(user.memberships.map(m => m.organization_id));
  const { data } = useQuery({
    queryKey: ["admin", "orgs", q],
    queryFn: async () => {
      const r = await api.get("/api/v1/admin/organizations", { params: { q } });
      return r.data.items as { id: string; name: string }[];
    },
    enabled: open,
  });

  const candidates = (data ?? []).filter(o => !existingOrgIds.has(o.id));

  const { mutate: addMember } = useAddMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add to organization</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <Input placeholder="Search organizations..." value={q} onChange={(e) => setQ(e.target.value)} />
          <ul className="max-h-48 overflow-auto border rounded">
            {candidates.map(o => (
              <li
                key={o.id}
                className={`px-3 py-2 cursor-pointer hover:bg-muted ${selectedOrg?.id === o.id ? "bg-muted" : ""}`}
                onClick={() => setSelectedOrg(o)}
              >
                {o.name}
              </li>
            ))}
            {candidates.length === 0 && <li className="px-3 py-2 text-muted-foreground">No matches.</li>}
          </ul>
          <div>
            <div className="text-xs uppercase mb-1 text-muted-foreground">Role</div>
            <RolePicker caller="platform_admin" current={role} onSelect={setRole} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            disabled={!selectedOrg}
            onClick={() =>
              selectedOrg && addMember(
                { orgId: selectedOrg.id, userId: user.id, role } as any,
                {
                  onSuccess: () => { setSuccess({ title: "Added to org" }); onClose(); },
                  onError: (e: any) =>
                    setError({ title: "Add failed",
                               list: [e?.response?.data?.detail ?? String(e)] }),
                },
              )
            }
          >
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Rerun**

```bash
cd src/frontend && npm test -- UserDetailPage
```

- [ ] **Step 5: Manual smoke**

Log in as platform admin → open user detail → try role change + add-to-org + remove.

- [ ] **Step 6: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/UserDetailPage/MembershipsTab.tsx \
  src/frontend/src/pages/AdminPage/UserDetailPage/AddToOrganizationDialog.tsx \
  src/frontend/src/pages/AdminPage/UserDetailPage/__tests__/MembershipsTab.test.tsx
git commit -m "feat(frontend): MembershipsTab + AddToOrganizationDialog"
```

---

### Task 18: `OrgMemberDetailPage` (org-admin scoped view)

**Files:**
- Create: `src/frontend/src/pages/AdminPage/organizations/OrgMemberDetailPage.tsx`
- Create: `src/frontend/src/pages/AdminPage/organizations/__tests__/OrgMemberDetailPage.test.tsx`
- Modify: `src/frontend/src/routes.tsx`

- [ ] **Step 1: Register route**

```tsx
{
  path: "settings/organizations/:orgId/members/:userId",
  element: <OrgMemberDetailPage />,
}
```

Guard: platform admin OR Owner/Admin of the org. Mirror how `OrganizationDetailPage` is gated — likely a hook that checks the caller's membership in `:orgId`.

- [ ] **Step 2: Failing test**

```tsx
// OrgMemberDetailPage.test.tsx
import { render, screen } from "@testing-library/react";
import OrgMemberDetailPage from "../OrgMemberDetailPage";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

jest.mock("@/controllers/API/queries/admin/use-get-organization", () => ({
  useGetOrganization: () => ({
    data: {
      id: "org-team", name: "Team",
      members: [
        { user_id: "u1", username: "ava", role: "admin", is_active: true },
      ],
    },
    isPending: false,
  }),
}));

const qc = new QueryClient();

it("renders scoped member view", () => {
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/settings/organizations/org-team/members/u1"]}>
        <Routes>
          <Route path="/settings/organizations/:orgId/members/:userId" element={<OrgMemberDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText("ava")).toBeInTheDocument();
  expect(screen.getByText(/active/i)).toBeInTheDocument();
  // Should NOT render platform-admin pill or other-org data.
  expect(screen.queryByText(/platform admin/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Implement**

```tsx
// OrgMemberDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useGetOrganization } from "@/controllers/API/queries/admin/use-get-organization";
import { useUpdateMemberRole } from "@/controllers/API/queries/admin/use-update-member-role";
import { useRemoveMember } from "@/controllers/API/queries/admin/use-remove-member";
import RolePicker from "@/components/common/rolePicker";
import { Button } from "@/components/ui/button";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import CustomLoader from "@/customization/components/custom-loader";
import useAuthStore from "@/stores/authStore";
import type { MembershipRole } from "@/constants/roles";

export default function OrgMemberDetailPage() {
  const { orgId = "", userId = "" } = useParams();
  const navigate = useNavigate();
  const { data: org, isPending } = useGetOrganization(orgId);
  const { mutate: updateRole } = useUpdateMemberRole();
  const { mutate: removeMember } = useRemoveMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const currentUser = useAuthStore((s) => s.userData);
  const callerMembership = org?.members.find((m: any) => m.user_id === currentUser?.id);
  const callerRole: MembershipRole | "platform_admin" =
    currentUser?.is_platform_admin ? "platform_admin" : (callerMembership?.role ?? "viewer");

  if (isPending) return <CustomLoader remSize={12} />;
  if (!org) return <div>Organization not found.</div>;
  const member = org.members.find((m: any) => m.user_id === userId);
  if (!member) return <div>Member not found.</div>;

  return (
    <div className="p-6 max-w-2xl">
      <button className="text-sm text-muted-foreground hover:underline mb-4"
              onClick={() => navigate(`/settings/organizations/${orgId}`)}>
        ← Back to {org.name}
      </button>
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-semibold">
          {member.username.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="font-semibold">{member.username}</div>
          <div className="text-sm text-muted-foreground">
            Joined {org.name}
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
          member.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
        }`}>
          ● {member.is_active ? "Active" : "Inactive"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="border rounded p-3">
          <div className="text-xs uppercase text-muted-foreground mb-1">Role in {org.name}</div>
          <RolePicker
            caller={callerRole}
            current={member.role}
            onSelect={(next) =>
              updateRole(
                { orgId, userId, role: next },
                {
                  onSuccess: () => setSuccess({ title: "Role updated" }),
                  onError: (e: any) =>
                    setError({ title: "Role change failed",
                               list: [e?.response?.data?.detail ?? String(e)] }),
                },
              )
            }
          />
        </div>
        <div className="border rounded p-3 border-red-200">
          <div className="text-xs uppercase text-red-600 mb-1">Remove from org</div>
          <ConfirmationModal
            size="x-small"
            title="Remove"
            titleHeader="Remove from organization"
            cancelText="Cancel"
            confirmationText="Confirm"
            icon="Trash2"
            data={member}
            index={0}
            onConfirm={() =>
              removeMember(
                { orgId, userId } as any,
                {
                  onSuccess: () => {
                    setSuccess({ title: "Member removed" });
                    navigate(`/settings/organizations/${orgId}`);
                  },
                  onError: (e: any) =>
                    setError({ title: "Remove failed",
                               list: [e?.response?.data?.detail ?? String(e)] }),
                },
              )
            }
          >
            <ConfirmationModal.Content>
              Remove {member.username} from {org.name}?
            </ConfirmationModal.Content>
            <ConfirmationModal.Trigger>
              <Button variant="destructive" size="sm">Remove</Button>
            </ConfirmationModal.Trigger>
          </ConfirmationModal>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-6">
        Org admins cannot toggle Active, Platform Admin, or see memberships in other orgs.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Test + smoke**

```bash
cd src/frontend && npm test -- organizations/__tests__/OrgMemberDetailPage
```

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/organizations/OrgMemberDetailPage.tsx \
  src/frontend/src/pages/AdminPage/organizations/__tests__/OrgMemberDetailPage.test.tsx \
  src/frontend/src/routes.tsx
git commit -m "feat(frontend): OrgMemberDetailPage scoped view"
```

**Phase 4 checkpoint** — detail pages functional end-to-end.

---

## Phase 5 — Existing Page Updates

### Task 19: `UsersPage` rows link to detail

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/UsersPage.tsx:348-500` (row body)

- [ ] **Step 1: Wrap each row's username (or add a View icon) with a link**

Edit the username cell (around line 355):

```tsx
<TableCell className="truncate py-2">
  <ShadTooltip content={user.username}>
    <button
      className="cursor-pointer hover:underline text-left"
      onClick={() => navigate(`/admin/users/${user.id}`)}
    >
      {user.username}
    </button>
  </ShadTooltip>
</TableCell>
```

Add `useNavigate` import and `const navigate = useNavigate();` at top of the component.

- [ ] **Step 2: Verify build, run the page, click a row, land on the detail page.**

- [ ] **Step 3: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/UsersPage.tsx
git commit -m "feat(admin): UsersPage row links to user detail"
```

---

### Task 20: `OrganizationMembersTab` — RoleBadge + link

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/organizations/OrganizationMembersTab.tsx`

- [ ] **Step 1: Replace role text with `RoleBadge`**

Find the column that renders `{m.role}` or `{member.role}` and replace with:

```tsx
<RoleBadge role={m.role as MembershipRole} />
```

Add import: `import RoleBadge from "@/components/common/roleBadge";` and `import type { MembershipRole } from "@/constants/roles";`

- [ ] **Step 2: Make the username cell a link**

```tsx
<button
  className="text-left hover:underline"
  onClick={() => navigate(`/settings/organizations/${orgId}/members/${m.user_id}`)}
>
  {m.username}
</button>
```

- [ ] **Step 3: Remove the old inline role-edit control**

Any per-row role-edit dropdown inline in the members table is now the member detail page's job. Delete that piece; keep only the badge + link-to-detail.

- [ ] **Step 4: Run existing tests, verify nothing broke**

```bash
cd src/frontend && npm test -- organizations/
```

- [ ] **Step 5: Propose commit**

```bash
git add src/frontend/src/pages/AdminPage/organizations/OrganizationMembersTab.tsx
git commit -m "feat(admin): members table uses RoleBadge + row link"
```

**Phase 5 checkpoint** — admin UI fully navigable to the new detail pages.

---

## Phase 6 — Flow & Folder Ownership Transition

### Task 21: Audit existing `user_id == current_user` checks

**Files:**
- Read-only pass; produce a markdown file listing every endpoint + line to modify.

- [ ] **Step 1: Grep**

```bash
grep -rn "user_id == current_user" src/backend/base/langflow/api/ src/lfx/src/lfx/ || true
grep -rn "current_user.id" src/backend/base/langflow/api/v1/flows* || true
grep -rn "current_user.id" src/backend/base/langflow/api/v1/folders* || true
```

- [ ] **Step 2: Build the worklist**

Create `docs/superpowers/plans/2026-04-22-flow-ownership-worklist.md`:

```md
# Flow/Folder Ownership Worklist

Each entry: `file:line — current check → replacement`.
- `src/backend/base/langflow/api/v1/flows.py:NN — select(Flow).where(Flow.user_id == current_user.id) → select(Flow).where(Flow.organization_id == current_org.id)`
- ...
```

Every site gets an explicit plan. Expect ~15-25 sites across flows + folders + build + run + stream.

- [ ] **Step 3: Propose commit**

```bash
git add docs/superpowers/plans/2026-04-22-flow-ownership-worklist.md
git commit -m "docs: flow/folder ownership transition worklist"
```

---

### Task 22: Flow CRUD — read endpoints (Viewer+)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (list flows, get flow)
- Create: `src/backend/tests/unit/api/v1/test_flow_role_enforcement.py`

- [ ] **Step 1: Failing test**

```python
# test_flow_role_enforcement.py
import pytest
from httpx import AsyncClient


@pytest.mark.parametrize("caller_role,expected", [
    ("owner", 200), ("admin", 200), ("member", 200),
    ("operator", 200), ("viewer", 200),
])
async def test_list_flows_all_roles_can_read(
    client: AsyncClient, role_token, org_with_flow, caller_role, expected
):
    token = role_token(caller_role, org_with_flow.org_id)
    r = await client.get(
        "/api/v1/flows/",
        headers={"Authorization": f"Bearer {token}"},
        params={"organization_id": str(org_with_flow.org_id)},
    )
    assert r.status_code == expected


async def test_get_flow_403_for_non_member(
    client: AsyncClient, outside_user_token, org_with_flow
):
    r = await client.get(
        f"/api/v1/flows/{org_with_flow.flow_id}",
        headers={"Authorization": f"Bearer {outside_user_token}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Update the list-flows endpoint**

Find the current handler (likely wrapped around `Flow.user_id == current_user.id`). Replace the where-clause with an org-membership join:

```python
from langflow.api.utils.authz import assert_org_role
from langflow.services.database.models.membership.model import Membership, MembershipRole

# existing list endpoint
@router.get("/")
async def read_flows(
    current_user: CurrentActiveUser,
    session: DbSession,
    organization_id: UUID | None = None,
    ...
):
    if organization_id is not None:
        await assert_org_role(current_user, organization_id, MembershipRole.VIEWER, session=session)
        stmt = select(Flow).where(Flow.organization_id == organization_id)
    else:
        # All flows in orgs the user is a member of.
        org_ids = (await session.exec(
            select(Membership.organization_id).where(Membership.user_id == current_user.id)
        )).all()
        stmt = select(Flow).where(Flow.organization_id.in_(org_ids))
        if current_user.is_platform_admin:
            stmt = select(Flow)  # platform admin sees all
    flows = (await session.exec(stmt)).all()
    return flows
```

Exact shape depends on current signature — preserve existing query params, pagination, ordering.

- [ ] **Step 3: Update `read_flow` (single)**

```python
@router.get("/{flow_id}")
async def read_flow(
    flow_id: UUID, current_user: CurrentActiveUser, session: DbSession,
) -> Flow:
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.VIEWER, session=session)
    return flow
```

- [ ] **Step 4: Run tests — pass**

- [ ] **Step 5: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py \
  src/backend/tests/unit/api/v1/test_flow_role_enforcement.py
git commit -m "feat(flows): org-role gate on list/read (Viewer+)"
```

---

### Task 23: Flow CRUD — write endpoints (Member+)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (create/update/delete)

- [ ] **Step 1: Extend the test file**

```python
@pytest.mark.parametrize("caller_role,expected", [
    ("owner", 200), ("admin", 200), ("member", 200),
    ("operator", 403), ("viewer", 403),
])
async def test_update_flow_role_matrix(
    client, role_token, org_with_flow, caller_role, expected
):
    token = role_token(caller_role, org_with_flow.org_id)
    r = await client.patch(
        f"/api/v1/flows/{org_with_flow.flow_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "renamed"},
    )
    assert r.status_code == expected


@pytest.mark.parametrize("caller_role,expected", [
    ("owner", 204), ("admin", 204), ("member", 204),
    ("operator", 403), ("viewer", 403),
])
async def test_delete_flow_role_matrix(
    client, role_token, org_with_flow, caller_role, expected
):
    token = role_token(caller_role, org_with_flow.org_id)
    r = await client.delete(
        f"/api/v1/flows/{org_with_flow.flow_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected


@pytest.mark.parametrize("caller_role,expected", [
    ("owner", 201), ("admin", 201), ("member", 201),
    ("operator", 403), ("viewer", 403),
])
async def test_create_flow_role_matrix(
    client, role_token, org_with_member, caller_role, expected
):
    token = role_token(caller_role, org_with_member.org_id)
    r = await client.post(
        "/api/v1/flows/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "new flow", "organization_id": str(org_with_member.org_id)},
    )
    assert r.status_code == expected
```

- [ ] **Step 2: Update each write endpoint**

For `create_flow`, `update_flow`, `delete_flow`:

```python
@router.post("/", response_model=FlowRead, status_code=201)
async def create_flow(body: FlowCreate, current_user: CurrentActiveUser, session: DbSession):
    await assert_org_role(current_user, body.organization_id, MembershipRole.MEMBER, session=session)
    flow = Flow.model_validate({**body.model_dump(), "user_id": current_user.id})
    session.add(flow)
    await session.flush()
    return flow


@router.patch("/{flow_id}", response_model=FlowRead)
async def update_flow(flow_id: UUID, body: FlowUpdate, current_user: CurrentActiveUser, session: DbSession):
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(404)
    await assert_org_role(current_user, flow.organization_id, MembershipRole.MEMBER, session=session)
    # DROP the old `if flow.user_id != current_user.id: raise 403` check.
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(flow, k, v)
    await session.flush()
    return flow


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(flow_id: UUID, current_user: CurrentActiveUser, session: DbSession):
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(404)
    await assert_org_role(current_user, flow.organization_id, MembershipRole.MEMBER, session=session)
    await cascade_delete_flow(session, flow_id)
```

Keep exact signatures and response models as they currently stand — only swap the authorization check.

- [ ] **Step 3: Tests pass**

- [ ] **Step 4: Propose commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py \
  src/backend/tests/unit/api/v1/test_flow_role_enforcement.py
git commit -m "feat(flows): org-role gate on create/update/delete (Member+)"
```

---

### Task 24: Folder CRUD — same transition

**Files:**
- Modify: `src/backend/base/langflow/api/v1/folders.py` (or the file that hosts folder endpoints)

- [ ] **Step 1: Extend tests** for folder create/update/delete with same matrix, same expected outcomes.

- [ ] **Step 2: Apply same transformation** — Viewer+ on read; Member+ on create/update/delete; drop `user_id == current_user.id` checks.

- [ ] **Step 3: Propose commit**

```bash
git commit -m "feat(folders): org-role gate replacing per-user ownership"
```

---

### Task 25: Flow execution — Operator+

**Files:**
- Modify: build/run/stream endpoints (likely `src/backend/base/langflow/api/v1/endpoints.py` and/or `chat.py` — grep for `/build/` and `/run/` registrations)

- [ ] **Step 1: Extend tests**

```python
@pytest.mark.parametrize("caller_role,expected_any_of", [
    ("owner",    (200, 202)),
    ("admin",    (200, 202)),
    ("member",   (200, 202)),
    ("operator", (200, 202)),
    ("viewer",   (403,)),
])
async def test_run_flow_role_matrix(
    client, role_token, org_with_flow, caller_role, expected_any_of
):
    token = role_token(caller_role, org_with_flow.org_id)
    r = await client.post(
        f"/api/v1/run/{org_with_flow.flow_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"input_value": "hi"},
    )
    assert r.status_code in expected_any_of
```

- [ ] **Step 2: Add `assert_org_role(..., MembershipRole.OPERATOR, ...)` to every execution endpoint**

For each flagged endpoint (build, run, run-public, stream, cancel):

```python
flow = await session.get(Flow, flow_id)
if flow is None: raise HTTPException(404)
await assert_org_role(current_user, flow.organization_id, MembershipRole.OPERATOR, session=session)
```

Apply only after resolving the flow — skip `X-Public-Flow`-style anonymous paths, which must stay unauthenticated.

- [ ] **Step 3: Tests pass**

- [ ] **Step 4: Propose commit**

```bash
git commit -m "feat(flows): Operator+ gate on run/build/stream endpoints"
```

---

### Task 26: UI — drop "my flows" user-id filter if present

**Files:**
- Search: `grep -rn "user_id" src/frontend/src/pages/`

- [ ] **Step 1: Find client-side filters** that pass `user_id=<self>` to flow list queries. Most common location: the flows page (`src/frontend/src/pages/MainPage/` or similar).

- [ ] **Step 2: Replace with org-scoped listing.** The backend already returns flows for all orgs the user is in. If the UI had a "My Flows" tab, rename to "Recent" or remove.

- [ ] **Step 3: Verify manually**

Start dev server. Confirm:
- Flow list shows flows from all orgs the user is a member of.
- No broken empty-states due to removed filters.

- [ ] **Step 4: Propose commit**

```bash
git commit -m "feat(frontend): flow list scoped to org membership, not user_id"
```

**Phase 6 checkpoint** — flows/folders fully org-owned. Users with no personal flows but `Member` role on a team org can now see and edit that org's shared flows.

---

## Phase 7 — Verification

### Task 27: End-to-end verification pass

- [ ] **Step 1: Backend full test suite**

```bash
uv run pytest src/backend/tests/unit/ -q
```
Expected: all green, no regressions.

- [ ] **Step 2: Frontend test suite**

```bash
cd src/frontend && npm test -- --watchAll=false
```
Expected: all green.

- [ ] **Step 3: Manual smoke — platform admin flow**

1. Log in as platform admin.
2. Navigate `/admin/users` → click a user → User Detail Page opens.
3. Toggle `is_active`; confirm persists on reload.
4. Toggle `is_platform_admin`; confirm persists.
5. Open Memberships tab; change a role via `RolePicker`; confirm persists.
6. "+ Add to organization" → add user to a second org with role Member; confirm row appears.
7. Remove user from that org; confirm row disappears.
8. Navigate `/settings/organizations/<org>/members/<user>`; confirm scoped view renders without the Platform Admin pill.

- [ ] **Step 4: Manual smoke — org admin flow**

1. Log in as a non-platform-admin user who is Admin in one org and Viewer in another.
2. Navigate to `/settings/organizations/<admin-org>/members/<some-user>` — scoped view loads.
3. Role-picker allows Member/Operator/Viewer, disables Admin and Owner.
4. Remove works; last-Owner guard blocks removing the sole Owner.
5. Navigate to `/admin/users/<id>` — page gate should redirect or 403 (not a platform admin).

- [ ] **Step 5: Manual smoke — flow ownership**

1. Create a second user.
2. Add them to your org as Member.
3. Log in as that second user.
4. Confirm they see your flows in that org and can edit/run them.
5. Demote to Viewer; confirm edit/run buttons disabled or endpoint 403s.
6. Demote to Operator; confirm read + run work but edit is blocked.

- [ ] **Step 6: Propose final commit batch or PR**

Batch up any outstanding changes; ask user before committing or opening a PR.

---

## Self-Review Checklist (post-plan)

Before declaring the plan done, the author walked back through the spec:

- [x] `MembershipRole` enum extension — Task 1.
- [x] Migrations (enum + FK) — Tasks 2, 3.
- [x] `ROLE_ORDER`, `require_org_role`, `assert_org_role` helpers — Task 4.
- [x] `GET /admin/users/{user_id}` — Task 5.
- [x] `PATCH /admin/organizations/{org_id}/members/{user_id}` — Task 6.
- [x] Relaxed gates on add/remove member + last-Owner guard — Task 7.
- [x] `is_active` on `MemberRow` — Task 8.
- [x] Verify `PATCH /users/{user_id}` accepts `is_platform_admin` — Task 9.
- [x] Frontend role metadata + `canAssignRole` — Task 10.
- [x] `RoleBadge` — Task 11.
- [x] `RolePicker` — Task 12.
- [x] `useGetUser` — Task 13.
- [x] `useUpdateMemberRole` — Task 14.
- [x] `UserDetailPage` shell + route — Task 15.
- [x] `AccountTab` — Task 16.
- [x] `MembershipsTab` + `AddToOrganizationDialog` — Task 17.
- [x] `OrgMemberDetailPage` — Task 18.
- [x] Existing pages: UsersPage + OrganizationMembersTab linkage — Tasks 19, 20.
- [x] Flow CRUD role gates (read Viewer+, write Member+) — Tasks 22, 23.
- [x] Folder CRUD role gates — Task 24.
- [x] Flow execution Operator+ — Task 25.
- [x] "My Flows" UI filter drop — Task 26.
- [x] End-to-end verification — Task 27.

**Not covered (deliberately deferred per spec Non-Goals / Known Gaps):**
- API keys, variables, files, deployments, flow_runs, messages, transactions, jobs, vertex_builds — stay per-user.
- Active session revocation on is_active=false — best-effort on next request only.
- Org transfer endpoint.
- Billing-role gating.
- Per-flow sharing.
