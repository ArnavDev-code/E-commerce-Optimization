"""Tests for Shopify webhook HMAC verification, deduplication, and topic processing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.product import Product, ProductVariant
from app.models.store import ConnectedStore
from app.models.webhook import WebhookDelivery
from app.shopify.webhooks import ShopifyWebhookManager
from app.utils.security import encrypt_token, verify_shopify_webhook_hmac

settings = get_settings()


def _compute_webhook_hmac(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def test_webhook_hmac_verification() -> None:
    """Verify incoming Shopify webhook HMAC-SHA256 signature verification."""
    secret = "secret-webhook-key-999"
    payload_bytes = json.dumps({"test": "data", "id": 12345}).encode("utf-8")

    valid_sig = _compute_webhook_hmac(payload_bytes, secret)
    assert verify_shopify_webhook_hmac(payload_bytes, valid_sig, secret) is True

    # Tampered body fails
    tampered_bytes = json.dumps({"test": "tampered", "id": 12345}).encode("utf-8")
    assert verify_shopify_webhook_hmac(tampered_bytes, valid_sig, secret) is False

    # Invalid secret fails
    assert verify_shopify_webhook_hmac(payload_bytes, valid_sig, "wrong-secret") is False


def test_webhook_idempotency_and_deduplication(db: Session) -> None:
    """Verify that multiple deliveries of the exact same webhook_id are processed only once."""
    merchant = Merchant(email=f"dedup_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="dedup-store.myshopify.com",
        access_token_encrypted=encrypt_token("tok"),
        is_active=True,
    )
    db.add(store)
    db.commit()

    webhook_id = f"wh_delivery_{uuid.uuid4().hex}"
    payload = {
        "id": 88001,
        "title": "Webhook Test Product",
        "variants": [{"id": 99001, "price": "35.00", "inventory_quantity": 10}],
    }

    # 1. First delivery -> Success
    res1 = ShopifyWebhookManager.process_webhook(
        db=db,
        topic="products/create",
        shop="dedup-store.myshopify.com",
        webhook_id=webhook_id,
        payload=payload,
    )
    assert res1["status"] == "success"

    # 2. Duplicate delivery with the same webhook_id -> Must be safely ignored
    res2 = ShopifyWebhookManager.process_webhook(
        db=db,
        topic="products/create",
        shop="dedup-store.myshopify.com",
        webhook_id=webhook_id,
        payload=payload,
    )
    assert res2["status"] == "ignored"
    assert res2["reason"] == "duplicate_webhook"

    # Verify only 1 product and 1 webhook log exist in DB
    prod_count = db.query(Product).filter(Product.shopify_product_id == "gid://shopify/Product/88001").count()
    assert prod_count == 1
    wh_count = db.query(WebhookDelivery).filter(WebhookDelivery.webhook_id == webhook_id).count()
    assert wh_count == 1


def test_product_update_webhook_preserves_manual_cogs(db: Session) -> None:
    """Verify products/update webhook updates product details while preserving merchant COGS."""
    merchant = Merchant(email=f"wh_prod_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="wh-prod.myshopify.com",
        access_token_encrypted=encrypt_token("tok"),
        is_active=True,
    )
    db.add(store)
    db.flush()

    # Pre-existing product with manual COGS
    prod = Product(
        store_id=store.id,
        shopify_product_id="gid://shopify/Product/77001",
        title="Old Product Title",
        price=Decimal("40.00"),
        unit_cost=Decimal("12.50"),
        cost_source="manual",  # Merchant explicitly set this!
        status="active",
    )
    db.add(prod)
    db.commit()

    # Incoming Shopify webhook with new title and new price
    payload = {
        "id": 77001,
        "title": "New Updated Title From Shopify",
        "handle": "new-updated-title",
        "variants": [
            {
                "id": 66001,
                "title": "Default",
                "price": "48.00",
                "inventory_quantity": 25,
            }
        ],
    }

    ShopifyWebhookManager.process_webhook(
        db=db,
        topic="products/update",
        shop="wh-prod.myshopify.com",
        webhook_id=f"wh_{uuid.uuid4().hex}",
        payload=payload,
    )

    db.refresh(prod)
    assert prod.title == "New Updated Title From Shopify"
    assert prod.price == Decimal("48.00")
    # Verify manual COGS was NOT lost:
    assert prod.unit_cost == Decimal("12.50")
    assert prod.cost_source == "manual"


def test_order_cancelled_and_refund_webhooks(db: Session) -> None:
    """Verify orders/cancelled and refunds/create update financial statuses accurately."""
    merchant = Merchant(email=f"wh_ord_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="wh-order.myshopify.com",
        access_token_encrypted=encrypt_token("tok"),
        is_active=True,
    )
    db.add(store)
    db.flush()

    order = Order(
        store_id=store.id,
        shopify_order_id="gid://shopify/Order/33001",
        order_number="#33001",
        total_price=Decimal("100.00"),
        subtotal_price=Decimal("100.00"),
        financial_status="paid",
        fulfillment_status="fulfilled",
        item_count=1,
        order_date=datetime.now(),
    )
    db.add(order)
    db.commit()

    # 1. Process refunds/create ($40 partial refund)
    refund_payload = {
        "order_id": 33001,
        "transactions": [{"amount": "40.00"}],
    }
    ShopifyWebhookManager.process_webhook(
        db=db,
        topic="refunds/create",
        shop="wh-order.myshopify.com",
        webhook_id=f"wh_{uuid.uuid4().hex}",
        payload=refund_payload,
    )

    db.refresh(order)
    assert order.total_refunded == Decimal("40.00")
    assert order.financial_status == "partially_refunded"

    # 2. Process orders/cancelled
    cancel_payload = {
        "id": 33001,
        "cancel_reason": "customer",
    }
    ShopifyWebhookManager.process_webhook(
        db=db,
        topic="orders/cancelled",
        shop="wh-order.myshopify.com",
        webhook_id=f"wh_{uuid.uuid4().hex}",
        payload=cancel_payload,
    )

    db.refresh(order)
    assert order.cancelled_at is not None
    assert order.financial_status == "voided"
    assert order.cancel_reason == "customer"


def test_app_uninstalled_webhook_revokes_store(db: Session) -> None:
    """Verify app/uninstalled invalidates stored credentials and marks store inactive."""
    merchant = Merchant(email=f"uninstall_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="uninstall-test.myshopify.com",
        access_token_encrypted=encrypt_token("offline_token_xyz"),
        is_active=True,
    )
    db.add(store)
    db.commit()

    ShopifyWebhookManager.process_webhook(
        db=db,
        topic="app/uninstalled",
        shop="uninstall-test.myshopify.com",
        webhook_id=f"wh_{uuid.uuid4().hex}",
        payload={},
    )

    db.refresh(store)
    assert store.is_active is False
    assert store.access_token_encrypted is None
    assert store.uninstalled_at is not None
