"""Diagnosis Engine for FunnelLeak AI.

Consumes detected leaks and deterministic analytics evidence,
orchestrating LLM providers (or deterministic fallback) to generate
structured diagnoses that strictly separate verified facts from hypotheses.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import BaseLLMProvider, DiagnosisOutput
from app.llm.provider_factory import get_llm_provider
from app.models.leak import AIDiagnosis, DetectedLeak
from app.models.product import Product


class DiagnosisEngine:
    """Diagnoses detected revenue leaks using structured evidence."""

    def __init__(
        self,
        db: Session,
        store_id: uuid.UUID,
        provider: Optional[BaseLLMProvider] = None,
    ):
        self.db = db
        self.store_id = store_id
        self.provider = provider or get_llm_provider()

    def diagnose_leak(
        self,
        leak_id: uuid.UUID,
        save_to_db: bool = True,
    ) -> AIDiagnosis:
        """Generate or retrieve a structured diagnosis for a specific detected leak."""
        # 1. Fetch leak and ensure store isolation
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

        # 2. Gather product and economics context
        product: Optional[Product] = None
        total_inventory = 0
        margin_pct: Optional[float] = None

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
                if product.price and product.unit_cost and product.price > 0:
                    margin_pct = round(
                        float((product.price - product.unit_cost) / product.price) * 100, 1
                    )

        # 3. Assemble structured context for provider
        context: Dict[str, Any] = {
            "leak_id": str(leak.id),
            "leak_type": leak.leak_type,
            "metric_affected": leak.metric_affected,
            "observed_value": float(leak.observed_value),
            "baseline_value": float(leak.baseline_value),
            "sample_size": leak.sample_size,
            "severity": leak.severity,
            "evidence_quality": leak.evidence_quality,
            "confidence_score": float(leak.confidence_score) if leak.confidence_score else 0.85,
            "period_start": str(leak.period_start),
            "period_end": str(leak.period_end),
            "reason": leak.reason,
            "product_title": product.title if product else "Storewide Funnel",
            "product_type": product.product_type if product else None,
            "price": float(product.price) if product and product.price else None,
            "unit_cost": float(product.unit_cost) if product and product.unit_cost else None,
            "margin_pct": margin_pct,
            "inventory_quantity": total_inventory,
            "is_significant": "Statistically significant" in leak.reason,
        }

        # 4. Invoke LLM provider / deterministic engine
        output: DiagnosisOutput = self.provider.diagnose_leak(context)

        # 5. Build AIDiagnosis model
        is_fallback = self.provider.provider_name == "fallback"

        # Check if diagnosis already exists for this leak
        diag_stmt = select(AIDiagnosis).where(AIDiagnosis.leak_id == leak.id)
        existing_diag = self.db.execute(diag_stmt).scalar_one_or_none()

        if existing_diag:
            existing_diag.provider = self.provider.provider_name
            existing_diag.issue_summary = output.issue_summary
            existing_diag.evidence = [obs.model_dump() for obs in output.observations]
            existing_diag.possible_explanations = [hyp.model_dump() for hyp in output.hypotheses]
            existing_diag.missing_information = output.missing_information
            existing_diag.recommended_investigation = output.recommended_investigation
            existing_diag.further_checks = output.recommended_investigation
            existing_diag.recommended_actions = output.recommended_actions
            existing_diag.confidence_level = output.confidence_level
            existing_diag.is_fallback = is_fallback
            diagnosis_record = existing_diag
        else:
            diagnosis_record = AIDiagnosis(
                leak_id=leak.id,
                provider=self.provider.provider_name,
                issue_summary=output.issue_summary,
                evidence=[obs.model_dump() for obs in output.observations],
                possible_explanations=[hyp.model_dump() for hyp in output.hypotheses],
                missing_information=output.missing_information,
                recommended_investigation=output.recommended_investigation,
                further_checks=output.recommended_investigation,
                recommended_actions=output.recommended_actions,
                confidence_level=output.confidence_level,
                is_fallback=is_fallback,
            )
            if save_to_db:
                self.db.add(diagnosis_record)

        if save_to_db:
            self.db.commit()
            self.db.refresh(diagnosis_record)

        return diagnosis_record
