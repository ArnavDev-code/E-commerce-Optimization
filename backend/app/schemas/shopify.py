"""Pydantic schemas for Shopify OAuth and store integration."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ShopifyAuthorizeRequest(BaseModel):
    shop: str = Field(description="Shopify store domain (e.g. my-store.myshopify.com)")


class ShopifyAuthorizeResponse(BaseModel):
    authorization_url: str
    shop: str


class SyncLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sync_type: str
    status: str
    records_synced: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class ShopifyStoreStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_domain: str
    is_active: bool
    platform: str
    scopes: Optional[str] = None
    sync_status: str
    last_sync_at: Optional[datetime] = None
    last_sync_error: Optional[str] = None
    data_source: str
    installed_at: datetime
    recent_sync_logs: List[SyncLogResponse] = []


class ShopifySyncResponse(BaseModel):
    status: str
    products_synced: int
    inventory_levels_synced: int
    orders_synced: int
    total_records: int
    synced_at: str
