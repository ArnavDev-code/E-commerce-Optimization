"""Prioritized Recommendation Engine for FunnelLeak AI.

Generates actionable CRO recommendations, prioritizes them using a transparent
multi-factor scoring model (Impact, Confidence, Margin/Stock, Feasibility),
and computes defensible profit lift without fabricating metrics.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import BaseLLMProvider, RecommendationItem
from app.llm.provider_factory import get_llm_provider
from app.models.leak import DetectedLeak, Recommendation
from app.models.product import Product


class RecommendationEngine:
    """Orchestrates recommendation generation and transparent multi-factor prioritization."""

    def __init__(
        self,
        db: Session,
        store_id: uuid.UUID,
        provider: Optional[BaseLLMProvider] = None,
    ):
        self.db = db
        self.store_id = store_id
        self.provider = provider or get_llm_provider()

    def generate_recommendations_for_leak(
        self,
        leak_id: uuid.UUID,
        save_to_db: bool = True,
    ) -> List[Recommendation]:
        """Generate and score recommendations for a single detected leak."""
        stmt = (
            select(DetectedLeak)
            .where(
                DetectedLeak.id == leak_id,
                DetectedLeak.store_id == self.store_id,
            )
        )
        leak = self.db.execute(stmt).scalar_one_or_none()
        if not leak:
            raise ValueError(f"Leak {leak_id} not found for store {self.store_id}")

        product: Optional[Product] = None
        total_inventory = 0
        margin_pct: Optional[float] = None
        unit_margin: Optional[float] = None

        if leak.product_id:
            prod_stmt = (
                select(Product)
                .where(
                    Product.id == leak.product_id,
                    Product.store_id == self.store_id,
                )
            )
            product = self.db.execute(prod_stmt).scalar_one_or_none()
            if product:
                if product.variants:
                    total_inventory = sum(v.inventory_quantity for v in product.variants)
                if product.price and product.unit_cost:
                    unit_margin = float(product.price - product.unit_cost)
                    if product.price > 0:
                        margin_pct = round((unit_margin / float(product.price)) * 100, 1)

        context: Dict[str, Any] = {
            "leak_id": str(leak.id),
            "leak_type": leak.leak_type,
            "metric_affected": leak.metric_affected,
            "observed_value": float(leak.observed_value),
            "baseline_value": float(leak.baseline_value),
            "sample_size": leak.sample_size,
            "severity": leak.severity,
            "evidence_quality": leak.evidence_quality,
            "product_title": product.title if product else "Storefront Funnel",
            "price": float(product.price) if product and product.price else None,
            "unit_cost": float(product.unit_cost) if product and product.unit_cost else None,
            "margin_pct": margin_pct,
            "inventory_quantity": total_inventory,
        }

        # Generate recommendation candidates via LLM provider or fallback
        candidates: List[RecommendationItem] = self.provider.generate_recommendations(context)

        persisted: List[Recommendation] = []
        for cand in candidates:
            # 1. Multi-factor prioritization scoring
            score_data = self._calculate_priority_score(
                leak=leak,
                candidate=cand,
                margin_pct=margin_pct,
                inventory=total_inventory,
            )

            # 2. Defensible Profit Impact calculation (or None if COGS missing)
            impact_estimate = self._calculate_profit_impact(
                leak=leak,
                price=float(product.price) if product and product.price else None,
                unit_cost=float(product.unit_cost) if product and product.unit_cost else None,
            )

            # 3. Check for existing recommendation to avoid duplicate clutter
            existing_stmt = (
                select(Recommendation)
                .where(
                    Recommendation.store_id == self.store_id,
                    Recommendation.leak_id == leak.id,
                    Recommendation.title == cand.title,
                )
            )
            existing = self.db.execute(existing_stmt).scalar_one_or_none()

            if existing:
                # Update scores and details while preserving merchant status
                existing.target_stage = cand.target_stage
                existing.expected_direction = cand.expected_direction
                existing.detected_problem = cand.detected_problem
                existing.supporting_evidence = {
                    "observed": float(leak.observed_value),
                    "baseline": float(leak.baseline_value),
                    "sample_size": leak.sample_size,
                    "evidence_quality": leak.evidence_quality,
                }
                existing.suggested_action = cand.suggested_action
                existing.business_reason = cand.business_reason
                existing.potential_impact_estimate = (
                    Decimal(str(impact_estimate)) if impact_estimate is not None else None
                )
                existing.implementation_effort = cand.implementation_effort
                existing.confidence_level = cand.confidence_level
                existing.priority_score = Decimal(str(score_data["composite_score"]))
                existing.priority_breakdown = score_data
                existing.risks_or_prerequisites = cand.risks_or_prerequisites
                existing.priority = score_data["priority_tier"]
                existing.metric_to_monitor = cand.metric_to_monitor
                persisted.append(existing)
            else:
                new_rec = Recommendation(
                    store_id=self.store_id,
                    leak_id=leak.id,
                    product_id=leak.product_id,
                    title=cand.title,
                    target_stage=cand.target_stage,
                    expected_direction=cand.expected_direction,
                    detected_problem=cand.detected_problem,
                    supporting_evidence={
                        "observed": float(leak.observed_value),
                        "baseline": float(leak.baseline_value),
                        "sample_size": leak.sample_size,
                        "evidence_quality": leak.evidence_quality,
                    },
                    suggested_action=cand.suggested_action,
                    business_reason=cand.business_reason,
                    potential_impact_estimate=(
                        Decimal(str(impact_estimate)) if impact_estimate is not None else None
                    ),
                    implementation_effort=cand.implementation_effort,
                    confidence_level=cand.confidence_level,
                    priority_score=Decimal(str(score_data["composite_score"])),
                    priority_breakdown=score_data,
                    risks_or_prerequisites=cand.risks_or_prerequisites,
                    priority=score_data["priority_tier"],
                    metric_to_monitor=cand.metric_to_monitor,
                    status="new",
                )
                if save_to_db:
                    self.db.add(new_rec)
                persisted.append(new_rec)

        if save_to_db and persisted:
            self.db.commit()
            for r in persisted:
                self.db.refresh(r)

        return persisted

    def generate_all_recommendations(
        self,
        save_to_db: bool = True,
    ) -> List[Recommendation]:
        """Run recommendation engine across all active leaks in the store."""
        stmt = (
            select(DetectedLeak)
            .where(
                DetectedLeak.store_id == self.store_id,
                DetectedLeak.status.in_(["new", "reviewed"]),
            )
        )
        leaks = self.db.execute(stmt).scalars().all()
        all_recs: List[Recommendation] = []
        for leak in leaks:
            recs = self.generate_recommendations_for_leak(leak.id, save_to_db=save_to_db)
            all_recs.extend(recs)
        return all_recs

    def _calculate_priority_score(
        self,
        leak: DetectedLeak,
        candidate: RecommendationItem,
        margin_pct: Optional[float],
        inventory: int,
    ) -> Dict[str, Any]:
        """Compute transparent 4-factor priority score (0-100 scale).

        Weights:
        - Impact: 35%
        - Confidence: 25%
        - Margin & Stock: 20%
        - Feasibility / Effort: 20%
        """
        # 1. Impact (0-100)
        severity_map = {"critical": 100.0, "high": 80.0, "medium": 55.0, "low": 30.0}
        base_severity = severity_map.get(leak.severity.lower(), 55.0)

        # Volume factor
        sample = leak.sample_size
        if sample >= 500:
            vol_score = 100.0
        elif sample >= 200:
            vol_score = 85.0
        elif sample >= 50:
            vol_score = 70.0
        else:
            vol_score = 50.0

        impact_score = round(0.60 * base_severity + 0.40 * vol_score, 1)

        # 2. Confidence (0-100)
        quality_map = {"strong": 100.0, "moderate": 70.0, "weak": 40.0}
        evidence_score = quality_map.get(leak.evidence_quality.lower(), 70.0)
        sample_conf = 100.0 if sample >= 200 else (80.0 if sample >= 50 else 50.0)
        confidence_score = round(0.50 * evidence_score + 0.50 * sample_conf, 1)

        # 3. Margin & Stock (0-100)
        if margin_pct is not None:
            if margin_pct >= 60.0:
                margin_score = 100.0
            elif margin_pct >= 40.0:
                margin_score = 80.0
            elif margin_pct >= 20.0:
                margin_score = 60.0
            else:
                margin_score = 40.0
        else:
            margin_score = 50.0  # Neutral when COGS is missing

        # Stock availability penalty
        if inventory > 50:
            stock_score = 100.0
        elif inventory >= 20:
            stock_score = 85.0
        elif inventory >= 5:
            stock_score = 50.0
        elif inventory >= 1:
            stock_score = 25.0
        else:
            stock_score = 5.0  # Heavy penalty for 0 inventory

        margin_stock_score = round(0.50 * margin_score + 0.50 * stock_score, 1)

        # 4. Feasibility / Effort (0-100)
        effort_map = {"low": 100.0, "medium": 65.0, "high": 35.0}
        feasibility_score = effort_map.get(candidate.implementation_effort.lower(), 65.0)

        # Composite weighted score (0 - 100)
        composite = round(
            (0.35 * impact_score)
            + (0.25 * confidence_score)
            + (0.20 * margin_stock_score)
            + (0.20 * feasibility_score),
            1,
        )

        if composite >= 70.0:
            priority_tier = "high"
        elif composite >= 40.0:
            priority_tier = "medium"
        else:
            priority_tier = "low"

        return {
            "composite_score": composite,
            "priority_tier": priority_tier,
            "impact_score": impact_score,
            "confidence_score": confidence_score,
            "margin_stock_score": margin_stock_score,
            "feasibility_score": feasibility_score,
            "weights": {
                "impact": 0.35,
                "confidence": 0.25,
                "margin_stock": 0.20,
                "feasibility": 0.20,
            },
            "cogs_provided": margin_pct is not None,
            "inventory_units": inventory,
        }

    def _calculate_profit_impact(
        self,
        leak: DetectedLeak,
        price: Optional[float],
        unit_cost: Optional[float],
    ) -> Optional[float]:
        """Compute conservative profit recovery estimate or None if COGS missing.

        Formula:
        Lost conversions = (baseline - observed)/100 * sample_size
        Recoverable conversions = lost_conversions * 20% (conservative recovery rate)
        Profit impact = recoverable_conversions * (price - unit_cost)
        """
        if price is None or unit_cost is None or price <= unit_cost:
            return None

        unit_margin = price - unit_cost
        obs = float(leak.observed_value)
        base = float(leak.baseline_value)
        gap = max(0.0, base - obs)

        # Rate of dropoff converted to orders
        lost_events = (gap / 100.0) * leak.sample_size
        if lost_events <= 0:
            return None

        # Conservative 20% recovery target
        conservative_recovered_orders = max(1.0, lost_events * 0.20)
        potential_profit = round(conservative_recovered_orders * unit_margin, 2)
        return potential_profit
