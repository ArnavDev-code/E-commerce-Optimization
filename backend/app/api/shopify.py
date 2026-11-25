"""Shopify OAuth, webhooks, and store integration API endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Header,
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
from app.models.merchant import Merchant
from app.models.store import ConnectedStore
from app.models.sync import SyncLog
from app.schemas.shopify import (
    ShopifyAuthorizeRequest,
    ShopifyAuthorizeResponse,
    ShopifyStoreStatusResponse,
    ShopifySyncResponse,
    SyncLogResponse,
)
from app.shopify.oauth import build_authorization_url, exchange_code_for_token
from app.shopify.sync import ShopifySynchronizer
from app.shopify.webhooks import ShopifyWebhookManager
from app.utils.security import (
    encrypt_token,
    generate_oauth_state,
    normalize_shop_domain,
    verify_oauth_state,
    verify_shopify_hmac,
    verify_shopify_webhook_hmac,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/shopify", tags=["Shopify Integration"])


# ── OAuth Endpoints ───────────────────────────────────────────────────────────

@router.post("/oauth/authorize", response_model=ShopifyAuthorizeResponse)
def authorize_store(
    payload: ShopifyAuthorizeRequest,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> ShopifyAuthorizeResponse:
    """Generate a signed Shopify OAuth authorization URL for the merchant."""
    try:
        normalized_shop = normalize_shop_domain(payload.shop)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Multi-tenancy check: Prevent another merchant from hijacking an actively connected store
    existing_store = db.execute(
        select(ConnectedStore).where(
            ConnectedStore.shop_domain == normalized_shop,
            ConnectedStore.is_active == True,
            ConnectedStore.merchant_id != merchant.id,
        )
    ).scalar_one_or_none()

    if existing_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Store '{normalized_shop}' is already actively connected to another FunnelLeak merchant account.",
        )

    # Generate state token (valid for 15 mins)
    state = generate_oauth_state(merchant.id, normalized_shop)
    auth_url = build_authorization_url(normalized_shop, state)

    return ShopifyAuthorizeResponse(authorization_url=auth_url, shop=normalized_shop)


@router.get("/oauth/callback")
def oauth_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Shopify OAuth redirect callback with HMAC and state verification."""
    # 1. Verify HMAC
    raw_params = dict(request.query_params)
    if not verify_shopify_hmac(raw_params, settings.SHOPIFY_API_SECRET):
        logger.warning("Shopify OAuth callback HMAC verification failed for shop %s", shop)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature from Shopify",
        )

    # 2. Verify state token & extract merchant_id
    try:
        normalized_shop = normalize_shop_domain(shop)
        merchant_id = verify_oauth_state(state, normalized_shop)
    except ValueError as exc:
        logger.warning("Shopify OAuth callback state verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired OAuth state token: {exc}",
        )

    # 3. Exchange code for access token
    try:
        token_data = exchange_code_for_token(normalized_shop, code)
        access_token = token_data.get("access_token")
        granted_scopes = token_data.get("scope", settings.SHOPIFY_SCOPES)
        if not access_token:
            raise ValueError("No access_token returned by Shopify")
    except Exception as exc:
        logger.exception("Failed to exchange code for token on %s", normalized_shop)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to obtain access token from Shopify: {exc}",
        )

    # 4. Encrypt token at rest
    encrypted_token = encrypt_token(access_token)

    # 5. Upsert ConnectedStore
    now = datetime.now(timezone.utc)
    store = db.execute(
        select(ConnectedStore).where(ConnectedStore.shop_domain == normalized_shop)
    ).scalar_one_or_none()

    if store:
        # Reconnection / update credentials
        store.merchant_id = merchant_id
        store.access_token_encrypted = encrypted_token
        store.scopes = granted_scopes
        store.is_active = True
        store.data_source = "shopify"
        store.sync_status = "idle"
        store.uninstalled_at = None
        store.installed_at = now
    else:
        store = ConnectedStore(
            merchant_id=merchant_id,
            platform="shopify",
            shop_domain=normalized_shop,
            access_token_encrypted=encrypted_token,
            scopes=granted_scopes,
            is_active=True,
            data_source="shopify",
            sync_status="idle",
            installed_at=now,
        )
        db.add(store)

    db.commit()
    db.refresh(store)

    # 6. Kick off initial sync in background
    def run_initial_sync(store_id: uuid.UUID):
        from app.database import SessionLocal
        with SessionLocal() as session:
            st = session.execute(select(ConnectedStore).where(ConnectedStore.id == store_id)).scalar_one_or_none()
            if st and st.access_token_encrypted:
                try:
                    sync_service = ShopifySynchronizer(session, st)
                    sync_service.sync_all(order_days=60)
                except Exception as e:
                    logger.exception("Background initial sync failed for %s: %s", st.shop_domain, e)

    background_tasks.add_task(run_initial_sync, store.id)

    # 7. Redirect to frontend dashboard
    redirect_url = f"{settings.FRONTEND_URL}/integrations?connected=true&shop={normalized_shop}"
    return RedirectResponse(url=redirect_url)


# ── Store Status & Sync Controls ──────────────────────────────────────────────

