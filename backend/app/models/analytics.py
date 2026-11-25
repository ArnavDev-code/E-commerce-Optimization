"""Analytics models for aggregated funnel metrics and GA4 data."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.store import ConnectedStore
    from app.models.product import Product


class GA4Metric(Base):
    """Reporting data retrieved from Google Analytics 4 Data API."""

    __tablename__ = "ga4_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dimension_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="product|device|source|overall"
    )
    dimension_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    users: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    add_to_carts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkouts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    purchases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="ga4_metrics")

    __table_args__ = (
        Index("ix_ga4_metrics_store_dim_date", "store_id", "dimension_type", "report_date"),
    )


class FunnelMetric(Base):
    """Computed funnel performance metrics.
    
    CRITICAL: data_source is tracked explicitly (pixel | ga4 | shopify) to ensure
    denominators and event definitions are never silently mixed.
    """

    __tablename__ = "funnel_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True
    )
    data_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pixel", comment="pixel|ga4|shopify"
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    segment_type: Mapped[str] = mapped_column(
        String(50), default="overall", nullable=False, comment="overall|device|source"
    )
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Funnel counts
    product_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    add_to_carts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    add_to_cart_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="add_to_carts / product_views * 100"
    )
    checkout_starts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkout_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="checkout_starts / add_to_carts * 100"
    )
    purchases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    purchase_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="purchases / checkout_starts * 100"
    )

    # Financial / efficiency metrics
    revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    aov: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    revenue_per_visitor: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    gross_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Only populated if COGS is available"
    )
    gross_profit_per_visitor: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="funnel_metrics")
    product: Mapped[Product | None] = relationship("Product")

    __table_args__ = (
        Index("ix_funnel_metrics_store_prod_dates", "store_id", "product_id", "period_start", "period_end"),
    )
