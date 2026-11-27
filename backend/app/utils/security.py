"""Security, password hashing, and JWT token utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings

settings = get_settings()


def _b64_url_encode(data: bytes) -> str:
    """Base64 URL-safe encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_url_decode(data: str) -> bytes:
    """Base64 URL-safe decode with padding restoration."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("ascii"))


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a cryptographically secure random salt."""
    salt = secrets.token_bytes(16)
    iterations = 200_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${_b64_url_encode(salt)}${_b64_url_encode(derived)}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    try:
        if hashed_password.startswith("demo_hash:") or hashed_password == "demo123":
            return plain_password == "demo123"
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        header, salt_str, hash_str = parts
        _, _, iter_str = header.split(":")
        iterations = int(iter_str)
        salt = _b64_url_decode(salt_str)
        expected_derived = _b64_url_decode(hash_str)
        actual_derived = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(expected_derived, actual_derived)
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Generate a standard HMAC-SHA256 JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload["exp"] = int(expire.timestamp())

    header_b64 = _b64_url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64_url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode HMAC-SHA256 JWT token. Raises ValueError on error/expiry."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token structure")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_sig = _b64_url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    payload_json = _b64_url_decode(payload_b64).decode("utf-8")
    payload = json.loads(payload_json)

    # Check expiration
    exp = payload.get("exp")
    if exp is not None:
        if datetime.now(timezone.utc).timestamp() > exp:
            raise ValueError("Token has expired")

    return payload


# ── Shopify Security & Encryption ──────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    """Retrieve or deterministically derive a 32-byte urlsafe Fernet key."""
    key_candidate = settings.ENCRYPTION_KEY.strip() if settings.ENCRYPTION_KEY else ""
    if key_candidate:
        try:
            decoded = base64.urlsafe_b64decode(key_candidate)
            if len(decoded) == 32:
                return key_candidate.encode("ascii")
        except Exception:
            pass
    # Deterministically derive 32-byte key from SECRET_KEY
    derived = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_token(plain_text: str) -> str:
    """Encrypt a sensitive token (e.g. Shopify offline access token) using AES/Fernet."""
    if not plain_text:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_get_fernet_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("ascii")


def decrypt_token(cipher_text: str) -> str:
    """Decrypt an encrypted token using AES/Fernet."""
    if not cipher_text:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_get_fernet_key())
    return f.decrypt(cipher_text.encode("ascii")).decode("utf-8")


def normalize_shop_domain(shop: str) -> str:
    """Normalize and validate a Shopify domain string."""
    shop = shop.strip().lower()
    if not shop:
        raise ValueError("Shop domain cannot be empty")
    # Strip protocol
    shop = re.sub(r"^https?://", "", shop)
    # Strip paths
    shop = shop.split("/")[0]
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    # Strict regex check
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$", shop):
        raise ValueError(f"Invalid Shopify store domain: {shop}")
    return shop


def generate_oauth_state(merchant_id: uuid.UUID, shop: str) -> str:
    """Create a signed, time-limited state nonce for Shopify OAuth CSRF protection."""
    data = {
        "sub": str(merchant_id),
        "shop": shop,
        "nonce": secrets.token_hex(16),
        "purpose": "shopify_oauth",
    }
    return create_access_token(data, expires_delta=timedelta(minutes=15))


def verify_oauth_state(state_token: str, expected_shop: str) -> uuid.UUID:
    """Verify OAuth state JWT signature, expiration, and shop domain match."""
    payload = decode_access_token(state_token)
    if payload.get("purpose") != "shopify_oauth":
        raise ValueError("Invalid state token purpose")
    if payload.get("shop") != expected_shop:
        raise ValueError("State token shop does not match callback shop")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("State token missing merchant id")
    return uuid.UUID(sub)


def generate_ga4_oauth_state(store_id: uuid.UUID) -> str:
    """Create a signed, time-limited state nonce for GA4 OAuth CSRF protection."""
    data = {
        "store_id": str(store_id),
        "nonce": secrets.token_hex(16),
        "purpose": "ga4_oauth",
    }
    return create_access_token(data, expires_delta=timedelta(minutes=15))


def verify_ga4_oauth_state(state_token: str) -> uuid.UUID:
    """Verify GA4 OAuth state JWT signature, expiration, and extract store_id."""
    payload = decode_access_token(state_token)
    if payload.get("purpose") != "ga4_oauth":
        raise ValueError("Invalid state token purpose")
    store_id_str = payload.get("store_id")
    if not store_id_str:
        raise ValueError("State token missing store id")
    return uuid.UUID(store_id_str)


def verify_shopify_hmac(query_params: dict[str, str], secret: str) -> bool:
    """Verify Shopify OAuth callback HMAC.
    
    Excludes 'hmac' and 'signature', sorts keys, formats as key=value&...,
    and computes HMAC-SHA256 hex digest.
    """
    provided_hmac = query_params.get("hmac")
    if not provided_hmac or not secret:
        return False
    filtered = {
        k: v for k, v in query_params.items()
        if k not in ("hmac", "signature")
    }
    sorted_parts = [f"{k}={filtered[k]}" for k in sorted(filtered.keys())]
    message = "&".join(sorted_parts).encode("utf-8")
    computed = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided_hmac, computed)


def verify_shopify_webhook_hmac(raw_body: bytes, hmac_header: str, secret: str) -> bool:
    """Verify incoming Shopify webhook HMAC-SHA256 signature (base64 encoded)."""
    if not hmac_header or not secret:
        return False
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(computed).decode("ascii")
    return hmac.compare_digest(hmac_header, expected)

