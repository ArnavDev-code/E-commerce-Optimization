"""Rule-based revenue leak detection engine with statistical rigor.

Implements the four initial approved rules:
1. Low Add-To-Cart rate vs category/store baseline.
2. Significant decline in Add-To-Cart rate vs prior period.
3. High Add-To-Cart with low checkout progression.
4. Checkout initiation with low purchase completion.

Enforces minimum sample thresholds and performs 2-proportion z-tests for statistical validity.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.analytics_engine import AnalyticsEngine
from app.models.leak import DetectedLeak
from app.models.product import Product
from app.utils.statistics import calculate_two_proportion_z_test


@dataclass
class LeakDetectionConfig:
    """Configurable thresholds and sample size requirements for leak detection."""
    # General
    min_sample_views: int = 50
    min_sample_atcs: int = 20
    min_sample_checkouts: int = 15

    # Rule 1: Low ATC rate vs Store Baseline
    low_atc_ratio_threshold: float = 0.50  # Flag if ATC rate < 50% of store median

    # Rule 2: ATC Rate Decline vs Prior Period
    atc_decline_pct_threshold: float = 30.0  # Flag if ATC rate dropped >= 30%

    # Rule 3: High ATC, Low Checkout Progression
    low_checkout_progression_threshold: float = 25.0  # Flag if Checkout / ATC < 25%

    # Rule 4: Low Purchase Completion from Checkout
    low_purchase_completion_threshold: float = 35.0  # Flag if Purchase / Checkout < 35%


class LeakDetector:
    """Analyzes calculated funnel metrics and flags revenue leaks with evidence."""

    def __init__(
        self,
        db: Session,
        store_id: uuid.UUID,
        config: Optional[LeakDetectionConfig] = None,
    ):
        self.db = db
        self.store_id = store_id
        self.config = config or LeakDetectionConfig()
        self.analytics = AnalyticsEngine(db, store_id)

    def run_detection(
        self,
        start_date: date,
        end_date: date,
        save_to_db: bool = True,
    ) -> List[DetectedLeak]:
        """Execute all 4 rules across the store catalog over the given date range."""
        product_rows = self.analytics.compute_product_metrics_table(start_date, end_date)
        if not product_rows:
            return []

        # Calculate store benchmark medians across eligible products (views >= min_sample)
        valid_atc_rates = [
            float(r["add_to_cart_rate"])
            for r in product_rows
            if r["views"] >= self.config.min_sample_views and r["add_to_cart_rate"] is not None
        ]
        store_median_atc = float(np.median(valid_atc_rates)) if valid_atc_rates else 4.0

        valid_chk_rates = [
            float(r["checkout_rate"])
            for r in product_rows
            if r["add_to_carts"] >= self.config.min_sample_atcs and r["checkout_rate"] is not None
        ]
        store_median_chk = float(np.median(valid_chk_rates)) if valid_chk_rates else 60.0

        valid_pur_rates = [
            float(r["purchase_rate"])
            for r in product_rows
            if r["checkout_starts"] >= self.config.min_sample_checkouts and r["purchase_rate"] is not None
        ]
        store_median_pur = float(np.median(valid_pur_rates)) if valid_pur_rates else 70.0

        # Prior comparison period for Rule 2 (ATC Decline)
        period_len = (end_date - start_date).days
        prior_start = start_date - timedelta(days=period_len)
        prior_end = start_date
        prior_rows = {
            r["product"].id: r
            for r in self.analytics.compute_product_metrics_table(prior_start, prior_end)
        }

        flagged_leaks: List[DetectedLeak] = []

        for row in product_rows:
            p = row["product"]
            v = row["views"]
            a = row["add_to_carts"]
            c = row["checkout_starts"]
            pur = row["purchases"]
            atc_rate = float(row["add_to_cart_rate"]) if row["add_to_cart_rate"] is not None else 0.0
            chk_rate = float(row["checkout_rate"]) if row["checkout_rate"] is not None else 0.0
            pur_rate = float(row["purchase_rate"]) if row["purchase_rate"] is not None else 0.0

            # ── RULE 1: Low Add-to-Cart Rate vs Baseline ───────────────────────
            if v >= self.config.min_sample_views:
                threshold = store_median_atc * self.config.low_atc_ratio_threshold
                if atc_rate < threshold:
                    # Statistical test: observed vs benchmark
                    expected_atcs = int(round(store_median_atc / 100.0 * v))
                    z_res = calculate_two_proportion_z_test(a, v, expected_atcs, v)
                    p_val = z_res.p_value
                    is_sig = z_res.is_statistically_significant

                    deficit_pct = ((store_median_atc - atc_rate) / store_median_atc) * 100
                    severity = "critical" if deficit_pct >= 60 else "high"
                    evidence_quality = "strong" if is_sig and v >= 100 else "moderate"

                    leak = DetectedLeak(
                        store_id=self.store_id,
                        product_id=p.id,
                        leak_type="low_atc_rate",
                        metric_affected="add_to_cart_rate",
                        observed_value=Decimal(str(round(atc_rate, 2))),
                        baseline_value=Decimal(str(round(store_median_atc, 2))),
                        sample_size=v,
                        period_start=start_date,
                        period_end=end_date,
                        severity=severity,
                        confidence_score=Decimal(str(round(1.0 - min(p_val, 0.99), 2))),
                        evidence_quality=evidence_quality,
                        reason=(
                            f"Add-to-cart rate ({atc_rate:.2f}%) is {deficit_pct:.1f}% below store median "
                            f"({store_median_atc:.2f}%) across {v:,} product views."
                            f"{' (Statistically significant p < 0.05)' if is_sig else ''}"
                        ),
                        status="new",
                    )
                    flagged_leaks.append(leak)

            # ── RULE 2: Significant Decline in Add-to-Cart Rate ────────────────
            if v >= self.config.min_sample_views and p.id in prior_rows:
                prior = prior_rows[p.id]
                prior_v = prior["views"]
                prior_atc = float(prior["add_to_cart_rate"]) if prior["add_to_cart_rate"] is not None else 0.0

                if prior_v >= self.config.min_sample_views and prior_atc > 0:
                    decline_pct = ((prior_atc - atc_rate) / prior_atc) * 100
                    if decline_pct >= self.config.atc_decline_pct_threshold:
                        z_res = calculate_two_proportion_z_test(a, v, prior["add_to_carts"], prior_v)
                        p_val = z_res.p_value
                        is_sig = z_res.is_statistically_significant
                        severity = "critical" if decline_pct >= 50 else "high"
                        evidence_quality = "strong" if is_sig else "moderate"

                        leak = DetectedLeak(
                            store_id=self.store_id,
                            product_id=p.id,
                            leak_type="atc_rate_decline",
                            metric_affected="add_to_cart_rate",
                            observed_value=Decimal(str(round(atc_rate, 2))),
                            baseline_value=Decimal(str(round(prior_atc, 2))),
                            sample_size=v,
                            period_start=start_date,
                            period_end=end_date,
                            severity=severity,
                            confidence_score=Decimal(str(round(1.0 - min(p_val, 0.99), 2))),
                            evidence_quality=evidence_quality,
                            reason=(
                                f"Add-to-cart rate dropped by {decline_pct:.1f}% vs prior comparison period "
                                f"(from {prior_atc:.2f}% down to {atc_rate:.2f}%)."
                                f"{' (Statistically significant p < 0.05)' if is_sig else ''}"
                            ),
                            status="new",
                        )
                        flagged_leaks.append(leak)

            # ── RULE 3: High Add-to-Cart, Low Checkout Progression ──────────────
            if a >= self.config.min_sample_atcs:
                if chk_rate < self.config.low_checkout_progression_threshold:
                    dropoff_pct = 100.0 - chk_rate
                    severity = "high" if dropoff_pct >= 80 else "medium"

                    leak = DetectedLeak(
                        store_id=self.store_id,
                        product_id=p.id,
                        leak_type="high_atc_low_checkout",
                        metric_affected="checkout_rate",
                        observed_value=Decimal(str(round(chk_rate, 2))),
                        baseline_value=Decimal(str(round(store_median_chk, 2))),
                        sample_size=a,
                        period_start=start_date,
                        period_end=end_date,
                        severity=severity,
                        confidence_score=Decimal("0.90"),
                        evidence_quality="strong" if a >= 50 else "moderate",
                        reason=(
                            f"Strong cart additions ({a:,} ATCs), but {dropoff_pct:.1f}% abandon before "
                            f"reaching checkout (observed checkout progression: {chk_rate:.1f}% vs store benchmark {store_median_chk:.1f}%)."
                        ),
                        status="new",
                    )
                    flagged_leaks.append(leak)

            # ── RULE 4: Checkout Initiation, Low Purchase Completion ────────────
            if c >= self.config.min_sample_checkouts:
                if pur_rate < self.config.low_purchase_completion_threshold:
                    payment_dropoff_pct = 100.0 - pur_rate
                    severity = "high" if payment_dropoff_pct >= 75 else "medium"

                    leak = DetectedLeak(
                        store_id=self.store_id,
                        product_id=p.id,
                        leak_type="low_purchase_completion",
                        metric_affected="purchase_rate",
                        observed_value=Decimal(str(round(pur_rate, 2))),
                        baseline_value=Decimal(str(round(store_median_pur, 2))),
                        sample_size=c,
                        period_start=start_date,
                        period_end=end_date,
                        severity=severity,
                        confidence_score=Decimal("0.85"),
                        evidence_quality="moderate",
                        reason=(
                            f"Checkout was initiated ({c:,} checkouts), but {payment_dropoff_pct:.1f}% "
                            f"abandoned during payment (completion: {pur_rate:.1f}% vs store baseline {store_median_pur:.1f}%)."
                        ),
                        status="new",
                    )
                    flagged_leaks.append(leak)

        if save_to_db and flagged_leaks:
            for lk in flagged_leaks:
                self.db.add(lk)
            self.db.commit()

        return flagged_leaks
