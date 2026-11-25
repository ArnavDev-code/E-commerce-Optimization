"""Experiment tracking and results models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
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
    from app.models.leak import Recommendation


class Experiment(Base):
    """Tracks a merchant-approved CRO experiment (before/after or split test).
    
    Explicitly tracks experiment_type ('before_after' vs 'ab_test') so merchants
    are never misled that a chronological comparison is a controlled randomized trial.
    """

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    experiment_type: Mapped[str] = mapped_column(
        String(50), default="before_after", nullable=False, comment="before_after|ab_test"
    )
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_made: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False, comment="draft|running|completed|cancelled"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metric_to_track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="experiments")
    recommendation: Mapped[Recommendation | None] = relationship(
        "Recommendation", back_populates="experiments"
    )
    product: Mapped[Product | None] = relationship("Product", back_populates="experiments")
    results: Mapped[List[ExperimentResult]] = relationship(
        "ExperimentResult", back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentResult(Base):
    """Measured performance outcome for an experiment period."""

    __tablename__ = "experiment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    control_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    treatment_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    absolute_change: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    relative_change_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    control_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    treatment_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    is_statistically_significant: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="Only true if 2-proportion z-test p < 0.05"
    )
    p_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    merchant_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="results")
