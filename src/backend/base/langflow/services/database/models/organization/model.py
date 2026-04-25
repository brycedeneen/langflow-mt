from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Numeric
from sqlmodel import Column, Field, SQLModel

from langflow.schema.serialize import UUIDstr


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "organization"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    is_personal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    runs_max_concurrent: int = Field(default=5, sa_column_kwargs={"server_default": "5"})
    runs_priority_tier: str = Field(default="default", sa_column_kwargs={"server_default": "default"})
    billable_rate_low_per_hour: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    billable_rate_high_per_hour: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
