"""Revenue leak detection, AI diagnosis, and recommendation models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.store import ConnectedStore
    from app.models.product import Product
    from app.models.experiment import Experiment


class DetectedLeak(Base):
    """Represents a potential conversion/revenue leak detected by the analytics engine.
    
    Contains strictly deterministic metrics, sample sizes, and baselines.
    """

    __tablename__ = "detected_leaks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True
    )
    leak_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="low_atc_rate|atc_rate_decline|high_atc_low_checkout|low_purchase_completion|...",
    )
    metric_affected: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    baseline_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", comment="critical|high|medium|low"
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence_quality: Mapped[str] = mapped_column(
        String(20), default="moderate", nullable=False, comment="strong|moderate|weak"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False, comment="new|reviewed|resolved|dismissed"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="leaks")
    product: Mapped[Product | None] = relationship("Product", back_populates="leaks")
    diagnoses: Mapped[List[AIDiagnosis]] = relationship(
        "AIDiagnosis", back_populates="leak", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List[Recommendation]] = relationship(
        "Recommendation", back_populates="leak"
    )


class AIDiagnosis(Base):
    """LLM or deterministic fallback diagnosis for a detected leak.
    
    Strictly separates observed facts from speculative explanations.
    """

    __tablename__ = "ai_diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    leak_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("detected_leaks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(50), default="fallback", nullable=False, comment="openai|anthropic|fallback"
    )
    issue_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Any] = mapped_column(
        JSON, nullable=False, comment="Observed facts verified by analytics engine"
    )
    possible_explanations: Mapped[Any] = mapped_column(
        JSON, nullable=False, comment="Hypothesized reasons; distinguished from facts"
    )
    further_checks: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="Recommended checks to confirm root cause"
    )
    missing_information: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="Missing data or telemetry needed to verify cause"
    )
    recommended_investigation: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="Next steps for merchant investigation"
    )
    recommended_actions: Mapped[Any] = mapped_column(
        JSON, nullable=False, comment="Concrete CRO interventions"
    )
    confidence_level: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False, comment="high|medium|low"
    )
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    leak: Mapped[DetectedLeak] = relationship("DetectedLeak", back_populates="diagnoses")


class Recommendation(Base):
    """Prioritised CRO recommendation awaiting merchant approval."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leak_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("detected_leaks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_stage: Mapped[str] = mapped_column(
        String(50), nullable=False, default="product_page", comment="product_page|cart|checkout|post_purchase"
    )
    expected_direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="increase", comment="increase|decrease"
    )
    detected_problem: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[Any] = mapped_column(JSON, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    business_reason: Mapped[str] = mapped_column(Text, nullable=False)
    potential_impact_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Estimated profit/revenue gain or None if COGS missing"
    )
    implementation_effort: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False, comment="low|medium|high"
    )
    confidence_level: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False, comment="high|medium|low"
    )
    priority_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="0.00 to 100.00 composite score"
    )
    priority_breakdown: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="Scoring components: impact, confidence, margin_stock, feasibility"
    )
    risks_or_prerequisites: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="Prerequisites, risks, or caveats"
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False, comment="critical|high|medium|low"
    )
    metric_to_monitor: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False, comment="new|pending|accepted|approved|rejected|in_progress|completed"
    )
    merchant_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="recommendations")
    leak: Mapped[DetectedLeak | None] = relationship("DetectedLeak", back_populates="recommendations")
    experiments: Mapped[List[Experiment]] = relationship(
        "Experiment", back_populates="recommendation"
    )
