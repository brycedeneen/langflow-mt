"""Unit tests for the built_with_assist flag on Flow."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, Organization, User


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


def _organization(s: Session) -> Organization:
    org = Organization(name="org", slug="org-slug")
    s.add(org)
    s.commit()
    s.refresh(org)
    return org


def test_built_with_assist_defaults_to_false(session):
    user = _user(session)
    org = _organization(session)
    flow = Flow(name="F", user_id=user.id, organization_id=org.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.built_with_assist is False


def test_built_with_assist_is_persistable_and_readable(session):
    user = _user(session)
    org = _organization(session)
    flow = Flow(name="F", user_id=user.id, organization_id=org.id, built_with_assist=True)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.built_with_assist is True

    loaded = session.exec(select(Flow).where(Flow.id == flow.id)).one()
    assert loaded.built_with_assist is True
