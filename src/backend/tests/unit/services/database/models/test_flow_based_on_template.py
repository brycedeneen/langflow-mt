"""Unit tests for Flow.based_on_template_flow_id column."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, Organization, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    # Enable FK constraints so ON DELETE SET NULL actually fires on SQLite
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        sess.exec(text("PRAGMA foreign_keys=ON"))
        yield sess


def _org(s: Session) -> Organization:
    o = Organization(name="test-org", slug="test-org-slug")
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


def _user(s: Session) -> User:
    u = User(username="u", password="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def test_based_on_template_flow_id_defaults_to_none(session):
    user = _user(session)
    org = _org(session)
    flow = Flow(name="F", user_id=user.id, organization_id=org.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.based_on_template_flow_id is None


def test_based_on_template_flow_id_persists_and_loads(session):
    user = _user(session)
    org = _org(session)
    template = Flow(name="T", user_id=user.id, organization_id=org.id)
    session.add(template)
    session.commit()
    session.refresh(template)

    clone = Flow(
        name="C",
        user_id=user.id,
        organization_id=org.id,
        based_on_template_flow_id=template.id,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)

    loaded = session.exec(select(Flow).where(Flow.id == clone.id)).one()
    assert loaded.based_on_template_flow_id == template.id


def test_template_delete_nulls_pointer_on_clones(session):
    user = _user(session)
    org = _org(session)
    template = Flow(name="T", user_id=user.id, organization_id=org.id)
    session.add(template)
    session.commit()
    session.refresh(template)

    clone = Flow(
        name="C",
        user_id=user.id,
        organization_id=org.id,
        based_on_template_flow_id=template.id,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)

    session.delete(template)
    session.commit()

    refreshed = session.exec(select(Flow).where(Flow.id == clone.id)).one()
    assert refreshed.based_on_template_flow_id is None
    # Clone itself still exists
    assert refreshed.name == "C"
