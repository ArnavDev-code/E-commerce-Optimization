"""Google Analytics 4 API router for OAuth, property selection, and synchronization."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_merchant, get_current_store
from app.config import get_settings
from app.database import get_db
from app.integrations.connectors.ga4.connector import GA4Connector
from app.integrations.connectors.ga4.oauth import (
    GoogleOAuthError,
    build_google_auth_url,
    exchange_code_for_tokens,
)
from app.integrations.connectors.ga4.schemas import (
    GA4ConnectionStatusResponse,
    GA4PropertiesResponse,
    GA4PropertySelectRequest,
    GA4PropertySummary,
    GA4AccountSummary,
    GA4SyncResponse,
)
from app.models.connection import DataSourceConnection
from app.models.merchant import Merchant
from app.models.store import ConnectedStore
from app.utils.security import (
    decrypt_token,
    encrypt_token,
    generate_ga4_oauth_state,
    verify_ga4_oauth_state,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/integrations/ga4", tags=["GA4 Integration"])


@router.get("/connect")
def initiate_ga4_oauth(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
) -> dict:
    """Generate the Google OAuth URL for connecting GA4 to the current store."""
    state = generate_ga4_oauth_state(store.id)
    auth_url = build_google_auth_url(state=state)
    return {"auth_url": auth_url}


@router.get("/callback")
def ga4_oauth_callback(
    code: Annotated[Optional[str], Query()] = None,
    state: Annotated[Optional[str], Query()] = None,
    error: Annotated[Optional[str], Query()] = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback, exchange token, and store encrypted credentials."""
    frontend_redirect_base = f"{settings.FRONTEND_URL}/integrations"

    if error:
        logger.warning(f"Google OAuth denied or returned error: {error}")
        return RedirectResponse(url=f"{frontend_redirect_base}?error={error}")

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter in Google callback.",
        )

    try:
        store_id = verify_ga4_oauth_state(state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired OAuth state parameter: {exc}",
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corrupted store identifier.")

    store = db.execute(
        select(ConnectedStore).where(ConnectedStore.id == store_id)
    ).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated store not found.")

    try:
        tokens = exchange_code_for_tokens(code)
    except GoogleOAuthError as exc:
        logger.error(f"Failed to exchange Google OAuth code: {exc}")
        return RedirectResponse(url=f"{frontend_redirect_base}?error=oauth_exchange_failed")

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    granted_scopes = tokens.get("scope")

    now = datetime.now(timezone.utc)
    token_expiry = now + timedelta(seconds=expires_in)

    # Upsert DataSourceConnection
    stmt = select(DataSourceConnection).where(
        DataSourceConnection.store_id == store.id,
        DataSourceConnection.provider == "ga4",
    )
    conn = db.execute(stmt).scalar_one_or_none()

    if not conn:
        conn = DataSourceConnection(
            store_id=store.id,
            provider="ga4",
            auth_type="oauth",
            encrypted_access_token=encrypt_token(access_token),
            encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
            token_expiry=token_expiry,
            granted_scopes=granted_scopes,
            connection_status="connected",
            last_validated_at=now,
        )
        db.add(conn)
    else:
        conn.encrypted_access_token = encrypt_token(access_token)
        if refresh_token:
            conn.encrypted_refresh_token = encrypt_token(refresh_token)
        conn.token_expiry = token_expiry
        conn.granted_scopes = granted_scopes
        conn.connection_status = "connected"
        conn.last_validated_at = now
        conn.last_sync_error = None

    db.commit()

    return RedirectResponse(url=f"{frontend_redirect_base}?status=ga4_connected")


@router.get("/status", response_model=GA4ConnectionStatusResponse)
def get_ga4_status(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
    db: Session = Depends(get_db),
) -> GA4ConnectionStatusResponse:
    """Get current connection and synchronization status for Google Analytics 4."""
    connector = GA4Connector(db=db, store_id=store.id)
    status_dict = connector.get_sync_status()
    return GA4ConnectionStatusResponse(**status_dict)


@router.get("/properties", response_model=GA4PropertiesResponse)
def list_ga4_properties(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
    db: Session = Depends(get_db),
) -> GA4PropertiesResponse:
    """Discover available GA4 accounts and properties for the connected user."""
    connector = GA4Connector(db=db, store_id=store.id)
    try:
        raw_accounts = connector.discover_resources()
        accounts: list[GA4AccountSummary] = []
        total_props = 0

        for a in raw_accounts:
            props = [GA4PropertySummary(**p) for p in a.get("properties", [])]
            total_props += len(props)
            accounts.append(
                GA4AccountSummary(
                    account_id=a["account_id"],
                    display_name=a["display_name"],
                    properties=props,
                )
            )

        return GA4PropertiesResponse(accounts=accounts, total_properties=total_props)
    except Exception as exc:
        logger.error(f"Failed to list GA4 properties: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve GA4 properties: {str(exc)}",
        )


@router.post("/select-property", response_model=GA4ConnectionStatusResponse)
def select_ga4_property(
    payload: GA4PropertySelectRequest,
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
    db: Session = Depends(get_db),
) -> GA4ConnectionStatusResponse:
    """Select the active GA4 property for tracking."""
    stmt = select(DataSourceConnection).where(
        DataSourceConnection.store_id == store.id,
        DataSourceConnection.provider == "ga4",
    )
    conn = db.execute(stmt).scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GA4 connection not found. Connect GA4 first.",
        )

    clean_property_id = payload.property_id.replace("properties/", "").strip()
    conn.provider_property_id = clean_property_id
    conn.provider_property_name = payload.property_name or f"Property {clean_property_id}"
    conn.connection_status = "connected"
    conn.last_validated_at = datetime.now(timezone.utc)
    db.commit()

    connector = GA4Connector(db=db, store_id=store.id, connection=conn)
    return GA4ConnectionStatusResponse(**connector.get_sync_status())


@router.post("/sync", response_model=GA4SyncResponse)
def sync_ga4_data(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
    db: Session = Depends(get_db),
) -> GA4SyncResponse:
    """Synchronize recent metrics from Google Analytics 4 Data API."""
    connector = GA4Connector(db=db, store_id=store.id)
    conn = connector.get_connection()
    if not conn or not conn.provider_property_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GA4 is not connected or no property has been selected.",
        )

    result = connector.initial_sync()
    if not result.success:
        return GA4SyncResponse(
            success=False,
            message="GA4 sync failed.",
            error=result.error_message,
        )

    return GA4SyncResponse(
        success=True,
        records_synced=result.records_synced,
        message=f"Successfully synced {result.records_synced} GA4 reporting records.",
    )


@router.post("/disconnect")
def disconnect_ga4(
    merchant: Annotated[Merchant, Depends(get_current_merchant)],
    store: Annotated[ConnectedStore, Depends(get_current_store)],
    db: Session = Depends(get_db),
) -> dict:
    """Revoke tokens and disconnect Google Analytics 4."""
    connector = GA4Connector(db=db, store_id=store.id)
    success = connector.disconnect()
    return {"success": success, "message": "GA4 disconnected successfully."}
