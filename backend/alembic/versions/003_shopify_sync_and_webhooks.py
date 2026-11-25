"""shopify sync and webhooks

Revision ID: 003_shopify_sync_and_webhooks
Revises: 002_recommendations_and_diagnoses_enhancement
Create Date: 2026-11-25 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_shopify_sync_and_webhooks'
down_revision: Union[str, None] = '002_recommendations_and_diagnoses_enhancement'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. connected_stores additions
    op.add_column('connected_stores', sa.Column('sync_status', sa.String(length=50), server_default='idle', nullable=False))
    op.add_column('connected_stores', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('connected_stores', sa.Column('last_sync_error', sa.Text(), nullable=True))
    op.add_column('connected_stores', sa.Column('data_source', sa.String(length=50), server_default='shopify', nullable=False))

    # 2. products additions
    op.add_column('products', sa.Column('data_source', sa.String(length=50), server_default='shopify', nullable=False))
    op.add_column('products', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('shopify_updated_at', sa.DateTime(timezone=True), nullable=True))

    # 3. product_variants additions
    op.add_column('product_variants', sa.Column('inventory_item_id', sa.String(length=100), nullable=True))
    op.add_column('product_variants', sa.Column('barcode', sa.String(length=100), nullable=True))

    # 4. inventory_snapshots additions
    op.add_column('inventory_snapshots', sa.Column('location_id', sa.String(length=100), nullable=True))
    op.add_column('inventory_snapshots', sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True))

    # 5. orders additions
    op.add_column('orders', sa.Column('data_source', sa.String(length=50), server_default='shopify', nullable=False))
    op.add_column('orders', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('cancel_reason', sa.String(length=100), nullable=True))
    op.add_column('orders', sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False))
    op.add_column('orders', sa.Column('total_tax', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('orders', sa.Column('total_shipping', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('orders', sa.Column('total_refunded', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('orders', sa.Column('is_test', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # 6. order_items additions
    op.add_column('order_items', sa.Column('shopify_line_item_id', sa.String(length=100), nullable=True))
    op.add_column('order_items', sa.Column('sku', sa.String(length=255), nullable=True))

    # 7. webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=True),
        sa.Column('webhook_id', sa.String(length=255), nullable=False),
        sa.Column('topic', sa.String(length=100), nullable=False),
        sa.Column('shop_domain', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='processed', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_webhook_deliveries_webhook_id'), 'webhook_deliveries', ['webhook_id'], unique=True)
    op.create_index(op.f('ix_webhook_deliveries_topic'), 'webhook_deliveries', ['topic'], unique=False)
    op.create_index(op.f('ix_webhook_deliveries_shop_domain'), 'webhook_deliveries', ['shop_domain'], unique=False)
    op.create_index(op.f('ix_webhook_deliveries_store_id'), 'webhook_deliveries', ['store_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_webhook_deliveries_store_id'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_shop_domain'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_topic'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_webhook_id'), table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')

    op.drop_column('order_items', 'sku')
    op.drop_column('order_items', 'shopify_line_item_id')

    op.drop_column('orders', 'is_test')
    op.drop_column('orders', 'total_refunded')
    op.drop_column('orders', 'total_shipping')
    op.drop_column('orders', 'total_tax')
    op.drop_column('orders', 'currency')
    op.drop_column('orders', 'cancel_reason')
    op.drop_column('orders', 'cancelled_at')
    op.drop_column('orders', 'data_source')

    op.drop_column('inventory_snapshots', 'synced_at')
    op.drop_column('inventory_snapshots', 'location_id')

    op.drop_column('product_variants', 'barcode')
    op.drop_column('product_variants', 'inventory_item_id')

    op.drop_column('products', 'shopify_updated_at')
    op.drop_column('products', 'description')
    op.drop_column('products', 'data_source')

    op.drop_column('connected_stores', 'data_source')
    op.drop_column('connected_stores', 'last_sync_error')
    op.drop_column('connected_stores', 'last_sync_at')
    op.drop_column('connected_stores', 'sync_status')
