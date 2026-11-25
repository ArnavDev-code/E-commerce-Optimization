"""Analytics and product Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Product Schemas ───────────────────────────────────────────────────────────

class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shopify_variant_id: Optional[str] = None
    sku: Optional[str] = None
    title: Optional[str] = None
    price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    inventory_quantity: int
    available: bool


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    shopify_product_id: Optional[str] = None
    title: str
    handle: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    status: str
    price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    cost_source: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    synced_at: Optional[datetime] = None
    variants: List[VariantResponse] = []

    # Dynamically aggregated metrics
    views: int = 0
    add_to_carts: int = 0
    add_to_cart_rate: Optional[Decimal] = None
    purchases: int = 0
    revenue: Decimal = Decimal("0.00")
    gross_margin_pct: Optional[Decimal] = None


class ProductCostUpdate(BaseModel):
    """Payload for updating product unit cost (COGS)."""
    unit_cost: Decimal = Field(gt=0, description="Cost of goods sold per unit")
    cost_source: str = Field(default="manual", description="shopify|manual|upload")


class BulkCostItem(BaseModel):
    sku: Optional[str] = None
    handle: Optional[str] = None
    product_id: Optional[uuid.UUID] = None
    unit_cost: Decimal = Field(gt=0)


class BulkCostUploadRequest(BaseModel):
    items: List[BulkCostItem]


# ── Analytics Schemas ─────────────────────────────────────────────────────────

class FunnelStageMetric(BaseModel):
    stage: str
    count: int
    conversion_rate: Optional[Decimal] = None  # Progression rate from prior stage
    dropoff_rate: Optional[Decimal] = None
    data_source: str = "pixel"


class SegmentBreakdown(BaseModel):
    segment_value: str
    views: int
    add_to_carts: int
    add_to_cart_rate: Optional[Decimal] = None
    purchases: int
    conversion_rate: Optional[Decimal] = None
    revenue: Decimal


class FunnelAnalyticsResponse(BaseModel):
    period_start: date
    period_end: date
    data_source: str = "pixel"
    stages: List[FunnelStageMetric]
    device_breakdown: List[SegmentBreakdown]
    source_breakdown: List[SegmentBreakdown]


class AnalyticsOverviewResponse(BaseModel):
    period_start: date
    period_end: date
    total_sessions: int
    total_views: int
    total_add_to_carts: int
    total_orders: int
    revenue: Decimal
    aov: Decimal
    overall_conversion_rate: Decimal
    gross_profit: Optional[Decimal] = None
    gross_profit_per_visitor: Optional[Decimal] = None
    detected_leaks_count: int
    data_source: str = "pixel"


# ── Leak Schemas ──────────────────────────────────────────────────────────────

class DetectedLeakResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_title: Optional[str] = None
    product_handle: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_cost: Optional[Decimal] = None
    leak_type: str
    metric_affected: str
    observed_value: Decimal
    baseline_value: Decimal
    sample_size: int
    period_start: date
    period_end: date
    severity: str
    confidence_score: Optional[Decimal] = None
    evidence_quality: str
    reason: str
    status: str
    detected_at: datetime


class LeakDetectRequest(BaseModel):
    days: int = Field(default=30, ge=7, le=90)
    min_sample_size: int = Field(default=50, ge=10)
