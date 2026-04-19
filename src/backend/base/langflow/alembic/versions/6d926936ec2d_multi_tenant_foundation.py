"""multi_tenant_foundation

Revision ID: 6d926936ec2d
Revises: 0e6138e7a0c2
Create Date: 2026-04-15 06:24:04.491803

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d926936ec2d'
down_revision: Union[str, None] = '0e6138e7a0c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TENANT_TABLES = [
    "flow",
    "folder",
    "file",
    "variable",
    "apikey",
    "deployment",
    "deployment_provider_account",
    "flow_version",
    "message",
    "transaction",
    "vertex_build",
    "job",
]


def _normalize_uuid_columns(bind, table: str, columns: list[str]) -> None:
    """Strip dashes from UUID columns so they match SQLAlchemy's CHAR(32) hex format on SQLite."""
    if bind.dialect.name != "sqlite":
        return
    for col in columns:
        bind.execute(
            sa.text(f'UPDATE "{table}" SET "{col}" = REPLACE("{col}", \'-\', \'\') WHERE "{col}" LIKE \'%-%\'')
        )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. organization table (skip if already created by create_db_and_tables)
    if "organization" not in existing_tables:
        op.create_table(
            "organization",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_organization_slug", "organization", ["slug"], unique=True)
        op.create_index("ix_organization_name", "organization", ["name"])

    # 2. membership table
    if "membership" not in existing_tables:
        op.create_table(
            "membership",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organization.id"), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="owner"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        )
        op.create_index("ix_membership_user_id", "membership", ["user_id"])
        op.create_index("ix_membership_organization_id", "membership", ["organization_id"])

    # 3. Insert or fetch the default organization. Use string UUIDs for cross-dialect
    #    compatibility (sqlite3 driver doesn't bind Python UUID objects directly).
    default_org_row = bind.execute(
        sa.text("SELECT id FROM organization WHERE slug = 'default' LIMIT 1")
    ).first()
    if default_org_row is not None:
        default_org_id = str(default_org_row[0])
    else:
        default_org_id = uuid4().hex
        bind.execute(
            sa.text(
                "INSERT INTO organization (id, name, slug, is_personal, created_at, updated_at) "
                "VALUES (:id, :name, :slug, :personal, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": default_org_id, "name": "Default Organization", "slug": "default", "personal": False},
        )

    # 4. Backfill one membership per existing user (owner role), skipping duplicates.
    user_rows = bind.execute(sa.text('SELECT id FROM "user"')).all()
    for (uid,) in user_rows:
        uid_str = str(uid) if uid is not None else None
        if uid_str is None:
            continue
        existing = bind.execute(
            sa.text(
                "SELECT 1 FROM membership WHERE user_id = :uid AND organization_id = :org LIMIT 1"
            ),
            {"uid": uid_str, "org": default_org_id},
        ).first()
        if existing is not None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO membership (id, user_id, organization_id, role, created_at) "
                "VALUES (:id, :uid, :org, 'owner', CURRENT_TIMESTAMP)"
            ),
            {"id": uuid4().hex, "uid": uid_str, "org": default_org_id},
        )

    # 5. Add organization_id columns to tenant tables, backfill, then FK + index
    for table in TENANT_TABLES:
        # Columns already present at the model level as nullable; ensure they exist at DB level.
        insp = sa.inspect(bind)
        existing_cols = {c["name"] for c in insp.get_columns(table)}
        if "organization_id" not in existing_cols:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
        bind.execute(
            sa.text(f'UPDATE "{table}" SET organization_id = :org_id WHERE organization_id IS NULL'),
            {"org_id": default_org_id},
        )
        existing_fks = {fk["name"] for fk in insp.get_foreign_keys(table)}
        existing_indexes = {ix["name"] for ix in insp.get_indexes(table)}
        with op.batch_alter_table(table) as batch:
            batch.alter_column("organization_id", existing_type=sa.Uuid(), nullable=False)
            if f"fk_{table}_organization" not in existing_fks:
                batch.create_foreign_key(
                    f"fk_{table}_organization", "organization", ["organization_id"], ["id"]
                )
            if f"ix_{table}_organization_id" not in existing_indexes:
                batch.create_index(f"ix_{table}_organization_id", ["organization_id"])

    # 6. Normalize UUIDs: strip dashes so SQLAlchemy's Uuid type (CHAR(32) hex on
    #    SQLite) can match values inserted by raw SQL.
    _normalize_uuid_columns(bind, "organization", ["id"])
    _normalize_uuid_columns(bind, "membership", ["id", "user_id", "organization_id"])
    for table in TENANT_TABLES:
        _normalize_uuid_columns(bind, table, ["organization_id"])

    # 7. Sanity check — no NULL org_id rows remain
    for table in TENANT_TABLES:
        nulls = bind.execute(
            sa.text(f'SELECT COUNT(*) FROM "{table}" WHERE organization_id IS NULL')
        ).scalar()
        if nulls:
            raise RuntimeError(f"Backfill failed: {table} has {nulls} NULL organization_id rows")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in reversed(TENANT_TABLES):
        existing_indexes = {ix["name"] for ix in insp.get_indexes(table)}
        existing_fks = {fk["name"] for fk in insp.get_foreign_keys(table)}
        with op.batch_alter_table(table) as batch:
            if f"ix_{table}_organization_id" in existing_indexes:
                batch.drop_index(f"ix_{table}_organization_id")
            if f"fk_{table}_organization" in existing_fks:
                batch.drop_constraint(f"fk_{table}_organization", type_="foreignkey")
            # Relax NOT NULL before dropping; batch_alter_table recreates the table anyway
            # but be explicit for other dialects.
            batch.alter_column("organization_id", existing_type=sa.Uuid(), nullable=True)
            batch.drop_column("organization_id")

    op.drop_index("ix_membership_organization_id", "membership")
    op.drop_index("ix_membership_user_id", "membership")
    op.drop_table("membership")
    op.drop_index("ix_organization_name", "organization")
    op.drop_index("ix_organization_slug", "organization")
    op.drop_table("organization")
