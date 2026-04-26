"""TDD test for list_user_variables org isolation.

Verifies that FlowInspectionTools.list_user_variables only returns variable
names that belong to the calling user's organization — not variables the user
owns in a different org.

Does NOT mock the DB — goes through the real VariableService and DatabaseSession
to verify end-to-end filtering.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import delete as sa_delete

from langflow.services.assistant.tools.inspection import FlowInspectionTools
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_variable_service, session_scope
from langflow.services.auth.utils import get_password_hash
from langflow.services.variable.constants import CREDENTIAL_TYPE


@pytest.mark.asyncio
async def test_list_user_variables_filters_by_org(client):  # noqa: ARG001
    """Variables created under org_B must not leak to a tool scoped to org_A.

    Setup:
    - user_A is a member of org_A and org_B (deliberately — worst-case scenario).
    - Variable "var_in_org_A" created with user_id=user_A.id, organization_id=org_A.id
    - Variable "var_in_org_B" created with user_id=user_A.id, organization_id=org_B.id
    - FlowInspectionTools constructed with user_id=user_A.id, org_id=org_A.id
    - list_user_variables() must return ["var_in_org_A"], NOT "var_in_org_B".
    """
    slug = uuid4().hex[:8]
    var_a_id = None
    var_b_id = None
    user_id = None
    org_a_id = None
    org_b_id = None

    # -- Setup ----------------------------------------------------------------
    async with session_scope() as session:
        org_a = Organization(
            name=f"test-org-a-{slug}",
            slug=f"test-org-a-{slug}",
            is_personal=False,
        )
        org_b = Organization(
            name=f"test-org-b-{slug}",
            slug=f"test-org-b-{slug}",
            is_personal=False,
        )
        session.add_all([org_a, org_b])
        await session.flush()

        user_a = User(
            username=f"user-a-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
        )
        session.add(user_a)
        await session.flush()

        # user_a is a member of both orgs (worst-case cross-org leak scenario)
        session.add_all([
            Membership(user_id=user_a.id, organization_id=org_a.id, role=MembershipRole.MEMBER),
            Membership(user_id=user_a.id, organization_id=org_b.id, role=MembershipRole.MEMBER),
        ])
        await session.flush()

        # Create the variable service to create variables with proper encryption
        svc = get_variable_service()
        var_a = await svc.create_variable(
            user_id=user_a.id,
            name="var_in_org_A",
            value="secret_a",
            type_=CREDENTIAL_TYPE,
            session=session,
            organization_id=org_a.id,
        )
        var_b = await svc.create_variable(
            user_id=user_a.id,
            name="var_in_org_B",
            value="secret_b",
            type_=CREDENTIAL_TYPE,
            session=session,
            organization_id=org_b.id,
        )
        await session.commit()

        # Capture IDs for cleanup
        user_id = user_a.id
        org_a_id = org_a.id
        org_b_id = org_b.id
        var_a_id = var_a.id
        var_b_id = var_b.id

    # -- Execute --------------------------------------------------------------
    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        user_id=user_id,
        org_id=org_a_id,
    )
    result = await tools.list_user_variables()

    # -- Assert ---------------------------------------------------------------
    assert "error" not in result, f"Unexpected error: {result}"
    names = result["variable_names"]
    assert "var_in_org_A" in names, f"Expected var_in_org_A in {names}"
    assert "var_in_org_B" not in names, (
        f"LEAK: var_in_org_B from a different org must NOT appear in {names}"
    )

    # -- Cleanup --------------------------------------------------------------
    async with session_scope() as session:
        await session.exec(
            sa_delete(Variable).where(Variable.id.in_([var_a_id, var_b_id]))
        )
        await session.exec(
            sa_delete(Membership).where(Membership.user_id == user_id)
        )
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
        for org_id_to_del in [org_a_id, org_b_id]:
            org = await session.get(Organization, org_id_to_del)
            if org:
                await session.delete(org)
        await session.commit()
