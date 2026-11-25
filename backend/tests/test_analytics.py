"""Tests for deterministic analytics calculations and edge cases."""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.api.analytics import get_analytics_overview, get_funnel_analytics
from app.demo.seed_data import seed_demo_data
from app.engine.analytics_engine import AnalyticsEngine
from app.models.merchant import Merchant
from app.models.store import ConnectedStore


def test_analytics_overview_calculation(db: Session) -> None:
    """Verify overview KPIs calculated deterministically from events and orders."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    engine = AnalyticsEngine(db, store.id)
    kpis = engine.compute_overview_kpis(start_date, end_date)

    assert kpis.total_views > 0
    assert kpis.total_add_to_carts > 0
    assert kpis.total_orders > 0
    assert kpis.revenue > Decimal("0.00")
    assert kpis.aov > Decimal("0.00")
    assert kpis.overall_conversion_rate > Decimal("0.00")
    assert kpis.gross_profit is not None
    assert kpis.gross_profit > Decimal("0.00")
    assert kpis.data_source == "pixel"


def test_funnel_progression_and_segmentation(db: Session) -> None:
    """Verify 4-stage funnel rates and device/source breakdowns."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    engine = AnalyticsEngine(db, store.id)
    funnel = engine.compute_funnel_breakdown(start_date, end_date)

    assert len(funnel.stages) == 4
    views_stage = funnel.stages[0]
    atc_stage = funnel.stages[1]
    chk_stage = funnel.stages[2]
    pur_stage = funnel.stages[3]

    assert views_stage.stage == "Product Views"
    assert atc_stage.stage == "Add to Cart"
    assert chk_stage.stage == "Checkout Started"
    assert pur_stage.stage == "Purchases Completed"

    # Monotonic dropoff: views >= atcs >= checkouts >= purchases
    assert views_stage.count >= atc_stage.count
    assert atc_stage.count >= chk_stage.count
    assert chk_stage.count >= pur_stage.count

    # Verify device segment breakdown
    assert len(funnel.device_breakdown) > 0
    devices = {d.segment_value.lower() for d in funnel.device_breakdown}
    assert "mobile" in devices
    assert "desktop" in devices

    # Verify traffic source segment breakdown
    assert len(funnel.source_breakdown) > 0


def test_zero_division_safety(db: Session) -> None:
    """Verify engine handles empty stores with zero views gracefully without throwing ZeroDivisionError."""
    # Create empty merchant and store with no events
    merchant = Merchant(email="empty@store.com", password_hash="hash")
    db.add(merchant)
    db.flush()
    empty_store = ConnectedStore(merchant_id=merchant.id, shop_domain="empty.myshopify.com")
    db.add(empty_store)
    db.commit()

    engine = AnalyticsEngine(db, empty_store.id)
    kpis = engine.compute_overview_kpis(date.today() - timedelta(days=7), date.today())

    assert kpis.total_views == 0
    assert kpis.total_orders == 0
    assert kpis.revenue == Decimal("0.00")
    assert kpis.aov == Decimal("0.00")
    assert kpis.overall_conversion_rate == Decimal("0.00")
    assert kpis.gross_profit is None
    assert kpis.gross_profit_per_visitor is None

    funnel = engine.compute_funnel_breakdown(date.today() - timedelta(days=7), date.today())
    assert funnel.stages[0].count == 0
    assert funnel.stages[1].conversion_rate == Decimal("0.0")
