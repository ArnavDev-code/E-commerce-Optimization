"""Tests for authentication and merchant accounts."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.auth import (
    get_current_merchant,
    get_me,
    login,
    login_demo,
    register,
)
from app.api.router import health_check
from app.schemas.auth import MerchantLogin, MerchantRegister


def test_health_check() -> None:
    """Verify system health endpoint returns status ok."""
    response = health_check()
    assert response == {"status": "ok", "service": "FunnelLeak AI Backend"}


def test_merchant_register_and_login(db: Session) -> None:
    """Test standard merchant registration followed by login."""
    # 1. Register new merchant
    reg_payload = MerchantRegister(
        email="sarah@fashionbrand.com",
        password="strongPassword123!",
        name="Sarah Designer",
    )
    reg_res = register(reg_payload, db=db)
    assert reg_res.access_token is not None
    assert reg_res.merchant.email == "sarah@fashionbrand.com"
    assert reg_res.merchant.is_demo is False

    # 2. Reject duplicate email
    with pytest.raises(HTTPException) as exc_info:
        register(reg_payload, db=db)
    assert exc_info.value.status_code == 400
    assert "already exists" in exc_info.value.detail

    # 3. Successful login
    login_payload = MerchantLogin(
        email="sarah@fashionbrand.com",
        password="strongPassword123!",
    )
    login_res = login(login_payload, db=db)
    assert login_res.access_token is not None
    assert login_res.token_type == "bearer"
    token = login_res.access_token

    # 4. Failed login (wrong password)
    with pytest.raises(HTTPException) as exc_info_bad:
        login(MerchantLogin(email="sarah@fashionbrand.com", password="wrongPassword"), db=db)
    assert exc_info_bad.value.status_code == 401

    # 5. Resolve merchant from Bearer credentials
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    resolved_merchant = get_current_merchant(creds, db=db)
    assert resolved_merchant.email == "sarah@fashionbrand.com"

    profile = get_me(current_merchant=resolved_merchant)
    assert profile.email == "sarah@fashionbrand.com"


def test_demo_login_flow(db: Session) -> None:
    """Test demo login automatically provisions demo merchant."""
    demo_res = login_demo(db=db)
    assert demo_res.access_token is not None
    assert demo_res.merchant.email == "demo@funnelleak.ai"
    assert demo_res.merchant.is_demo is True
