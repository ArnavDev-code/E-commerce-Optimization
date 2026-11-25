"""Tests for demo store seeding and problem generation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo.seed_data import seed_demo_data
from app.models.experiment import Experiment, ExperimentResult
from app.models.leak import AIDiagnosis, DetectedLeak, Recommendation
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.product import Product, ProductVariant


def test_seed_demo_data_integrity(db: Session) -> None:
    """Verify demo store is fully seeded with 24 products and deliberate leaks."""
    result = seed_demo_data(db, force_reset=True)
    assert result["status"] == "success"
    assert result["products_count"] == 24
    assert result["leaks_count"] == 4

    # 1. Check products count and COGS availability
    products = db.execute(select(Product)).scalars().all()
    assert len(products) == 24
    for p in products:
        assert p.price is not None
        assert p.unit_cost is not None
        assert p.unit_cost < p.price  # Realistic positive margin

    # 2. Check variants
    variants = db.execute(select(ProductVariant)).scalars().all()
    assert len(variants) >= 24

    # 3. Check deliberate leaks
    leaks = db.execute(select(DetectedLeak)).scalars().all()
    assert len(leaks) == 4
    leak_types = {leak.leak_type for leak in leaks}
    assert "low_atc_rate" in leak_types
    assert "atc_rate_decline" in leak_types
    assert "high_atc_low_checkout" in leak_types
    assert "low_purchase_completion" in leak_types

    # 4. Verify AI Diagnosis structure distinguishes evidence from hypotheses
    diag = db.execute(select(AIDiagnosis)).scalars().first()
    assert diag is not None
    assert isinstance(diag.evidence, list)
    assert isinstance(diag.possible_explanations, list)
    assert isinstance(diag.recommended_actions, list)
    assert diag.confidence_level in ["high", "medium", "low"]

    # 5. Check Recommendations
    recs = db.execute(select(Recommendation)).scalars().all()
    assert len(recs) == 4
    for rec in recs:
        assert rec.suggested_action is not None
        assert rec.business_reason is not None
        assert rec.metric_to_monitor in ["add_to_cart_rate", "checkout_rate", "purchase_rate"]

    # 6. Check Sample Experiment
    exp = db.execute(select(Experiment)).scalars().first()
    assert exp is not None
    assert exp.experiment_type == "before_after"
    assert exp.status == "completed"

    exp_res = db.execute(select(ExperimentResult)).scalars().first()
    assert exp_res is not None
    assert exp_res.control_value < exp_res.treatment_value
    assert exp_res.is_statistically_significant is True
    assert exp_res.merchant_conclusion is not None

    # 7. Check Idempotency (calling seed again without force_reset does not duplicate)
    second_result = seed_demo_data(db, force_reset=False)
    assert second_result["status"] == "already_seeded"
    count_after = len(db.execute(select(Product)).scalars().all())
    assert count_after == 24
