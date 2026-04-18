"""Unit tests for starter-project detection helper."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models import Flow, Folder, Organization, User
from langflow.services.database.models.flow.starter import (
    STARTER_FOLDER_NAME,
    is_flow_a_starter_project,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
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


def _organization(s: Session) -> Organization:
    org = Organization(name="test_org", slug="test_org")
    s.add(org)
    s.commit()
    s.refresh(org)
    return org


def _user(s: Session) -> User:
    u = User(username="u", password="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def test_flow_in_starter_folder_is_a_starter(session):
    org = _organization(session)
    user = _user(session)
    starter = Folder(name=STARTER_FOLDER_NAME, user_id=user.id, organization_id=org.id)
    session.add(starter)
    session.commit()
    session.refresh(starter)

    flow = Flow(name="f", user_id=user.id, organization_id=org.id, folder_id=starter.id, data={"nodes": [], "edges": []})
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is True


def test_flow_in_other_folder_is_not_a_starter(session):
    org = _organization(session)
    user = _user(session)
    other = Folder(name="My Projects", user_id=user.id, organization_id=org.id)
    session.add(other)
    session.commit()
    session.refresh(other)

    flow = Flow(name="f", user_id=user.id, organization_id=org.id, folder_id=other.id, data={"nodes": [], "edges": []})
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is False


def test_flow_without_folder_is_not_a_starter(session):
    org = _organization(session)
    user = _user(session)
    flow = Flow(name="f", user_id=user.id, organization_id=org.id, data={"nodes": [], "edges": []})
    session.add(flow)
    session.commit()
    session.refresh(flow)

    assert is_flow_a_starter_project(flow, session) is False
