from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class MembershipRole(str, Enum):
    OWNER = "owner"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Membership(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(index=True, foreign_key="user.id")
    organization_id: UUIDstr = Field(index=True, foreign_key="organization.id")
    role: MembershipRole = Field(
        default=MembershipRole.OWNER,
        sa_column=Column(
            SQLEnum(
                MembershipRole,
                name="membership_role_enum",
                values_callable=lambda e: [m.value for m in e],
            ),
            nullable=False,
        ),
    )
    created_at: datetime = Field(default_factory=_utc_now)
