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
