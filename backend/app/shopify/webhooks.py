"""Shopify Webhook registration, signature verification, and idempotent processing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.models.store import ConnectedStore
from app.models.webhook import WebhookDelivery
from app.shopify.client import ShopifyGraphQLClient

logger = logging.getLogger(__name__)

# Topics to subscribe to for live store synchronization
WEBHOOK_TOPICS = [
    ("PRODUCTS_CREATE", "products/create"),
    ("PRODUCTS_UPDATE", "products/update"),
    ("PRODUCTS_DELETE", "products/delete"),
    ("ORDERS_CREATE", "orders/create"),
    ("ORDERS_UPDATED", "orders/updated"),
    ("ORDERS_CANCELLED", "orders/cancelled"),
    ("REFUNDS_CREATE", "refunds/create"),
    ("INVENTORY_LEVELS_UPDATE", "inventory_levels/update"),
    ("APP_UNINSTALLED", "app/uninstalled"),
]

WEBHOOK_CREATE_MUTATION = """
mutation WebhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    userErrors {
      field
      message
    }
    webhookSubscription {
      id
      topic
      endpoint {
        __typename
        ... on WebhookHttpEndpoint {
          callbackUrl
        }
      }
    }
  }
}
"""


class ShopifyWebhookManager:
    """Manages Shopify webhook registrations and handles incoming event processing."""

    @classmethod
    def register_all_webhooks(cls, client: ShopifyGraphQLClient, callback_url: str) -> List[str]:
        """Subscribe to all necessary event topics using Shopify GraphQL mutation."""
        registered: List[str] = []
        for graphql_topic, readable_topic in WEBHOOK_TOPICS:
            try:
                variables = {
                    "topic": graphql_topic,
                    "webhookSubscription": {
                        "callbackUrl": callback_url,
                        "format": "JSON",
                    },
                }
                res = client.execute(WEBHOOK_CREATE_MUTATION, variables)
                sub_data = res.get("webhookSubscriptionCreate", {})
                user_errors = sub_data.get("userErrors", [])
                if user_errors:
                    logger.warning(
                        "Shopify webhook subscription for %s on %s reported errors: %s",
                        graphql_topic, client.shop_domain, user_errors,
                    )
                else:
                    registered.append(readable_topic)
            except Exception as exc:
                logger.warning(
                    "Failed to register webhook %s on %s: %s",
                    graphql_topic, client.shop_domain, exc,
                )
        return registered

    @classmethod
    def process_webhook(
        cls,
        db: Session,
        topic: str,
        shop: str,
        webhook_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Idempotently process an incoming Shopify webhook."""
        # 1. Deduplication check using X-Shopify-Webhook-Id
        existing_stmt = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
        if db.execute(existing_stmt).scalar_one_or_none():
            logger.info("Ignoring duplicate webhook delivery %s for %s (%s)", webhook_id, shop, topic)
            return {"status": "ignored", "reason": "duplicate_webhook"}

        # 2. Resolve store by shop domain
        store_stmt = select(ConnectedStore).where(
            ConnectedStore.shop_domain == shop.lower().strip()
        )
        store = db.execute(store_stmt).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        normalized_topic = topic.lower().strip()

        # Record delivery log
        delivery = WebhookDelivery(
            store_id=store.id if store else None,
            webhook_id=webhook_id,
            topic=normalized_topic,
            shop_domain=shop,
            status="processed",
            received_at=now,
        )
        db.add(delivery)

        if not store:
            logger.warning("Received webhook for unknown shop %s; logged but not processed", shop)
            delivery.status = "ignored"
            delivery.error_message = "Store not found"
            db.commit()
            return {"status": "ignored", "reason": "store_not_found"}

        try:
            # 3. Dispatch to topic handler
            if normalized_topic in ("products/create", "products/update"):
                cls._handle_product_upsert(db, store, payload, now)

            elif normalized_topic == "products/delete":
                cls._handle_product_delete(db, store, payload)

            elif normalized_topic in ("orders/create", "orders/updated"):
                cls._handle_order_upsert(db, store, payload, now)

            elif normalized_topic == "orders/cancelled":
                cls._handle_order_cancelled(db, store, payload, now)

            elif normalized_topic == "refunds/create":
                cls._handle_refund_create(db, store, payload, now)

            elif normalized_topic == "inventory_levels/update":
                cls._handle_inventory_update(db, store, payload, now)

            elif normalized_topic == "app/uninstalled":
                cls._handle_app_uninstalled(db, store, now)

            elif normalized_topic in ("customers/data_request", "customers/redact"):
                # Compliance webhooks: FunnelLeak does not store customer PII
                logger.info("Processed compliance webhook %s for %s (no PII stored)", normalized_topic, shop)

            elif normalized_topic == "shop/redact":
                # Compliance webhook: store uninstall cleanup
                cls._handle_app_uninstalled(db, store, now)

            db.commit()
            return {"status": "success", "topic": normalized_topic}

        except Exception as exc:
            logger.exception("Error processing webhook %s on %s", normalized_topic, shop)
            delivery.status = "failed"
            delivery.error_message = str(exc)
            db.commit()
            raise

    # ── Private Topic Handlers ────────────────────────────────────────────────

    @classmethod
    def _handle_product_upsert(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
        now: datetime,
    ) -> None:
        raw_id = payload.get("id")
        if not raw_id:
            return
        shopify_id = f"gid://shopify/Product/{raw_id}" if not str(raw_id).startswith("gid://") else str(raw_id)
        title = payload.get("title") or "Untitled Product"
        handle = payload.get("handle")
        description = payload.get("body_html")
        product_type = payload.get("product_type")
        vendor = payload.get("vendor")
        status = (payload.get("status") or "active").lower()

        images = payload.get("images") or []
        image_url = images[0].get("src") if images else None

        variants = payload.get("variants") or []
        primary_price = None
        if variants and variants[0].get("price"):
            try:
                primary_price = Decimal(str(variants[0]["price"]))
            except (ValueError, TypeError):
                pass

        # Look up existing product
        stmt = select(Product).where(
            Product.store_id == store.id,
            Product.shopify_product_id == shopify_id,
        )
        product = db.execute(stmt).scalar_one_or_none()

        if product:
            product.title = title
            product.handle = handle
            product.description = description
            product.product_type = product_type
            product.vendor = vendor
            product.status = status
            product.data_source = "shopify"
            if primary_price is not None:
                product.price = primary_price
            if image_url:
                product.image_url = image_url
            product.synced_at = now
            # CRITICAL: Preserve manual COGS! If cost_source == 'manual', leave unit_cost intact.
        else:
            product = Product(
                store_id=store.id,
                shopify_product_id=shopify_id,
                title=title,
                handle=handle,
                description=description,
                product_type=product_type,
                vendor=vendor,
                status=status,
                data_source="shopify",
                price=primary_price or Decimal("0.00"),
                image_url=image_url,
                synced_at=now,
            )
            db.add(product)
            db.flush()

        # Upsert variants
        for v in variants:
            v_raw_id = v.get("id")
            if not v_raw_id:
                continue
            v_shopify_id = f"gid://shopify/ProductVariant/{v_raw_id}" if not str(v_raw_id).startswith("gid://") else str(v_raw_id)
            v_title = v.get("title") or "Default Title"
            v_sku = v.get("sku")
            v_barcode = v.get("barcode")
            v_qty = int(v.get("inventory_quantity") or 0)
            inv_item_id = str(v.get("inventory_item_id")) if v.get("inventory_item_id") else None

            v_price = None
            if v.get("price"):
                try:
                    v_price = Decimal(str(v["price"]))
                except (ValueError, TypeError):
                    pass

            v_stmt = select(ProductVariant).where(
                ProductVariant.product_id == product.id,
                ProductVariant.shopify_variant_id == v_shopify_id,
            )
            variant = db.execute(v_stmt).scalar_one_or_none()

            if variant:
                variant.title = v_title
                variant.sku = v_sku
                variant.barcode = v_barcode
                if inv_item_id:
                    variant.inventory_item_id = inv_item_id
                variant.inventory_quantity = v_qty
                variant.available = v_qty > 0
                if v_price is not None:
                    variant.price = v_price
                variant.synced_at = now
            else:
                variant = ProductVariant(
                    product_id=product.id,
                    shopify_variant_id=v_shopify_id,
                    title=v_title,
                    sku=v_sku,
                    barcode=v_barcode,
                    inventory_item_id=inv_item_id,
                    price=v_price or product.price,
                    unit_cost=product.unit_cost,
                    inventory_quantity=v_qty,
                    available=v_qty > 0,
                    synced_at=now,
                )
                db.add(variant)

    @classmethod
    def _handle_product_delete(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
    ) -> None:
        raw_id = payload.get("id")
        if not raw_id:
            return
        shopify_id = f"gid://shopify/Product/{raw_id}" if not str(raw_id).startswith("gid://") else str(raw_id)
        stmt = select(Product).where(
            Product.store_id == store.id,
            Product.shopify_product_id == shopify_id,
        )
        product = db.execute(stmt).scalar_one_or_none()
        if product:
            product.status = "archived"

    @classmethod
    def _handle_order_upsert(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
        now: datetime,
    ) -> None:
        raw_id = payload.get("id")
        if not raw_id:
            return
        shopify_id = f"gid://shopify/Order/{raw_id}" if not str(raw_id).startswith("gid://") else str(raw_id)
        order_number = str(payload.get("name") or payload.get("order_number") or "")
        created_at_raw = payload.get("created_at")
        order_date = (
            datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            if created_at_raw
            else now
        )

        financial_status = (payload.get("financial_status") or "paid").lower()
        fulfillment_status = (payload.get("fulfillment_status") or "unfulfilled").lower()
        currency = payload.get("currency") or "USD"
        is_test = bool(payload.get("test", False))

        cancelled_at_raw = payload.get("cancelled_at")
        cancelled_at = (
            datetime.fromisoformat(cancelled_at_raw.replace("Z", "+00:00"))
            if cancelled_at_raw
            else None
        )
        cancel_reason = payload.get("cancel_reason")

        total_price = Decimal(str(payload.get("total_price") or "0.00"))
        subtotal_price = Decimal(str(payload.get("subtotal_price") or "0.00"))
        total_discounts = Decimal(str(payload.get("total_discounts") or "0.00"))
        total_tax = Decimal(str(payload.get("total_tax") or "0.00"))
        total_shipping = Decimal("0.00")
        for line in payload.get("shipping_lines") or []:
            try:
                total_shipping += Decimal(str(line.get("price") or "0.00"))
            except (ValueError, TypeError):
                pass

        total_refunded = Decimal("0.00")
        for ref in payload.get("refunds") or []:
            for trans in ref.get("transactions") or []:
                try:
                    total_refunded += Decimal(str(trans.get("amount") or "0.00"))
                except (ValueError, TypeError):
                    pass

        line_items = payload.get("line_items") or []
        item_count = sum(int(item.get("quantity") or 0) for item in line_items)

        # Check existing order
        stmt = select(Order).where(
            Order.store_id == store.id,
            Order.shopify_order_id == shopify_id,
        )
        order = db.execute(stmt).scalar_one_or_none()

        if order:
            order.order_number = order_number
            order.total_price = total_price
            order.subtotal_price = subtotal_price
            order.total_discounts = total_discounts
            order.total_tax = total_tax
            order.total_shipping = total_shipping
            order.total_refunded = total_refunded
            order.financial_status = financial_status
            order.fulfillment_status = fulfillment_status
            order.item_count = item_count
            order.currency = currency
            order.is_test = is_test
            order.cancelled_at = cancelled_at
            order.cancel_reason = cancel_reason
            order.synced_at = now
        else:
            order = Order(
                store_id=store.id,
                shopify_order_id=shopify_id,
                order_number=order_number,
                total_price=total_price,
                subtotal_price=subtotal_price,
                total_discounts=total_discounts,
                total_tax=total_tax,
                total_shipping=total_shipping,
                total_refunded=total_refunded,
                financial_status=financial_status,
                fulfillment_status=fulfillment_status,
                item_count=item_count,
                currency=currency,
                is_test=is_test,
                data_source="shopify",
                cancelled_at=cancelled_at,
                cancel_reason=cancel_reason,
                order_date=order_date,
                synced_at=now,
            )
            db.add(order)
            db.flush()

        # Update line items
        if order.items:
            for old in order.items:
                db.delete(old)
            db.flush()

        for item in line_items:
            line_raw_id = item.get("id")
            line_prod_raw = item.get("product_id")
            line_var_raw = item.get("variant_id")

            line_prod_id = f"gid://shopify/Product/{line_prod_raw}" if line_prod_raw else None
            line_var_id = f"gid://shopify/ProductVariant/{line_var_raw}" if line_var_raw else None

            matched_prod = None
            if line_prod_id:
                matched_prod = db.execute(
                    select(Product).where(Product.store_id == store.id, Product.shopify_product_id == line_prod_id)
                ).scalar_one_or_none()

            matched_var = None
            if line_var_id:
                matched_var = db.execute(
                    select(ProductVariant).where(ProductVariant.shopify_variant_id == line_var_id)
                ).scalar_one_or_none()

            line_price = Decimal(str(item.get("price") or "0.00"))
            line_disc = Decimal(str(item.get("total_discount") or "0.00"))

            order_item = OrderItem(
                order_id=order.id,
                product_id=matched_prod.id if matched_prod else None,
                variant_id=matched_var.id if matched_var else None,
                shopify_product_id=line_prod_id,
                shopify_line_item_id=str(line_raw_id) if line_raw_id else None,
                sku=item.get("sku"),
                title=item.get("title") or "Item",
                quantity=int(item.get("quantity") or 1),
                price=line_price,
                total_discount=line_disc,
            )
            db.add(order_item)

    @classmethod
    def _handle_order_cancelled(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
        now: datetime,
    ) -> None:
        raw_id = payload.get("id")
        if not raw_id:
            return
        shopify_id = f"gid://shopify/Order/{raw_id}" if not str(raw_id).startswith("gid://") else str(raw_id)
        stmt = select(Order).where(Order.store_id == store.id, Order.shopify_order_id == shopify_id)
        order = db.execute(stmt).scalar_one_or_none()
        if order:
            order.cancelled_at = now
            order.cancel_reason = payload.get("cancel_reason") or "customer"
            order.financial_status = "voided"

    @classmethod
    def _handle_refund_create(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
        now: datetime,
    ) -> None:
        raw_order_id = payload.get("order_id")
        if not raw_order_id:
            return
        shopify_order_id = f"gid://shopify/Order/{raw_order_id}" if not str(raw_order_id).startswith("gid://") else str(raw_order_id)
        stmt = select(Order).where(Order.store_id == store.id, Order.shopify_order_id == shopify_order_id)
        order = db.execute(stmt).scalar_one_or_none()
        if order:
            refund_amount = Decimal("0.00")
            for trans in payload.get("transactions") or []:
                try:
                    refund_amount += Decimal(str(trans.get("amount") or "0.00"))
                except (ValueError, TypeError):
                    pass
            order.total_refunded += refund_amount
            if order.total_refunded >= order.total_price:
                order.financial_status = "refunded"
            else:
                order.financial_status = "partially_refunded"

    @classmethod
    def _handle_inventory_update(
        cls,
        db: Session,
        store: ConnectedStore,
        payload: Dict[str, Any],
        now: datetime,
    ) -> None:
        inv_item_id = str(payload.get("inventory_item_id")) if payload.get("inventory_item_id") else None
        available = payload.get("available")
        if not inv_item_id or available is None:
            return

        stmt = (
            select(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(
                Product.store_id == store.id,
                ProductVariant.inventory_item_id == inv_item_id,
            )
        )
        variant = db.execute(stmt).scalar_one_or_none()
        if variant:
            qty = int(available)
            variant.inventory_quantity = qty
            variant.available = qty > 0

    @classmethod
    def _handle_app_uninstalled(
        cls,
        db: Session,
        store: ConnectedStore,
        now: datetime,
    ) -> None:
        logger.info("Handling app/uninstalled for shop %s", store.shop_domain)
        store.is_active = False
        store.access_token_encrypted = None
        store.uninstalled_at = now
        store.sync_status = "idle"
