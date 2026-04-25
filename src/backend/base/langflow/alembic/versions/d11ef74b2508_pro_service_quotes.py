"""pro_service_quotes

Revision ID: d11ef74b2508
Revises: 67630b517fbb
Create Date: 2026-04-25 19:05:31.005772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd11ef74b2508'
down_revision: Union[str, None] = '67630b517fbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to component_metadata.
    with op.batch_alter_table("component_metadata") as batch_op:
        batch_op.add_column(sa.Column("integration_minutes_low", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("integration_minutes_high", sa.Integer(), nullable=True))

    # 2. Add ps_request_active to flow.
    with op.batch_alter_table("flow") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ps_request_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )

    # 3. Add billable rate columns to organization.
    with op.batch_alter_table("organization") as batch_op:
        batch_op.add_column(sa.Column("billable_rate_low_per_hour", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("billable_rate_high_per_hour", sa.Numeric(10, 2), nullable=True))

    # 4. Add audience_user_id + index to admin_notification.
    # NOTE: ondelete=SET NULL preserves notifications when target user is deleted.
    with op.batch_alter_table("admin_notification") as batch_op:
        batch_op.add_column(sa.Column("audience_user_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_admin_notification_audience_user_id_user",
            "user",
            ["audience_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_admin_notification_user_read_created",
            ["audience_user_id", "read_at", "created_at"],
        )

    # 5. Create professional_services_settings (singleton via CHECK id=1).
    op.create_table(
        "professional_services_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_hourly_rate_low", sa.Numeric(10, 2), nullable=True),
        sa.Column("default_hourly_rate_high", sa.Numeric(10, 2), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_ps_settings_singleton"),
    )

    # 6. Create pro_service_quote.
    op.create_table(
        "pro_service_quote",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("flow_id", sa.Uuid(), nullable=True),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("assigned_admin_user_id", sa.Uuid(), nullable=True),
        sa.Column("estimated_minutes_low", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes_high", sa.Integer(), nullable=False),
        sa.Column("rate_low_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("rate_high_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("headline_summary", sa.Text(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("org_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("in_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_admin_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pro_service_quote") as batch_op:
        batch_op.create_index(
            "ix_pro_service_quote_org_status_created",
            ["org_id", "status", "created_at"],
        )
        batch_op.create_index(
            "ix_pro_service_quote_status_created",
            ["status", "created_at"],
        )
        batch_op.create_index(
            "ix_pro_service_quote_flow_id",
            ["flow_id"],
        )

    # 7. Backfill component_metadata defaults.
    op.execute(
        "UPDATE component_metadata "
        "SET integration_minutes_low = 15, integration_minutes_high = 60 "
        "WHERE integration_minutes_low IS NULL OR integration_minutes_high IS NULL"
    )

    # 8. Seed professional_services_settings singleton (idempotent).
    # Use dialect-aware INSERT so upgrade() can be replayed without a prior
    # downgrade (e.g. partial-failure recovery).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "INSERT INTO professional_services_settings "
            "(id, default_hourly_rate_low, default_hourly_rate_high, updated_at) "
            "VALUES (1, 200.00, 200.00, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO NOTHING"
        )
    else:
        # SQLite uses INSERT OR IGNORE; MySQL also accepts this syntax.
        op.execute(
            "INSERT OR IGNORE INTO professional_services_settings "
            "(id, default_hourly_rate_low, default_hourly_rate_high, updated_at) "
            "VALUES (1, 200.00, 200.00, CURRENT_TIMESTAMP)"
        )


def downgrade() -> None:
    with op.batch_alter_table("pro_service_quote") as batch_op:
        batch_op.drop_index("ix_pro_service_quote_flow_id")
        batch_op.drop_index("ix_pro_service_quote_status_created")
        batch_op.drop_index("ix_pro_service_quote_org_status_created")
    op.drop_table("pro_service_quote")
    op.drop_table("professional_services_settings")

    with op.batch_alter_table("admin_notification") as batch_op:
        batch_op.drop_index("ix_admin_notification_user_read_created")
        batch_op.drop_constraint(
            "fk_admin_notification_audience_user_id_user",
            type_="foreignkey",
        )
        batch_op.drop_column("audience_user_id")

    with op.batch_alter_table("organization") as batch_op:
        batch_op.drop_column("billable_rate_high_per_hour")
        batch_op.drop_column("billable_rate_low_per_hour")

    with op.batch_alter_table("flow") as batch_op:
        batch_op.drop_column("ps_request_active")

    with op.batch_alter_table("component_metadata") as batch_op:
        batch_op.drop_column("integration_minutes_high")
        batch_op.drop_column("integration_minutes_low")
