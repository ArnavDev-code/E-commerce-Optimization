"""Tests for GA4 OAuth 2.0 flow, property discovery, report synchronization, and analytics engine integration."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ga4 import (
    disconnect_ga4,
    ga4_oauth_callback,
    get_ga4_status,
    initiate_ga4_oauth,
    list_ga4_properties,
    select_ga4_property,
    sync_ga4_data,
)
from app.config import get_settings
from app.engine.analytics_engine import AnalyticsEngine
from app.integrations.connectors.ga4.client import GA4Client
from app.integrations.connectors.ga4.connector import GA4Connector
from app.integrations.connectors.ga4.normalizer import normalize_ga4_report
from app.integrations.connectors.ga4.oauth import (
    build_google_auth_url,
    exchange_code_for_tokens,
)
from app.integrations.connectors.ga4.schemas import (
    GA4PropertySelectRequest,
)
from app.models.analytics import GA4Metric
from app.models.connection import DataSourceConnection
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.store import ConnectedStore
from app.models.sync import SyncLog
from app.utils.security import (
    decrypt_token,
    encrypt_token,
    generate_ga4_oauth_state,
    verify_ga4_oauth_state,
)

settings = get_settings()


def test_ga4_oauth_state_and_auth_url() -> None:
    """Verify cryptographically signed state nonce and Google OAuth 2.0 URL construction."""
    store_id = uuid.uuid4()
    state = generate_ga4_oauth_state(store_id)
    assert isinstance(state, str)
    assert len(state) > 20

    verified_store_id = verify_ga4_oauth_state(state)
    assert verified_store_id == store_id

    # Tampered state token rejection
    with pytest.raises(ValueError):
        verify_ga4_oauth_state(state[:-5] + "error")

    # Auth URL contains expected Google OAuth parameters
    auth_url = build_google_auth_url(state)
    assert "accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "analytics.readonly" in auth_url
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url


def test_ga4_connect_and_callback_flow(db: Session) -> None:
    """Verify complete OAuth authorization code exchange and credential encryption at rest."""
    merchant = Merchant(email="ga4_owner@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="ga4-chic-store.myshopify.com",
        is_active=True,
    )
    db.add(store)
    db.commit()

    # 1. Initiate OAuth
    connect_resp = initiate_ga4_oauth(merchant=merchant, store=store)
    assert "auth_url" in connect_resp
    assert "accounts.google.com" in connect_resp["auth_url"]

    # 2. Callback with mock token exchange
    state = generate_ga4_oauth_state(store.id)
    mock_tokens = {
        "access_token": "mock_google_access_token_12345",
        "refresh_token": "mock_google_refresh_token_67890",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/analytics.readonly",
        "token_type": "Bearer",
    }

    with patch("app.api.ga4.exchange_code_for_tokens", return_value=mock_tokens):
        callback_resp = ga4_oauth_callback(
            code="test_google_auth_code",
            state=state,
            db=db,
        )
        assert callback_resp.status_code == 307
        assert "status=ga4_connected" in callback_resp.headers["location"]

    # 3. Verify DataSourceConnection was created and tokens encrypted
    conn = db.execute(
        select(DataSourceConnection).where(
            DataSourceConnection.store_id == store.id,
            DataSourceConnection.provider == "ga4",
        )
    ).scalar_one_or_none()

    assert conn is not None
    assert conn.connection_status == "connected"
    assert conn.encrypted_access_token != "mock_google_access_token_12345"
    assert "mock_google" not in conn.encrypted_access_token
    assert decrypt_token(conn.encrypted_access_token) == "mock_google_access_token_12345"
    assert decrypt_token(conn.encrypted_refresh_token) == "mock_google_refresh_token_67890"


def test_ga4_property_discovery_and_selection(db: Session) -> None:
    """Verify property discovery from Google Analytics Admin API and merchant selection."""
    merchant = Merchant(email="ga4_admin@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="ga4-discovery.myshopify.com",
        is_active=True,
    )
    db.add(store)
    db.flush()

    conn = DataSourceConnection(
        store_id=store.id,
        provider="ga4",
        encrypted_access_token=encrypt_token("active_access_token"),
        connection_status="connected",
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)
    db.commit()

    mock_account_summaries = [
        {
            "account": "accounts/123456",
            "displayName": "Fashion Holdings LLC",
            "propertySummaries": [
                {
                    "property": "properties/99887766",
                    "displayName": "Fashion Boutique Main",
                },
                {
                    "property": "properties/11223344",
                    "displayName": "Staging Store",
                },
            ],
        }
    ]

    with patch.object(GA4Client, "list_account_summaries", return_value=mock_account_summaries):
        props_resp = list_ga4_properties(merchant=merchant, store=store, db=db)
        assert props_resp.total_properties == 2
        assert len(props_resp.accounts) == 1
        assert props_resp.accounts[0].display_name == "Fashion Holdings LLC"
        assert props_resp.accounts[0].properties[0].property_id == "99887766"

    # Select property
    sel_resp = select_ga4_property(
        payload=GA4PropertySelectRequest(
            property_id="properties/99887766",
            property_name="Fashion Boutique Main",
        ),
        merchant=merchant,
        store=store,
        db=db,
    )
    assert sel_resp.provider_property_id == "99887766"
    assert sel_resp.provider_property_name == "Fashion Boutique Main"
    assert sel_resp.is_connected is True

    # Check status endpoint
    status_resp = get_ga4_status(merchant=merchant, store=store, db=db)
    assert status_resp.is_connected is True
    assert status_resp.provider_property_id == "99887766"


def test_ga4_sync_and_idempotent_normalizer(db: Session) -> None:
    """Verify GA4 Data API runReport querying, normalizer, and idempotent database updates."""
    merchant = Merchant(email="sync_test@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="sync-store.myshopify.com",
        is_active=True,
    )
    db.add(store)
    db.flush()

    conn = DataSourceConnection(
        store_id=store.id,
        provider="ga4",
        provider_property_id="99887766",
        provider_property_name="Sync Boutique",
        encrypted_access_token=encrypt_token("active_token"),
        connection_status="connected",
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)
    db.commit()

    sample_overall_report = {
        "dimensionHeaders": [{"name": "date"}],
        "metricHeaders": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "screenPageViews"},
            {"name": "itemsViewed"},
            {"name": "itemsAddedToCart"},
            {"name": "itemsCheckedOut"},
            {"name": "ecommercePurchases"},
            {"name": "purchaseRevenue"},
        ],
        "rows": [
            {
                "dimensionValues": [{"value": "20261120"}],
                "metricValues": [
                    {"value": "150"},
                    {"value": "120"},
                    {"value": "450"},
                    {"value": "300"},
                    {"value": "45"},
                    {"value": "20"},
                    {"value": "8"},
                    {"value": "380.50"},
                ],
            }
        ],
    }

    sample_device_report = {
        "dimensionHeaders": [{"name": "date"}, {"name": "deviceCategory"}],
        "metricHeaders": [{"name": "sessions"}, {"name": "totalUsers"}, {"name": "screenPageViews"}],
        "rows": [
            {
                "dimensionValues": [{"value": "20261120"}, {"value": "mobile"}],
                "metricValues": [{"value": "100"}, {"value": "80"}, {"value": "300"}],
            },
            {
                "dimensionValues": [{"value": "20261120"}, {"value": "desktop"}],
                "metricValues": [{"value": "50"}, {"value": "40"}, {"value": "150"}],
            },
        ],
    }

    sample_source_report = {
        "dimensionHeaders": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
        "metricHeaders": [{"name": "sessions"}, {"name": "totalUsers"}, {"name": "screenPageViews"}],
        "rows": [
            {
                "dimensionValues": [{"value": "20261120"}, {"value": "Organic Search"}],
                "metricValues": [{"value": "90"}, {"value": "75"}, {"value": "260"}],
            }
        ],
    }

    def mock_run_report_impl(property_id, date_ranges, dimensions, metrics, **kwargs):
        dim_names = [d["name"] for d in dimensions]
        if "deviceCategory" in dim_names:
            return sample_device_report
        elif "sessionDefaultChannelGroup" in dim_names:
            return sample_source_report
        else:
            return sample_overall_report

    with patch.object(GA4Client, "run_report", side_effect=mock_run_report_impl):
        sync_res = sync_ga4_data(merchant=merchant, store=store, db=db)
        assert sync_res.success is True
        assert sync_res.records_synced == 4  # 1 overall + 2 device + 1 source

    # Verify metrics saved in database
    metrics = db.execute(
        select(GA4Metric).where(GA4Metric.store_id == store.id)
    ).scalars().all()
    assert len(metrics) == 4

    overall_row = next(m for m in metrics if m.dimension_type == "overall")
    assert overall_row.sessions == 150
    assert overall_row.product_views == 300
    assert overall_row.add_to_carts == 45
    assert overall_row.revenue == Decimal("380.50")

    # Idempotent re-sync test: run report again and ensure row count remains 4
    with patch.object(GA4Client, "run_report", side_effect=mock_run_report_impl):
        sync_res_2 = sync_ga4_data(merchant=merchant, store=store, db=db)
        assert sync_res_2.success is True

    metrics_after = db.execute(
        select(GA4Metric).where(GA4Metric.store_id == store.id)
    ).scalars().all()
    assert len(metrics_after) == 4


def test_ga4_analytics_engine_source_attribution(db: Session) -> None:
    """Verify AnalyticsEngine consumes GA4 sessions and breakdowns while keeping Shopify orders authoritative."""
    merchant = Merchant(email="engine_test@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="analytics-engine-test.myshopify.com",
        is_active=True,
    )
    db.add(store)
    db.flush()

    target_date = date.today() - timedelta(days=2)

    # 1. Add Shopify Orders (authoritative for commerce)
    order_1 = Order(
        store_id=store.id,
        shopify_order_id="gid://shopify/Order/111",
        order_number="1001",
        total_price=Decimal("150.00"),
        subtotal_price=Decimal("150.00"),
        order_date=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        financial_status="paid",
        fulfillment_status="fulfilled",
    )
    order_2 = Order(
        store_id=store.id,
        shopify_order_id="gid://shopify/Order/222",
        order_number="1002",
        total_price=Decimal("100.00"),
        subtotal_price=Decimal("100.00"),
        order_date=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        financial_status="paid",
        fulfillment_status="fulfilled",
    )
    db.add_all([order_1, order_2])

    # 2. Add GA4 Metrics (authoritative for traffic and funnel stages)
    ga4_overall = GA4Metric(
        store_id=store.id,
        report_date=target_date,
        dimension_type="overall",
        dimension_value=None,
        sessions=200,
        users=160,
        page_views=500,
        product_views=400,
        add_to_carts=60,
        checkouts=20,
        purchases=2,
        revenue=Decimal("250.00"),
    )
    ga4_device_mobile = GA4Metric(
        store_id=store.id,
        report_date=target_date,
        dimension_type="device",
        dimension_value="mobile",
        sessions=150,
        users=120,
        page_views=350,
        product_views=300,
        add_to_carts=45,
        checkouts=15,
        purchases=1,
        revenue=Decimal("150.00"),
    )
    ga4_source_organic = GA4Metric(
        store_id=store.id,
        report_date=target_date,
        dimension_type="source",
        dimension_value="organic search",
        sessions=120,
        users=100,
        page_views=280,
        product_views=240,
        add_to_carts=35,
        checkouts=12,
        purchases=1,
        revenue=Decimal("100.00"),
    )
    db.add_all([ga4_overall, ga4_device_mobile, ga4_source_organic])
    db.commit()

    engine = AnalyticsEngine(db=db, store_id=store.id)

    # Overview KPIs
    overview = engine.compute_overview_kpis(
        start_date=target_date - timedelta(days=1),
        end_date=target_date + timedelta(days=1),
        data_source="ga4",
    )
    assert overview.data_source == "ga4"
    assert overview.total_sessions == 200  # From GA4
    assert overview.total_views == 400     # From GA4
    assert overview.total_add_to_carts == 60  # From GA4
    assert overview.total_orders == 2      # Strictly from Shopify orders table!
    assert overview.revenue == Decimal("250.00")  # Strictly from Shopify orders table!
    # Conversion rate: 2 orders / 200 sessions * 100 = 1.00%
    assert overview.overall_conversion_rate == Decimal("1.00")

    # Funnel Breakdown
    funnel = engine.compute_funnel_breakdown(
        start_date=target_date - timedelta(days=1),
        end_date=target_date + timedelta(days=1),
        data_source="ga4",
    )
    assert funnel.data_source == "ga4"
    assert len(funnel.stages) == 4
    assert funnel.stages[0].stage == "Product Views"
    assert funnel.stages[0].count == 400
    assert funnel.stages[0].data_source == "ga4"
    assert funnel.stages[1].stage == "Add to Cart"
    assert funnel.stages[1].count == 60
    assert funnel.stages[1].conversion_rate == Decimal("15.00")  # 60 / 400 * 100

    # Device & Source breakdown from GA4
    assert len(funnel.device_breakdown) == 1
    assert funnel.device_breakdown[0].segment_value == "Mobile"
    assert funnel.device_breakdown[0].views == 300
    assert funnel.device_breakdown[0].add_to_carts == 45

    assert len(funnel.source_breakdown) == 1
    assert funnel.source_breakdown[0].segment_value == "Organic Search"
    assert funnel.source_breakdown[0].views == 240


def test_ga4_disconnect(db: Session) -> None:
    """Verify GA4 disconnection revokes tokens, clears credentials, and updates status."""
    merchant = Merchant(email="disconnect_test_ga4@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="ga4-disconnect.myshopify.com",
        is_active=True,
    )
    db.add(store)
    db.flush()

    conn = DataSourceConnection(
        store_id=store.id,
        provider="ga4",
        provider_property_id="123456",
        provider_property_name="My Property",
        encrypted_access_token=encrypt_token("active_token"),
        encrypted_refresh_token=encrypt_token("refresh_token"),
        connection_status="connected",
    )
    db.add(conn)
    db.commit()

    with patch("app.integrations.connectors.ga4.connector.revoke_token", return_value=True):
        resp = disconnect_ga4(merchant=merchant, store=store, db=db)
        assert resp["success"] is True

    db.refresh(conn)
    assert conn.connection_status == "disconnected"
    assert conn.encrypted_access_token is None
    assert conn.encrypted_refresh_token is None
    assert conn.provider_property_id is None
