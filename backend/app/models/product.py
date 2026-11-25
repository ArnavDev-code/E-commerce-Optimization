"""Product, variant, and inventory models."""

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
    from app.models.order import OrderItem
    from app.models.leak import DetectedLeak
    from app.models.experiment import Experiment


class Product(Base):
    """Represents a product synced from Shopify or provided in demo."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connected_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shopify_product_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(50), default="shopify", nullable=False, comment="demo|shopify|manual"
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="COGS, merchant supplied or synced"
    )
    cost_source: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="shopify|manual|upload"
    )
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shopify_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    store: Mapped[ConnectedStore] = relationship("ConnectedStore", back_populates="products")
    variants: Mapped[List[ProductVariant]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[List[OrderItem]] = relationship("OrderItem", back_populates="product")
    leaks: Mapped[List[DetectedLeak]] = relationship("DetectedLeak", back_populates="product")
    experiments: Mapped[List[Experiment]] = relationship("Experiment", back_populates="product")


class ProductVariant(Base):
    """Represents a product SKU / variant."""

    __tablename__ = "product_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shopify_variant_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inventory_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    inventory_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="variants")
    inventory_snapshots: Mapped[List[InventorySnapshot]] = relationship(
        "InventorySnapshot", back_populates="variant", cascade="all, delete-orphan"
    )


class InventorySnapshot(Base):
    """Daily or periodic inventory level snapshot for stock velocity & runout analysis."""

    __tablename__ = "inventory_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    variant: Mapped[ProductVariant] = relationship(
        "ProductVariant", back_populates="inventory_snapshots"
    )
