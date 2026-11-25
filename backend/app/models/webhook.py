"""Shopify webhook delivery and audit logging model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.store import ConnectedStore


class WebhookDelivery(Base):
    """Logs incoming Shopify webhook deliveries for idempotency and audit trails."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=True, index=True
    )
    webhook_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, comment="X-Shopify-Webhook-Id for idempotency"
    )
    topic: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="products/update, orders/create, etc."
    )
    shop_domain: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="processed", nullable=False, comment="processed|failed|ignored"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[ConnectedStore | None] = relationship("ConnectedStore")
