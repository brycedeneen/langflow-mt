"""Unit tests for the Template SQLModel."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models import Organization, User
from langflow.services.database.models.template.model import Template


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def test_template_name_is_required(session):
    # SQLModel fields with sa_column defer NOT NULL validation to flush time,
    # so we must commit to trigger the constraint violation.
    t = Template(nodes=[], edges=[], created_by=uuid.uuid4(), updated_by=uuid.uuid4())  # type: ignore[call-arg]
    session.add(t)
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_scope_defaults_to_platform():
    t = Template(
        name="test",
        nodes=[],
        edges=[],
        created_by=uuid.uuid4(),
        updated_by=uuid.uuid4(),
    )
    assert t.scope == "platform"
    assert t.org_id is None


def test_template_org_scope_requires_non_null_org_id(session):
    """Committing a row with scope='org' and org_id=None must violate the CHECK constraint."""
    user = User(username="admin", password="x", is_superuser=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    t = Template(
        name="bad-org",
        scope="org",
        org_id=None,
        nodes=[],
        edges=[],
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(t)
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_platform_scope_requires_null_org_id(session):
    """Committing a row with scope='platform' and a non-null org_id must violate the CHECK constraint."""
    user = User(username="admin2", password="x", is_superuser=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    org = Organization(name="some_org", slug="some-org")
    session.add(org)
    session.commit()
    session.refresh(org)

    t = Template(
        name="bad-platform",
        scope="platform",
        org_id=org.id,
        nodes=[],
        edges=[],
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(t)
    with pytest.raises(IntegrityError):
        session.commit()
