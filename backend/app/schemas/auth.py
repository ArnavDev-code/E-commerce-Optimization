"""Authentication Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MerchantRegister(BaseModel):
    """Payload for merchant registration."""

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=255)


class MerchantLogin(BaseModel):
    """Payload for merchant login."""

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str


class MerchantResponse(BaseModel):
    """Safe merchant profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    is_demo: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT Bearer token response with merchant context."""

    access_token: str
    token_type: str = "bearer"
    merchant: MerchantResponse
