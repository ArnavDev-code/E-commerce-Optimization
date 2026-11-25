"""Tests for LLM diagnosis engine, prioritized recommendation engine, and scoring models."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List

import pytest
from sqlalchemy.orm import Session

from app.api.leaks import diagnose_leak_endpoint, get_leak_diagnosis_endpoint
from app.api.recommendations import (
    generate_recommendations,
    get_recommendation_detail,
    list_recommendations,
    update_recommendation_status,
)
from app.demo.seed_data import seed_demo_data
from app.engine.diagnosis_engine import DiagnosisEngine
from app.engine.leak_detector import LeakDetectionConfig, LeakDetector
from app.engine.recommendation_engine import RecommendationEngine
from app.llm.providers.fallback import FallbackLLMProvider
from app.models.leak import AIDiagnosis, DetectedLeak, Recommendation
from app.models.merchant import Merchant
from app.models.product import Product, ProductVariant
from app.models.store import ConnectedStore
from app.schemas.recommendations import (
    RecommendationGenerateRequest,
    RecommendationStatusUpdate,
)


def _ensure_leaks(db: Session, store: ConnectedStore) -> List[DetectedLeak]:
    """Helper to detect and return leaks across all 4 rules."""
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
    return detector.run_detection(start_date, end_date, save_to_db=True)


def test_diagnose_all_4_leak_rules(db: Session) -> None:
    """Verify diagnosis engine outputs structured facts vs hypotheses for all 4 initial leak rules."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    leaks = _ensure_leaks(db, store)
    assert len(leaks) >= 4

    engine = DiagnosisEngine(db, store.id, provider=FallbackLLMProvider())
    leak_types_seen = set()

    for leak in leaks:
        diag = engine.diagnose_leak(leak.id, save_to_db=True)
        leak_types_seen.add(leak.leak_type)

        # 1. Confirmed observations (facts directly supported by database records)
        assert len(diag.evidence) >= 1
        for obs in diag.evidence:
            assert "metric" in obs
            assert "observed_value" in obs
            assert "baseline_value" in obs
            assert obs["sample_size"] > 0

        # 2. Hypotheses (distinct from facts, marked with likelihood)
        assert len(diag.possible_explanations) >= 1
        for hyp in diag.possible_explanations:
            assert "hypothesis" in hyp
            assert "supporting_signals" in hyp
            assert hyp["likelihood"] in ("high", "medium", "low")

        # 3. Missing information & recommended investigation
        assert len(diag.missing_information) >= 1
        assert len(diag.recommended_investigation) >= 1
        assert len(diag.recommended_actions) >= 1

        # 4. Status and confidence
        assert diag.confidence_level in ("high", "medium", "low")
        assert diag.is_fallback is True

    # Confirm all 4 rules were diagnosed
    assert "low_atc_rate" in leak_types_seen
    assert "atc_rate_decline" in leak_types_seen
    assert "high_atc_low_checkout" in leak_types_seen
    assert "low_purchase_completion" in leak_types_seen


def test_recommendation_prioritization_and_profit_scoring(db: Session) -> None:
    """Verify 4-factor scoring model (Impact, Confidence, Margin/Stock, Feasibility) and profit lift calculation."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    leaks = _ensure_leaks(db, store)
    engine = RecommendationEngine(db, store.id, provider=FallbackLLMProvider())

    all_recs = engine.generate_all_recommendations(save_to_db=True)
    assert len(all_recs) >= 4

    for rec in all_recs:
        # Check composite score bounds
        score = float(rec.priority_score)
        assert 0.0 <= score <= 100.0

        # Priority tier alignment
        if score >= 70.0:
            assert rec.priority == "high"
        elif score >= 40.0:
            assert rec.priority == "medium"
        else:
            assert rec.priority == "low"

        # Check breakdown components
        breakdown = rec.priority_breakdown
        assert "impact_score" in breakdown
        assert "confidence_score" in breakdown
        assert "margin_stock_score" in breakdown
        assert "feasibility_score" in breakdown
        assert "weights" in breakdown
        assert breakdown["weights"]["impact"] == 0.35
        assert breakdown["weights"]["confidence"] == 0.25
        assert breakdown["weights"]["margin_stock"] == 0.20
        assert breakdown["weights"]["feasibility"] == 0.20

        # When product has valid unit_cost and price, profit estimate must be calculated
        if rec.product_id:
            prod = db.query(Product).filter(Product.id == rec.product_id).first()
            if prod and prod.price and prod.unit_cost and prod.price > prod.unit_cost:
                assert rec.potential_impact_estimate is not None
                assert float(rec.potential_impact_estimate) > 0.0


def test_missing_cogs_handling_does_not_fabricate(db: Session) -> None:
    """Verify that when COGS is missing, potential profit estimate is None (never invented)."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    # Pick a product and remove its unit_cost
    prod = db.query(Product).filter(Product.store_id == store.id).first()
    assert prod is not None
    prod.unit_cost = None
    db.commit()

    # Create a synthetic leak on this product
    leak = DetectedLeak(
        store_id=store.id,
        product_id=prod.id,
        leak_type="low_atc_rate",
        metric_affected="add_to_cart_rate",
        observed_value=Decimal("1.50"),
        baseline_value=Decimal("5.00"),
        sample_size=300,
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        severity="high",
        confidence_score=Decimal("0.95"),
        evidence_quality="strong",
        reason="Test leak missing COGS",
        status="new",
    )
    db.add(leak)
    db.commit()

    engine = RecommendationEngine(db, store.id, provider=FallbackLLMProvider())
    recs = engine.generate_recommendations_for_leak(leak.id, save_to_db=True)
    assert len(recs) >= 1

    for r in recs:
        # Crucial requirement: never fabricate profit when COGS is missing
        assert r.potential_impact_estimate is None
        assert r.priority_breakdown["cogs_provided"] is False


