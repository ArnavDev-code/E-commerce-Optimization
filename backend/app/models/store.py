"""Connected store model (Shopify store connection)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.product import Product
    from app.models.order import Order
    from app.models.event import StorefrontEvent
    from app.models.analytics import FunnelMetric, GA4Metric
    from app.models.leak import DetectedLeak, Recommendation
    from app.models.experiment import Experiment
    from app.models.sync import SyncLog


class ConnectedStore(Base):
    """Represents a connected Shopify (or other platform) store."""

    __tablename__ = "connected_stores"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), default="shopify", nullable=False)
    shop_domain: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        String(50), default="idle", nullable=False, comment="idle|syncing|success|failed"
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_source: Mapped[str] = mapped_column(
        String(50), default="shopify", nullable=False, comment="demo|shopify|manual"
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uninstalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="stores")
    products: Mapped[List[Product]] = relationship(
        "Product", back_populates="store", cascade="all, delete-orphan"
    )
    orders: Mapped[List[Order]] = relationship(
        "Order", back_populates="store", cascade="all, delete-orphan"
    )
    events: Mapped[List[StorefrontEvent]] = relationship(
        "StorefrontEvent", back_populates="store", cascade="all, delete-orphan"
    )
    ga4_metrics: Mapped[List[GA4Metric]] = relationship(
        "GA4Metric", back_populates="store", cascade="all, delete-orphan"
    )
    funnel_metrics: Mapped[List[FunnelMetric]] = relationship(
        "FunnelMetric", back_populates="store", cascade="all, delete-orphan"
    )
    leaks: Mapped[List[DetectedLeak]] = relationship(
        "DetectedLeak", back_populates="store", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List[Recommendation]] = relationship(
        "Recommendation", back_populates="store", cascade="all, delete-orphan"
    )
    experiments: Mapped[List[Experiment]] = relationship(
        "Experiment", back_populates="store", cascade="all, delete-orphan"
    )
    sync_logs: Mapped[List[SyncLog]] = relationship(
        "SyncLog", back_populates="store", cascade="all, delete-orphan"
    )
