"""Tests for the rule-based leak detection engine and thresholds."""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.api.leaks import get_leak_detail, list_detected_leaks, run_leak_detection
from app.demo.seed_data import seed_demo_data
from app.engine.leak_detector import LeakDetectionConfig, LeakDetector
from app.models.product import Product
from app.models.store import ConnectedStore
from app.schemas.analytics import LeakDetectRequest


def test_leak_detection_rules_with_calculated_metrics(db: Session) -> None:
    """Verify all 4 initial rules flag the deliberately planted conversion issues."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    detector = LeakDetector(
        db,
        store.id,
        config=LeakDetectionConfig(
            min_sample_views=40,
            min_sample_atcs=15,
            min_sample_checkouts=10,
        ),
    )
    leaks = detector.run_detection(start_date, end_date, save_to_db=False)

    assert len(leaks) >= 4
    leak_types = {lk.leak_type for lk in leaks}

    # Rule 1
    assert "low_atc_rate" in leak_types
    # Rule 2
    assert "atc_rate_decline" in leak_types
    # Rule 3
    assert "high_atc_low_checkout" in leak_types
    # Rule 4
    assert "low_purchase_completion" in leak_types

    # Verify every leak contains required audit fields
    for lk in leaks:
        assert lk.product_id is not None
        assert lk.metric_affected in ["add_to_cart_rate", "checkout_rate", "purchase_rate"]
        assert lk.observed_value >= 0
        assert lk.baseline_value >= 0
        assert lk.sample_size >= 15
        assert lk.severity in ["critical", "high", "medium", "low"]
        assert lk.evidence_quality in ["strong", "moderate", "weak"]
        assert len(lk.reason) > 10


def test_leak_detection_sample_threshold_enforcement(db: Session) -> None:
    """Verify that products with insufficient data (below min_sample threshold) are NOT flagged."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Set an impossibly high min_sample_views threshold (10,000)
    strict_config = LeakDetectionConfig(
        min_sample_views=10_000,
        min_sample_atcs=5_000,
        min_sample_checkouts=2_000,
    )
    detector = LeakDetector(db, store.id, config=strict_config)
    leaks = detector.run_detection(start_date, end_date, save_to_db=False)

    # No products have 10,000 views, so ZERO leaks should be flagged
    assert len(leaks) == 0


def test_leak_api_endpoints(db: Session) -> None:
    """Test /api/leaks and /api/leaks/detect endpoints."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    # List leaks
    leaks_list = list_detected_leaks(status_filter=None, store=store, db=db)
    assert len(leaks_list) >= 4
    first_leak = leaks_list[0]
    assert first_leak.product_title is not None

    # Get single leak detail
    detail = get_leak_detail(leak_id=first_leak.id, store=store, db=db)
    assert detail.id == first_leak.id
    assert detail.reason == first_leak.reason

    # Trigger detection run
    detect_res = run_leak_detection(
        payload=LeakDetectRequest(days=30, min_sample_size=40),
        store=store,
        db=db,
    )
    assert len(detect_res) >= 4
