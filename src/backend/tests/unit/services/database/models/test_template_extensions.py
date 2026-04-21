"""Unit tests for Template model extensions: archived_at, org scope, categories M:N."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models.category.model import Category
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.template.model import Template


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    # Enforce CASCADE on FK deletes on SQLite (off by default).
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def org_id(session):
    org = Organization(
        id=uuid4(),
        name="Acme",
        slug="acme",
        is_personal=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(org)
    session.commit()
    return org.id


def _make_template(**kwargs) -> Template:
    defaults = dict(
        id=uuid4(),
        name="Seed",
        description=None,
        icon="bot",
        gradient="1",
        scope="platform",
        org_id=None,
        nodes={},
        edges={},
        created_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Template(**defaults)


def test_template_defaults_archived_at_to_none(session: Session) -> None:
    t = _make_template()
    session.add(t)
    session.commit()
    assert t.archived_at is None


def test_template_accepts_org_scope_with_org_id(session: Session, org_id) -> None:
    t = _make_template(name="Org Seed", scope="org", org_id=org_id)
    session.add(t)
    session.commit()
    assert t.scope == "org"
    assert t.org_id == org_id


def test_template_rejects_org_scope_without_org_id(session: Session) -> None:
    t = _make_template(name="Bad", scope="org", org_id=None)
    session.add(t)
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_name_is_case_insensitive_unique_per_scope(session: Session) -> None:
    session.add(_make_template(name="Basic Prompting"))
    session.commit()

    session.add(_make_template(name="basic prompting"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_template_categories_many_to_many(session: Session) -> None:
    cat = Category(
        id=uuid4(),
        name="Agents",
        icon="bot",
        color="rose",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    t = _make_template(name="Agent Starter")
    t.categories.append(cat)
    session.add_all([cat, t])
    session.commit()
    session.refresh(t)
    assert [c.name for c in t.categories] == ["Agents"]
