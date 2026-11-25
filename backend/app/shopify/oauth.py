"""Shopify OAuth Authorization Code Grant helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict
import httpx

from app.config import get_settings
from app.shopify.client import ShopifyApiError
from app.utils.security import normalize_shop_domain


def build_authorization_url(shop: str, state: str) -> str:
    """Construct the official Shopify OAuth authorization URL for standard web apps."""
    settings = get_settings()
    normalized_shop = normalize_shop_domain(shop)

    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": settings.SHOPIFY_REDIRECT_URI,
        "state": state,
    }
    query_string = urllib.parse.urlencode(params)
    return f"https://{normalized_shop}/admin/oauth/authorize?{query_string}"


def exchange_code_for_token(shop: str, code: str) -> Dict[str, Any]:
    """Exchange authorization code for permanent offline access token."""
    settings = get_settings()
    normalized_shop = normalize_shop_domain(shop)

    token_url = f"https://{normalized_shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_API_KEY,
        "client_secret": settings.SHOPIFY_API_SECRET,
        "code": code,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(token_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data
    except httpx.HTTPStatusError as exc:
        raise ShopifyApiError(
            f"Failed to exchange authorization code for access token: {exc.response.text}",
            status_code=exc.response.status_code,
        )
    except httpx.RequestError as exc:
        raise ShopifyApiError(f"Network error contacting Shopify OAuth endpoint: {exc}")