def test_inventory_stock_penalty_on_priority(db: Session) -> None:
    """Verify that an out-of-stock product receives a heavy stock score penalty."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    # Get two products with similar price/margin
    prods = db.query(Product).filter(Product.store_id == store.id, Product.unit_cost.isnot(None)).limit(2).all()
    p_in_stock, p_out_of_stock = prods[0], prods[1]

    # Ensure p_in_stock has high inventory
    for v in p_in_stock.variants:
        v.inventory_quantity = 100
    # Set p_out_of_stock to 0 inventory
    for v in p_out_of_stock.variants:
        v.inventory_quantity = 0
    db.commit()

    leak_in_stock = DetectedLeak(
        store_id=store.id,
        product_id=p_in_stock.id,
        leak_type="low_atc_rate",
        metric_affected="add_to_cart_rate",
        observed_value=Decimal("2.00"),
        baseline_value=Decimal("6.00"),
        sample_size=400,
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        severity="high",
        confidence_score=Decimal("0.90"),
        evidence_quality="strong",
        reason="Test high stock",
        status="new",
    )
    leak_out_of_stock = DetectedLeak(
        store_id=store.id,
        product_id=p_out_of_stock.id,
        leak_type="low_atc_rate",
        metric_affected="add_to_cart_rate",
        observed_value=Decimal("2.00"),
        baseline_value=Decimal("6.00"),
        sample_size=400,
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        severity="high",
        confidence_score=Decimal("0.90"),
        evidence_quality="strong",
        reason="Test zero stock",
        status="new",
    )
    db.add_all([leak_in_stock, leak_out_of_stock])
    db.commit()

    engine = RecommendationEngine(db, store.id, provider=FallbackLLMProvider())
    recs_in_stock = engine.generate_recommendations_for_leak(leak_in_stock.id, save_to_db=False)
    recs_out_of_stock = engine.generate_recommendations_for_leak(leak_out_of_stock.id, save_to_db=False)

    score_in = float(recs_in_stock[0].priority_score)
    score_out = float(recs_out_of_stock[0].priority_score)

    # In-stock product priority score should be notably higher than out-of-stock
    assert score_in > score_out
    assert recs_out_of_stock[0].priority_breakdown["inventory_units"] == 0
    assert recs_in_stock[0].priority_breakdown["inventory_units"] > 0


def test_recommendation_status_lifecycle_and_notes(db: Session) -> None:
    """Test merchant workflow: review, accept/reject, add notes."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    _ensure_leaks(db, store)
    recs = generate_recommendations(
        payload=RecommendationGenerateRequest(),
        store=store,
        db=db,
    )
    assert len(recs) >= 1
    target_rec = recs[0]
    assert target_rec.status == "new"

    # Accept recommendation and add merchant notes
    updated = update_recommendation_status(
        rec_id=target_rec.id,
        payload=RecommendationStatusUpdate(
            status="accepted",
            merchant_notes="Approved for upcoming sprint with the design team.",
        ),
        store=store,
        db=db,
    )
    assert updated.status == "accepted"
    assert updated.merchant_notes == "Approved for upcoming sprint with the design team."

    # Verify persistence via detail endpoint
    fetched = get_recommendation_detail(rec_id=target_rec.id, store=store, db=db)
    assert fetched.status == "accepted"
    assert fetched.merchant_notes == "Approved for upcoming sprint with the design team."


def test_cross_merchant_isolation_on_recommendations_and_diagnoses(db: Session) -> None:
    """Ensure merchants cannot read or mutate another merchant's recommendations or diagnoses."""
    seed_demo_data(db, force_reset=True)
    store_a = db.query(ConnectedStore).first()
    assert store_a is not None

    # Create Store B and Merchant B
    m_b = Merchant(
        email=f"merchant_b_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="testhash",
        name="Merchant B",
        is_demo=False,
    )
    db.add(m_b)
    db.flush()

    store_b = ConnectedStore(
        merchant_id=m_b.id,
        platform="shopify",
        shop_domain=f"store-b-{uuid.uuid4().hex[:6]}.myshopify.com",
        access_token_encrypted="encrypted",
        scopes="read_products",
        is_active=True,
    )
    db.add(store_b)
    db.commit()

    # Generate recommendation and diagnosis for Store A
    leaks_a = _ensure_leaks(db, store_a)
    rec_engine = RecommendationEngine(db, store_a.id)
    recs_a = rec_engine.generate_recommendations_for_leak(leaks_a[0].id, save_to_db=True)
    diag_engine = DiagnosisEngine(db, store_a.id)
    diag_a = diag_engine.diagnose_leak(leaks_a[0].id, save_to_db=True)

    # Store B tries to view Store A's diagnosis -> 404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_diag:
        get_leak_diagnosis_endpoint(leak_id=leaks_a[0].id, store=store_b, db=db)
    assert exc_diag.value.status_code == 404

    # Store B tries to view Store A's recommendation -> 404
    with pytest.raises(HTTPException) as exc_rec:
        get_recommendation_detail(rec_id=recs_a[0].id, store=store_b, db=db)
    assert exc_rec.value.status_code == 404

    # Store B tries to mutate Store A's recommendation status -> 404
    with pytest.raises(HTTPException) as exc_mut:
        update_recommendation_status(
            rec_id=recs_a[0].id,
            payload=RecommendationStatusUpdate(status="rejected"),
            store=store_b,
            db=db,
        )
    assert exc_mut.value.status_code == 404
