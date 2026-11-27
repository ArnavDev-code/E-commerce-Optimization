"""Pydantic schemas for Google Analytics 4 integration."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GA4PropertySummary(BaseModel):
    """A GA4 property representation."""
    property_id: str = Field(..., description="GA4 property resource name, e.g. properties/123456789 or 123456789")
    display_name: str = Field(..., description="User-friendly name of the GA4 property")
    account_id: Optional[str] = Field(None, description="Parent account identifier")
    account_name: Optional[str] = Field(None, description="Parent account display name")


class GA4AccountSummary(BaseModel):
    """A GA4 account containing child properties."""
    account_id: str
    display_name: str
    properties: List[GA4PropertySummary] = Field(default_factory=list)


class GA4PropertiesResponse(BaseModel):
    """Response containing discovered GA4 accounts and properties."""
    accounts: List[GA4AccountSummary]
    total_properties: int


class GA4PropertySelectRequest(BaseModel):
    """Request payload to associate a GA4 property with a store."""
    property_id: str = Field(..., description="Selected GA4 property ID (digits or properties/digits)")
    property_name: Optional[str] = Field(None, description="Display name of the property")


class GA4ConnectionStatusResponse(BaseModel):
    """Current connection and sync status for GA4."""
    is_connected: bool
    connection_status: str = Field(..., description="connected | disconnected | error | expired")
    provider_property_id: Optional[str] = None
    provider_property_name: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    last_sync_error: Optional[str] = None
    token_expired: bool = False


class GA4SyncResponse(BaseModel):
    """Response returned upon triggering a GA4 synchronization."""
    success: bool
    sync_id: Optional[UUID] = None
    records_synced: int = 0
    message: str
    error: Optional[str] = None
