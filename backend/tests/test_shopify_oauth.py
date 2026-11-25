"""Tests for Shopify OAuth authorization, HMAC verification, and token encryption."""

from __future__ import annotations

import hashlib
import hmac
import uuid
import pytest
from sqlalchemy.orm import Session

from app.api.auth import get_current_merchant
from app.api.shopify import authorize_store, disconnect_store
from app.config import get_settings
from app.models.merchant import Merchant
from app.models.store import ConnectedStore
from app.schemas.shopify import ShopifyAuthorizeRequest
from app.utils.security import (
    decrypt_token,
    encrypt_token,
    generate_oauth_state,
    normalize_shop_domain,
    verify_oauth_state,
    verify_shopify_hmac,
)

settings = get_settings()


def test_normalize_shop_domain() -> None:
    """Verify robust normalization and regex validation of Shopify shop domains."""
    assert normalize_shop_domain("my-store") == "my-store.myshopify.com"
    assert normalize_shop_domain("my-store.myshopify.com") == "my-store.myshopify.com"
    assert normalize_shop_domain("https://boutique-chic.myshopify.com/") == "boutique-chic.myshopify.com"
    assert normalize_shop_domain("UPPER-CASE.myshopify.com") == "upper-case.myshopify.com"

    # Invalid domains
    with pytest.raises(ValueError):
        normalize_shop_domain("")
    with pytest.raises(ValueError):
        normalize_shop_domain("invalid_domain!@#.com")
    with pytest.raises(ValueError):
        normalize_shop_domain("-starts-with-dash.myshopify.com")


def test_oauth_state_signing_and_validation() -> None:
    """Verify cryptographically signed OAuth state nonce prevents CSRF."""
    merchant_id = uuid.uuid4()
    shop = "wellness-co.myshopify.com"

    state = generate_oauth_state(merchant_id, shop)
    assert isinstance(state, str)
    assert len(state) > 30

    # Successful verification
    verified_merchant_id = verify_oauth_state(state, shop)
    assert verified_merchant_id == merchant_id

    # Shop mismatch rejection
    with pytest.raises(ValueError, match="State token shop does not match"):
        verify_oauth_state(state, "different-shop.myshopify.com")

    # Tampered state token rejection
    tampered = state[:-4] + "abcd"
    with pytest.raises(ValueError):
        verify_oauth_state(tampered, shop)


def test_shopify_callback_hmac_verification() -> None:
    """Verify Shopify OAuth callback query string HMAC-SHA256 signature checking."""
    secret = "test-shopify-secret-key-12345"
    query_params = {
        "code": "auth_code_xyz987",
        "shop": "beauty-glow.myshopify.com",
        "state": "valid-state-nonce",
        "timestamp": "1710000000",
    }

    # Compute expected Shopify HMAC: sort keys lexicographically, format as k=v&...
    sorted_parts = [f"{k}={query_params[k]}" for k in sorted(query_params.keys())]
    message = "&".join(sorted_parts).encode("utf-8")
    valid_hmac = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    params_with_hmac = {**query_params, "hmac": valid_hmac}

    # Valid HMAC passes
    assert verify_shopify_hmac(params_with_hmac, secret) is True

    # Tampered parameter fails
    tampered_params = {**params_with_hmac, "code": "tampered_code"}
    assert verify_shopify_hmac(tampered_params, secret) is False

    # Missing HMAC fails
    assert verify_shopify_hmac(query_params, secret) is False


def test_token_encryption_at_rest() -> None:
    """Verify offline access tokens are securely encrypted and never stored in plaintext."""
    raw_token = "shpat_live_merchant_offline_token_987654321"

    encrypted = encrypt_token(raw_token)
    assert encrypted != raw_token
    assert "shpat_" not in encrypted

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_token

    # Empty string edge cases
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_oauth_authorize_and_cross_merchant_protection(db: Session) -> None:
    """Ensure merchants cannot connect a shop actively claimed by another merchant."""
    # Merchant A
    m_a = Merchant(email="merchant_a@example.com", password_hash="testhash", is_demo=False)
    db.add(m_a)
    db.flush()

    # Store A connected actively
    store_a = ConnectedStore(
        merchant_id=m_a.id,
        shop_domain="brand-a.myshopify.com",
        access_token_encrypted=encrypt_token("token_a"),
        is_active=True,
    )
    db.add(store_a)

    # Merchant B
    m_b = Merchant(email="merchant_b@example.com", password_hash="testhash", is_demo=False)
    db.add(m_b)
    db.commit()

    # Merchant A can authorize their own store
    resp_a = authorize_store(
        payload=ShopifyAuthorizeRequest(shop="brand-a.myshopify.com"),
        merchant=m_a,
        db=db,
    )
    assert "admin/oauth/authorize" in resp_a.authorization_url
    assert resp_a.shop == "brand-a.myshopify.com"

    # Merchant B attempts to connect brand-a.myshopify.com -> Must be rejected!
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        authorize_store(
            payload=ShopifyAuthorizeRequest(shop="brand-a.myshopify.com"),
            merchant=m_b,
            db=db,
        )
    assert exc_info.value.status_code == 400
    assert "already actively connected to another FunnelLeak merchant account" in exc_info.value.detail


def test_store_disconnection_revokes_credentials(db: Session) -> None:
    """Verify disconnecting a store sets is_active=False and wipes stored credentials."""
    m = Merchant(email="disconnect_test@example.com", password_hash="testhash", is_demo=False)
    db.add(m)
    db.flush()

    store = ConnectedStore(
        merchant_id=m.id,
        shop_domain="disconnect-me.myshopify.com",
        access_token_encrypted=encrypt_token("live_secret_token"),
        is_active=True,
    )
    db.add(store)
    db.commit()

    res = disconnect_store(store=store, db=db)
    assert res["status"] == "disconnected"

    # Verify state in DB
    db.refresh(store)
    assert store.is_active is False
    assert store.access_token_encrypted is None
    assert store.uninstalled_at is not None
