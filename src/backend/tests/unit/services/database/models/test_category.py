"""Unit tests for the Category SQLModel and TemplateCategory join model."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models.category.model import Category


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def test_category_insert_and_read(session: Session) -> None:
    cat = Category(
        id=uuid4(),
        name="RAG",
        icon="database",
        color="indigo",
        description="Retrieval-augmented generation templates",
        created_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(cat)
    session.commit()

    from sqlmodel import select

    loaded = session.exec(select(Category).where(Category.name == "RAG")).one()
    assert loaded.icon == "database"
    assert loaded.color == "indigo"
    assert loaded.created_by is None


def test_category_name_is_case_insensitive_unique(session: Session) -> None:
    session.add(Category(
        id=uuid4(), name="RAG", icon="database", color="indigo",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    session.commit()

    session.add(Category(
        id=uuid4(), name="rag", icon="database", color="indigo",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    with pytest.raises(Exception):  # IntegrityError or its driver subclass
        session.commit()
