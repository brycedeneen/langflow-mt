"""add_metering_tables

Revision ID: 40bee434d2c0
Revises: fe03bc35cf61
Create Date: 2026-04-23 06:55:47.635008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '40bee434d2c0'
down_revision: Union[str, None] = 'fe03bc35cf61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # org_usage_daily
    op.create_table(
        'org_usage_daily',
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('runs', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('run_seconds', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('org_id', 'date'),
    )

    # org_usage_threshold
    op.create_table(
        'org_usage_threshold',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('metric', sa.String(length=32), nullable=False),
        sa.Column('period', sa.String(length=16), nullable=False),
        sa.Column('threshold_value', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_fired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('org_usage_threshold', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_org_usage_threshold_org_active'), ['org_id', 'is_active'], unique=False)

    # alert_rule
    op.create_table(
        'alert_rule',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('flow_id', sa.Uuid(), nullable=True),
        sa.Column('rule_type', sa.String(length=32), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_fired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='900'),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('alert_rule', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alert_rule_org_flow_active'), ['org_id', 'flow_id', 'is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_alert_rule_org_active'), ['org_id', 'is_active'], unique=False)

    # admin_notification
    op.create_table(
        'admin_notification',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='warning'),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('audience', sa.String(length=32), nullable=False, server_default='super_admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_by_user_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['read_by_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('admin_notification', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_admin_notification_audience_read_created'),
            ['audience', 'read_at', 'created_at'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('admin_notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_notification_audience_read_created'))
    op.drop_table('admin_notification')

    with op.batch_alter_table('alert_rule', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_rule_org_active'))
        batch_op.drop_index(batch_op.f('ix_alert_rule_org_flow_active'))
    op.drop_table('alert_rule')

    with op.batch_alter_table('org_usage_threshold', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_org_usage_threshold_org_active'))
    op.drop_table('org_usage_threshold')

    op.drop_table('org_usage_daily')