@router.get("/status", response_model=ShopifyStoreStatusResponse)
def get_store_status(
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> ShopifyStoreStatusResponse:
    """Get active connected store details, sync status, and recent synchronization logs."""
    logs_stmt = (
        select(SyncLog)
        .where(SyncLog.store_id == store.id)
        .order_by(SyncLog.started_at.desc())
        .limit(5)
    )
    logs = db.execute(logs_stmt).scalars().all()

    return ShopifyStoreStatusResponse(
        id=store.id,
        shop_domain=store.shop_domain,
        is_active=store.is_active,
        platform=store.platform,
        scopes=store.scopes,
        sync_status=store.sync_status,
        last_sync_at=store.last_sync_at,
        last_sync_error=store.last_sync_error,
        data_source=store.data_source,
        installed_at=store.installed_at,
        recent_sync_logs=[SyncLogResponse.model_validate(l) for l in logs],
    )


@router.post("/sync", response_model=ShopifySyncResponse)
def trigger_manual_sync(
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> ShopifySyncResponse:
    """Manually trigger immediate catalog, inventory, and order synchronization."""
    if not store.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store has no active Shopify authorization. Please reconnect via OAuth.",
        )

    try:
        synchronizer = ShopifySynchronizer(db, store)
        result = synchronizer.sync_all(order_days=60)
        return ShopifySyncResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Shopify synchronization failed: {exc}",
        )


@router.post("/disconnect")
def disconnect_store(
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Disconnect active Shopify store, revoking and clearing stored credentials."""
    store.is_active = False
    store.access_token_encrypted = None
    store.uninstalled_at = datetime.now(timezone.utc)
    store.sync_status = "idle"
    db.commit()

    return {"status": "disconnected", "shop_domain": store.shop_domain}


# ── Webhooks Ingestion ─────────────────────────────────────────────────────────

@router.post("/webhooks")
async def handle_shopify_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_shopify_hmac_sha256: Annotated[Optional[str], Header()] = None,
    x_shopify_topic: Annotated[Optional[str], Header()] = None,
    x_shopify_shop_domain: Annotated[Optional[str], Header()] = None,
    x_shopify_webhook_id: Annotated[Optional[str], Header()] = None,
):
    """Secure endpoint for all Shopify webhook event subscriptions."""
    raw_body = await request.body()

    # 1. Validate signature using raw body
    if not x_shopify_hmac_sha256 or not verify_shopify_webhook_hmac(
        raw_body, x_shopify_hmac_sha256, settings.SHOPIFY_API_SECRET
    ):
        logger.warning("Webhook HMAC signature validation failed from %s", x_shopify_shop_domain)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Shopify webhook HMAC signature",
        )

    if not x_shopify_topic or not x_shopify_shop_domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required webhook headers")

    webhook_id = x_shopify_webhook_id or str(uuid.uuid4())

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}

    result = ShopifyWebhookManager.process_webhook(
        db=db,
        topic=x_shopify_topic,
        shop=x_shopify_shop_domain,
        webhook_id=webhook_id,
        payload=payload,
    )
    return result


# ── Mandatory Compliance Webhooks (GDPR / Privacy) ────────────────────────────

@router.post("/compliance/customers/data_request")
async def compliance_customer_data_request(
    request: Request,
    x_shopify_hmac_sha256: Annotated[Optional[str], Header()] = None,
):
    """Mandatory compliance webhook: customers/data_request."""
    raw_body = await request.body()
    if not x_shopify_hmac_sha256 or not verify_shopify_webhook_hmac(
        raw_body, x_shopify_hmac_sha256, settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")
    logger.info("Compliance webhook: customers/data_request received (FunnelLeak stores no customer PII)")
    return {"status": "ok", "message": "No customer PII stored"}


@router.post("/compliance/customers/redact")
async def compliance_customer_redact(
    request: Request,
    x_shopify_hmac_sha256: Annotated[Optional[str], Header()] = None,
):
    """Mandatory compliance webhook: customers/redact."""
    raw_body = await request.body()
    if not x_shopify_hmac_sha256 or not verify_shopify_webhook_hmac(
        raw_body, x_shopify_hmac_sha256, settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")
    logger.info("Compliance webhook: customers/redact received (FunnelLeak stores no customer PII)")
    return {"status": "ok", "message": "No customer PII stored"}


@router.post("/compliance/shop/redact")
async def compliance_shop_redact(
    request: Request,
    db: Session = Depends(get_db),
    x_shopify_hmac_sha256: Annotated[Optional[str], Header()] = None,
    x_shopify_shop_domain: Annotated[Optional[str], Header()] = None,
):
    """Mandatory compliance webhook: shop/redact (erases store credentials upon uninstall)."""
    raw_body = await request.body()
    if not x_shopify_hmac_sha256 or not verify_shopify_webhook_hmac(
        raw_body, x_shopify_hmac_sha256, settings.SHOPIFY_API_SECRET
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")

    shop = x_shopify_shop_domain
    if shop:
        store = db.execute(
            select(ConnectedStore).where(ConnectedStore.shop_domain == shop.strip().lower())
        ).scalar_one_or_none()
        if store:
            store.is_active = False
            store.access_token_encrypted = None
            store.uninstalled_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Compliance webhook: shop/redact scrubbed credentials for %s", shop)

    return {"status": "ok"}
