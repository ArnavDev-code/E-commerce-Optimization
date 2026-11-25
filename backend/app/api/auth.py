"""Authentication API routes and JWT security dependencies."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.merchant import Merchant
from app.models.store import ConnectedStore
from app.schemas.auth import (
    MerchantLogin,
    MerchantRegister,
    MerchantResponse,
    TokenResponse,
)
from app.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

security_bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def get_current_merchant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    db: Session = Depends(get_db),
) -> Merchant:
    """Dependency that authenticates the merchant from Bearer JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        merchant_id_str: str | None = payload.get("sub")
        if merchant_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject identifier",
                headers={"WWW-Authenticate": "Bearer"},
            )
        merchant_id = uuid.UUID(merchant_id_str)
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    merchant = db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    ).scalar_one_or_none()

    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Merchant not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return merchant


def get_current_store(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    db: Session = Depends(get_db),
) -> ConnectedStore:
    """Dependency ensuring store isolation: returns the active store for the current merchant."""
    store = db.execute(
        select(ConnectedStore).where(
            ConnectedStore.merchant_id == merchant.id,
            ConnectedStore.is_active == True,
        )
    ).scalar_one_or_none()

    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active connected store found for this merchant",
        )
    return store


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: MerchantRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new merchant and create a default store placeholder."""
    existing = db.execute(
        select(Merchant).where(Merchant.email == payload.email)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    merchant = Merchant(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name or payload.email.split("@")[0],
        is_demo=False,
    )
    db.add(merchant)
    db.flush()

    # Create associated default store placeholder
    store_domain = f"{merchant.email.split('@')[0]}.myshopify.com"
    store = ConnectedStore(
        merchant_id=merchant.id,
        platform="shopify",
        shop_domain=store_domain,
        is_active=True,
    )
    db.add(store)
    db.commit()
    db.refresh(merchant)

    token = create_access_token({"sub": str(merchant.id), "email": merchant.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        merchant=MerchantResponse.model_validate(merchant),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: MerchantLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate merchant with email and password."""
    merchant = db.execute(
        select(Merchant).where(Merchant.email == payload.email)
    ).scalar_one_or_none()

    if not merchant or not verify_password(payload.password, merchant.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(merchant.id), "email": merchant.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        merchant=MerchantResponse.model_validate(merchant),
    )


@router.post("/demo", response_model=TokenResponse)
def login_demo(db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate or auto-provision the demo merchant account.
    
    Allows prospective merchants to explore all features with realistic seeded data.
    """
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is disabled on this server instance",
        )

    demo_email = "demo@funnelleak.ai"
    merchant = db.execute(
        select(Merchant).where(Merchant.email == demo_email)
    ).scalar_one_or_none()

    if not merchant:
        # Create demo merchant if not yet seeded
        merchant = Merchant(
            email=demo_email,
            password_hash=hash_password("demo123"),
            name="Demo Fashion & Skincare Store",
            is_demo=True,
        )
        db.add(merchant)
        db.flush()

        store = ConnectedStore(
            merchant_id=merchant.id,
            platform="shopify",
            shop_domain="demo-store.myshopify.com",
            is_active=True,
        )
        db.add(store)
        db.commit()
        db.refresh(merchant)

    token = create_access_token({"sub": str(merchant.id), "email": merchant.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        merchant=MerchantResponse.model_validate(merchant),
    )


@router.get("/me", response_model=MerchantResponse)
def get_me(current_merchant: Merchant = Depends(get_current_merchant)) -> MerchantResponse:
    """Get the currently authenticated merchant profile."""
    return MerchantResponse.model_validate(current_merchant)
