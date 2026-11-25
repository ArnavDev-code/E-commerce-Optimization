"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-18 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. merchants
    op.create_table(
        'merchants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_merchants_email', 'merchants', ['email'], unique=True)

    # 2. connected_stores
    op.create_table(
        'connected_stores',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('merchant_id', sa.Uuid(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False, server_default='shopify'),
        sa.Column('shop_domain', sa.String(length=255), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('scopes', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('installed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('uninstalled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_connected_stores_merchant_id', 'connected_stores', ['merchant_id'])
    op.create_index('ix_connected_stores_shop_domain', 'connected_stores', ['shop_domain'], unique=True)

    # 3. products
    op.create_table(
        'products',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('shopify_product_id', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('handle', sa.String(length=500), nullable=True),
        sa.Column('product_type', sa.String(length=255), nullable=True),
        sa.Column('vendor', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('compare_at_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('cost_source', sa.String(length=50), nullable=True),
        sa.Column('image_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_products_store_id', 'products', ['store_id'])
    op.create_index('ix_products_shopify_product_id', 'products', ['shopify_product_id'])

    # 4. product_variants
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('shopify_variant_id', sa.String(length=100), nullable=True),
        sa.Column('sku', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('inventory_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('available', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_product_variants_product_id', 'product_variants', ['product_id'])

    # 5. inventory_snapshots
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('variant_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_snapshots_variant_id', 'inventory_snapshots', ['variant_id'])
    op.create_index('ix_inventory_snapshots_snapshot_date', 'inventory_snapshots', ['snapshot_date'])

    # 6. orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('shopify_order_id', sa.String(length=100), nullable=True),
        sa.Column('order_number', sa.String(length=100), nullable=True),
        sa.Column('total_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('subtotal_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_discounts', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('financial_status', sa.String(length=50), nullable=True),
        sa.Column('fulfillment_status', sa.String(length=50), nullable=True),
        sa.Column('item_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('traffic_source', sa.String(length=255), nullable=True),
        sa.Column('device_category', sa.String(length=50), nullable=True),
        sa.Column('order_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_orders_store_id', 'orders', ['store_id'])
    op.create_index('ix_orders_order_date', 'orders', ['order_date'])

    # 7. order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('variant_id', sa.Uuid(), nullable=True),
        sa.Column('shopify_product_id', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total_discount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])

    # 8. storefront_events
    op.create_table(
        'storefront_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('shopify_product_id', sa.String(length=100), nullable=True),
        sa.Column('page_url', sa.String(length=1000), nullable=True),
        sa.Column('device_category', sa.String(length=50), nullable=True),
        sa.Column('traffic_source', sa.String(length=255), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_storefront_events_store_id', 'storefront_events', ['store_id'])
    op.create_index('ix_storefront_events_store_type_time', 'storefront_events', ['store_id', 'event_type', 'event_timestamp'])

    # 9. ga4_metrics
    op.create_table(
        'ga4_metrics',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('dimension_type', sa.String(length=50), nullable=False),
        sa.Column('dimension_value', sa.String(length=255), nullable=True),
        sa.Column('sessions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('users', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('page_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('product_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('add_to_carts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checkouts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('purchases', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ga4_metrics_store_dim_date', 'ga4_metrics', ['store_id', 'dimension_type', 'report_date'])

    # 10. funnel_metrics
    op.create_table(
        'funnel_metrics',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False, server_default='pixel'),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('segment_type', sa.String(length=50), nullable=False, server_default='overall'),
        sa.Column('segment_value', sa.String(length=255), nullable=True),
        sa.Column('product_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('add_to_carts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('add_to_cart_rate', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('checkout_starts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checkout_rate', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('purchases', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('purchase_rate', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('aov', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('revenue_per_visitor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('gross_profit', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('gross_profit_per_visitor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_funnel_metrics_store_prod_dates', 'funnel_metrics', ['store_id', 'product_id', 'period_start', 'period_end'])

    # 11. detected_leaks
    op.create_table(
        'detected_leaks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('leak_type', sa.String(length=100), nullable=False),
        sa.Column('metric_affected', sa.String(length=100), nullable=False),
        sa.Column('observed_value', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('baseline_value', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('evidence_quality', sa.String(length=20), nullable=False, server_default='moderate'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_detected_leaks_store_id', 'detected_leaks', ['store_id'])

    # 12. ai_diagnoses
    op.create_table(
        'ai_diagnoses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('leak_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='fallback'),
        sa.Column('issue_summary', sa.Text(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('possible_explanations', sa.JSON(), nullable=False),
        sa.Column('further_checks', sa.JSON(), nullable=True),
        sa.Column('recommended_actions', sa.JSON(), nullable=False),
        sa.Column('confidence_level', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('is_fallback', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['leak_id'], ['detected_leaks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_diagnoses_leak_id', 'ai_diagnoses', ['leak_id'])

    # 13. recommendations
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('leak_id', sa.Uuid(), nullable=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('detected_problem', sa.Text(), nullable=False),
        sa.Column('supporting_evidence', sa.JSON(), nullable=False),
        sa.Column('suggested_action', sa.Text(), nullable=False),
        sa.Column('business_reason', sa.Text(), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('metric_to_monitor', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['leak_id'], ['detected_leaks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recommendations_store_id', 'recommendations', ['store_id'])

    # 14. experiments
    op.create_table(
        'experiments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('recommendation_id', sa.Uuid(), nullable=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('experiment_type', sa.String(length=50), nullable=False, server_default='before_after'),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('control_description', sa.Text(), nullable=True),
        sa.Column('treatment_description', sa.Text(), nullable=True),
        sa.Column('change_made', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('metric_to_track', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['recommendations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiments_store_id', 'experiments', ['store_id'])

    # 15. experiment_results
    op.create_table(
        'experiment_results',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('experiment_id', sa.Uuid(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('control_value', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('treatment_value', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('absolute_change', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('relative_change_pct', sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column('control_sample_size', sa.Integer(), nullable=False),
        sa.Column('treatment_sample_size', sa.Integer(), nullable=False),
        sa.Column('is_statistically_significant', sa.Boolean(), nullable=True),
        sa.Column('p_value', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('merchant_conclusion', sa.Text(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiment_results_experiment_id', 'experiment_results', ['experiment_id'])

    # 16. sync_logs
    op.create_table(
        'sync_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='started'),
        sa.Column('records_synced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['connected_stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sync_logs_store_id', 'sync_logs', ['store_id'])


def downgrade() -> None:
    op.drop_table('sync_logs')
    op.drop_table('experiment_results')
    op.drop_table('experiments')
    op.drop_table('recommendations')
    op.drop_table('ai_diagnoses')
    op.drop_table('detected_leaks')
    op.drop_table('funnel_metrics')
    op.drop_table('ga4_metrics')
    op.drop_table('storefront_events')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('inventory_snapshots')
    op.drop_table('product_variants')
    op.drop_table('products')
    op.drop_table('connected_stores')
    op.drop_table('merchants')
