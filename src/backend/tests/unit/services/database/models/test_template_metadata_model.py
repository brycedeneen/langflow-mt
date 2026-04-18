"""Unit tests for TemplateMetadata SQLModel."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, Organization, TemplateMetadata, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Enable foreign key constraints for SQLite
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def _make_user(session: Session) -> User:
    user = User(username="admin", password="x", is_superuser=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_organization(session: Session) -> Organization:
    org = Organization(name="test_org", slug="test_org")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _make_flow(session: Session, user: User, org: Organization) -> Flow:
    flow = Flow(
        name="Onboarding",
        user_id=user.id,
        organization_id=org.id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    session.commit()
    session.refresh(flow)
    return flow


def test_template_metadata_row_can_be_created(session):
    user = _make_user(session)
    org = _make_organization(session)
    flow = _make_flow(session, user, org)

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
    org = _make_organization(session)
    flow = _make_flow(session, user, org)

    session.add(TemplateMetadata(flow_id=flow.id, updated_by=user.id))
    session.commit()

    duplicate = TemplateMetadata(flow_id=flow.id, updated_by=user.id)
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_metadata_cascade_deletes_with_flow(session):
    user = _make_user(session)
    org = _make_organization(session)
    flow = _make_flow(session, user, org)
    session.add(TemplateMetadata(flow_id=flow.id, updated_by=user.id))
    session.commit()

    session.delete(flow)
    session.commit()

    rows = session.exec(select(TemplateMetadata)).all()
    assert rows == []


def test_template_metadata_updated_at_autobumps(session):
    user = _make_user(session)
    org = _make_organization(session)
    flow = _make_flow(session, user, org)
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
