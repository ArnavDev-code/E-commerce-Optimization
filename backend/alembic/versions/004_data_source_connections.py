"""data source connections

Revision ID: 004_data_source_connections
Revises: 003_shopify_sync_and_webhooks
Create Date: 2026-11-26 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_data_source_connections'
down_revision: Union[str, None] = '003_shopify_sync_and_webhooks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'data_source_connections',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_account_id', sa.String(length=255), nullable=True),
        sa.Column('provider_property_id', sa.String(length=255), nullable=True),
        sa.Column('provider_property_name', sa.String(length=255), nullable=True),
        sa.Column('auth_type', sa.String(length=50), server_default='oauth', nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=True),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('granted_scopes', sa.String(length=500), nullable=True),
        sa.Column('connection_status', sa.String(length=50), server_default='disconnected', nullable=False),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'provider', name='uq_store_provider_connection')
    )
    op.create_index(op.f('ix_data_source_connections_store_id'), 'data_source_connections', ['store_id'], unique=False)
    op.create_index(op.f('ix_data_source_connections_provider'), 'data_source_connections', ['provider'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_data_source_connections_provider'), table_name='data_source_connections')
    op.drop_index(op.f('ix_data_source_connections_store_id'), table_name='data_source_connections')
    op.drop_table('data_source_connections')
