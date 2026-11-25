"""Storefront event model (Web Pixel ingestion)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.store import ConnectedStore


class StorefrontEvent(Base):
    """Raw or normalized customer behavior event collected via Web Pixel.
    
    Contains no PII; customer identity is anonymous session/client IDs.
    """

    __tablename__ = "storefront_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="page_viewed|product_viewed|product_added_to_cart|checkout_started|checkout_completed",
    )
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    shopify_product_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    device_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    traffic_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="events")

    __table_args__ = (
        Index("ix_storefront_events_store_type_time", "store_id", "event_type", "event_timestamp"),
    )
