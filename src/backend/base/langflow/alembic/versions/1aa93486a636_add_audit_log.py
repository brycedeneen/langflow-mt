"""add_audit_log

Revision ID: 1aa93486a636
Revises: 0acebda9c705
Create Date: 2026-04-23 06:55:55.823389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1aa93486a636'
down_revision: Union[str, None] = '0acebda9c705'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_user_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=False),
        sa.Column('actor_is_super', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('org_id', sa.Uuid(), nullable=True),
        sa.Column('target_type', sa.String(length=32), nullable=False),
        sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('diff', sa.JSON(), nullable=False),
        sa.Column('diff_hash', sa.String(length=64), nullable=False),
        sa.Column('request_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index('ix_audit_log_org_occurred', ['org_id', 'occurred_at'], unique=False)
        batch_op.create_index('ix_audit_log_actor_occurred', ['actor_user_id', 'occurred_at'], unique=False)
        batch_op.create_index('ix_audit_log_target', ['target_type', 'target_id', 'occurred_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index('ix_audit_log_target')
        batch_op.drop_index('ix_audit_log_actor_occurred')
        batch_op.drop_index('ix_audit_log_org_occurred')
    op.drop_table('audit_log')
