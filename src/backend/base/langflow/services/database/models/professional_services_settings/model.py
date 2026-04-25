from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfessionalServicesSettings(SQLModel, table=True):
    __tablename__ = "professional_services_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ps_settings_singleton"),)

    id: int = Field(default=1, primary_key=True)
    default_hourly_rate_low: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )
    default_hourly_rate_high: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True),
    )
    webhook_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    webhook_secret_encrypted: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_utcnow),
    )
    updated_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
