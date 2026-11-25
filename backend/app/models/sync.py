"""Data synchronization and audit logging models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.store import ConnectedStore


class SyncLog(Base):
    """Audit log of data synchronization runs (Shopify Admin API, GA4, pixel processing)."""

    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="products|orders|inventory|ga4|pixel|funnel_aggregation"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="started", comment="started|completed|failed"
    )
    records_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="sync_logs")
