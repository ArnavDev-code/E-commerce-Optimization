"""Google OAuth 2.0 flow helpers for Google Analytics 4."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


class GoogleOAuthError(Exception):
    """Exception raised for Google OAuth errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def build_google_auth_url(state: str, redirect_uri: Optional[str] = None) -> str:
    """Generate Google OAuth 2.0 authorization URL requesting analytics.readonly scope."""
    settings = get_settings()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.GOOGLE_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Exchange OAuth authorization code for access and refresh tokens."""
    settings = get_settings()
    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(GOOGLE_TOKEN_ENDPOINT, data=payload)
            if response.status_code != 200:
                logger.error(f"Google token exchange failed: {response.text}")
                raise GoogleOAuthError(
                    f"Token exchange failed with status {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )
            return response.json()
    except httpx.RequestError as exc:
        logger.error(f"Network error during Google token exchange: {exc}")
        raise GoogleOAuthError(f"Network error contacting Google OAuth token endpoint: {exc}")


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh an expired access token using the stored refresh token."""
    settings = get_settings()
    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(GOOGLE_TOKEN_ENDPOINT, data=payload)
            if response.status_code != 200:
                logger.error(f"Google token refresh failed: {response.text}")
                raise GoogleOAuthError(
                    f"Token refresh failed with status {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )
            return response.json()
    except httpx.RequestError as exc:
        logger.error(f"Network error during Google token refresh: {exc}")
        raise GoogleOAuthError(f"Network error contacting Google OAuth token endpoint: {exc}")


def revoke_token(token: str) -> bool:
    """Revoke a Google OAuth access or refresh token upon disconnection."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                GOOGLE_REVOKE_ENDPOINT,
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return response.status_code == 200
    except Exception as exc:
        logger.warning(f"Error revoking Google token: {exc}")
        return False
