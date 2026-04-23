"""add_cost_and_flow_usage

Revision ID: 0acebda9c705
Revises: 40bee434d2c0
Create Date: 2026-04-23 07:18:28.071415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0acebda9c705'
down_revision: Union[str, None] = '40bee434d2c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. trace.flow_run_id — nullable; backfill not required
    with op.batch_alter_table('trace', schema=None) as batch_op:
        batch_op.add_column(sa.Column('flow_run_id', sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f('ix_trace_flow_run_id'), ['flow_run_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_trace_flow_run_id',
            'flow_run',
            ['flow_run_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 2. flow_run.cost_cents + model_usage
    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cost_cents', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('model_usage', sa.JSON(), nullable=True))

    # 3. org_usage_daily.cost_cents
    with op.batch_alter_table('org_usage_daily', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cost_cents', sa.BigInteger(), nullable=False, server_default='0'))

    # 4. flow_usage_daily (new)
    op.create_table(
        'flow_usage_daily',
        sa.Column('flow_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('runs', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('run_seconds', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('cost_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('flow_id', 'date'),
    )
    with op.batch_alter_table('flow_usage_daily', schema=None) as batch_op:
        batch_op.create_index('ix_flow_usage_daily_org_date', ['org_id', 'date'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('flow_usage_daily', schema=None) as batch_op:
        batch_op.drop_index('ix_flow_usage_daily_org_date')
    op.drop_table('flow_usage_daily')

    with op.batch_alter_table('org_usage_daily', schema=None) as batch_op:
        batch_op.drop_column('cost_cents')

    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.drop_column('model_usage')
        batch_op.drop_column('cost_cents')

    with op.batch_alter_table('trace', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trace_flow_run_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_trace_flow_run_id'))
        batch_op.drop_column('flow_run_id')
