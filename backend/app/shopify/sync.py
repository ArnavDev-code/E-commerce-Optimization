"""Shopify synchronization engine for products, inventory, and orders.

Core Guarantees:
- Pinned to Shopify GraphQL Admin API 2026-10.
- Preserves existing manual COGS without ever overwriting with null/zero.
- Minimal customer PII: no customer names, emails, addresses, or phone numbers.
- Accurate cancellation and refund accounting for revenue analytics.
- Full SyncLog tracking and store sync status updates.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.product import InventorySnapshot, Product, ProductVariant
from app.models.store import ConnectedStore
from app.models.sync import SyncLog
from app.shopify.client import ShopifyGraphQLClient
from app.utils.security import decrypt_token

logger = logging.getLogger(__name__)

# ── GraphQL Queries (Pinned to 2026-10) ────────────────────────────────────────

PRODUCTS_QUERY = """
query GetProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      id
      title
      handle
      description
      productType
      vendor
      status
      featuredImage {
        url
      }
      updatedAt
      variants(first: 100) {
        nodes {
          id
          title
          sku
          price
          compareAtPrice
          barcode
          inventoryQuantity
          inventoryItem {
            id
            unitCost {
              amount
            }
          }
        }
      }
    }
  }
}
"""

ORDERS_QUERY = """
query GetOrders($cursor: String, $query: String) {
  orders(first: 50, after: $cursor, query: $query, sortKey: CREATED_AT, reverse: true) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      id
      name
      createdAt
      displayFinancialStatus
      displayFulfillmentStatus
      cancelledAt
      cancelReason
      currencyCode
      test
      totalPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
      subtotalPriceSet {
        shopMoney {
          amount
        }
      }
      totalDiscountsSet {
        shopMoney {
          amount
        }
      }
      totalTaxSet {
        shopMoney {
          amount
        }
      }
      totalShippingPriceSet {
        shopMoney {
          amount
        }
      }
      totalRefundedSet {
        shopMoney {
          amount
        }
      }
      lineItems(first: 100) {
        nodes {
          id
          title
          quantity
          originalUnitPriceSet {
            shopMoney {
              amount
            }
          }
          totalDiscountSet {
            shopMoney {
              amount
            }
          }
          product {
            id
          }
          variant {
            id
            sku
          }
        }
      }
    }
  }
}
"""

INVENTORY_QUERY = """
query GetInventoryLocations($cursor: String) {
  locations(first: 20) {
    nodes {
      id
      name
      isActive
      inventoryLevels(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          updatedAt
          quantities(names: ["available"]) {
            name
            quantity
          }
          item {
            id
            variant {
              id
            }
          }
        }
      }
    }
  }
}
"""


class ShopifySynchronizer:
    """Manages ingestion and synchronization of live merchant store data."""

    def __init__(self, db: Session, store: ConnectedStore, client: Optional[ShopifyGraphQLClient] = None):
        self.db = db
        self.store = store
        if client:
            self.client = client
        else:
            if not store.access_token_encrypted:
                raise ValueError(f"Store {store.shop_domain} has no stored access token")
            decrypted_token = decrypt_token(store.access_token_encrypted)
            self.client = ShopifyGraphQLClient(store.shop_domain, decrypted_token)

    def sync_all(self, order_days: int = 60) -> Dict[str, Any]:
        """Perform full synchronization: products, inventory, and orders."""
        now = datetime.now(timezone.utc)
        self.store.sync_status = "syncing"
        self.db.commit()

        sync_log = SyncLog(
            store_id=self.store.id,
            sync_type="full_shopify_sync",
            status="started",
            started_at=now,
        )
        self.db.add(sync_log)
        self.db.commit()

        try:
            products_count = self.sync_products()
            inventory_count = self.sync_inventory()
            orders_count = self.sync_orders(days=order_days)

            total_records = products_count + inventory_count + orders_count

            self.store.sync_status = "success"
            self.store.last_sync_at = datetime.now(timezone.utc)
            self.store.last_sync_error = None
            self.store.data_source = "shopify"

            sync_log.status = "completed"
            sync_log.records_synced = total_records
            sync_log.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return {
                "status": "success",
                "products_synced": products_count,
                "inventory_levels_synced": inventory_count,
                "orders_synced": orders_count,
                "total_records": total_records,
                "synced_at": self.store.last_sync_at.isoformat(),
            }

        except Exception as exc:
            logger.exception("Shopify synchronization failed for %s", self.store.shop_domain)
            error_msg = str(exc)
            self.store.sync_status = "failed"
            self.store.last_sync_error = error_msg

            sync_log.status = "failed"
            sync_log.error_message = error_msg
            sync_log.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            raise

    def sync_products(self) -> int:
        """Fetch and upsert all products and variants from Shopify GraphQL, preserving manual COGS."""
        cursor: Optional[str] = None
        has_next = True
        synced_count = 0
        now = datetime.now(timezone.utc)

        while has_next:
            data = self.client.execute(PRODUCTS_QUERY, {"cursor": cursor})
            products_data = data.get("products", {})
            nodes = products_data.get("nodes", [])
            page_info = products_data.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            for node in nodes:
                shopify_id = str(node["id"])
                title = node.get("title") or "Untitled Product"
                handle = node.get("handle")
                description = node.get("description")
                product_type = node.get("productType")
                vendor = node.get("vendor")
                raw_status = (node.get("status") or "ACTIVE").lower()
                image_url = node.get("featuredImage", {}).get("url") if node.get("featuredImage") else None

                # Find or create Product
                stmt = select(Product).where(
                    Product.store_id == self.store.id,
                    Product.shopify_product_id == shopify_id,
                )
                product = self.db.execute(stmt).scalar_one_or_none()

                # Process variants and extract COGS
                variants_nodes = node.get("variants", {}).get("nodes", [])
                primary_price: Optional[Decimal] = None
                primary_compare: Optional[Decimal] = None
                shopify_cogs: Optional[Decimal] = None

                for v_node in variants_nodes:
                    if v_node.get("price") is not None and primary_price is None:
                        try:
                            primary_price = Decimal(str(v_node["price"]))
                        except (ValueError, TypeError):
                            pass
                    if v_node.get("compareAtPrice") is not None and primary_compare is None:
                        try:
                            primary_compare = Decimal(str(v_node["compareAtPrice"]))
                        except (ValueError, TypeError):
                            pass

                    # Extract unit cost if available
                    inv_item = v_node.get("inventoryItem") or {}
                    unit_cost_info = inv_item.get("unitCost") or {}
                    if unit_cost_info.get("amount") is not None and shopify_cogs is None:
                        try:
                            val = Decimal(str(unit_cost_info["amount"]))
                            if val > 0:
                                shopify_cogs = val
                        except (ValueError, TypeError):
                            pass

                # ── CRITICAL COGS PRESERVATION RULE ───────────────────────────
                # Never wipe out or overwrite merchant-entered manual COGS!
                if product:
                    if product.cost_source == "manual" and product.unit_cost is not None:
                        # Retain manual merchant COGS
                        final_unit_cost = product.unit_cost
                        final_cost_source = "manual"
                    elif shopify_cogs is not None and shopify_cogs > 0:
                        final_unit_cost = shopify_cogs
                        final_cost_source = "shopify"
                    elif product.unit_cost is not None:
                        # Retain existing cost rather than setting to null/zero
                        final_unit_cost = product.unit_cost
                        final_cost_source = product.cost_source
                    else:
                        final_unit_cost = None
                        final_cost_source = None
                else:
                    final_unit_cost = shopify_cogs
                    final_cost_source = "shopify" if shopify_cogs is not None else None

                if product:
                    product.title = title
                    product.handle = handle
                    product.description = description
                    product.product_type = product_type
                    product.vendor = vendor
                    product.status = raw_status
                    product.data_source = "shopify"
                    if primary_price is not None:
                        product.price = primary_price
                    if primary_compare is not None:
                        product.compare_at_price = primary_compare
                    product.unit_cost = final_unit_cost
                    product.cost_source = final_cost_source
                    if image_url:
                        product.image_url = image_url
                    product.synced_at = now
                else:
                    product = Product(
                        store_id=self.store.id,
                        shopify_product_id=shopify_id,
                        title=title,
                        handle=handle,
                        description=description,
                        product_type=product_type,
                        vendor=vendor,
                        status=raw_status,
                        data_source="shopify",
                        price=primary_price or Decimal("0.00"),
                        compare_at_price=primary_compare,
                        unit_cost=final_unit_cost,
                        cost_source=final_cost_source,
                        image_url=image_url,
                        synced_at=now,
                    )
                    self.db.add(product)
                    self.db.flush()

                # Upsert Variants
                for v_node in variants_nodes:
                    v_shopify_id = str(v_node["id"])
                    v_title = v_node.get("title") or "Default Title"
                    v_sku = v_node.get("sku")
                    v_barcode = v_node.get("barcode")
                    v_inv_qty = int(v_node.get("inventoryQuantity") or 0)
                    inv_item_id = str(v_node.get("inventoryItem", {}).get("id")) if v_node.get("inventoryItem") else None

                    v_price = None
                    if v_node.get("price") is not None:
                        try:
                            v_price = Decimal(str(v_node["price"]))
                        except (ValueError, TypeError):
                            pass

                    # Look up existing variant
                    v_stmt = select(ProductVariant).where(
                        ProductVariant.product_id == product.id,
                        ProductVariant.shopify_variant_id == v_shopify_id,
                    )
                    variant = self.db.execute(v_stmt).scalar_one_or_none()

                    if variant:
                        variant.title = v_title
                        variant.sku = v_sku
                        variant.barcode = v_barcode
                        variant.inventory_item_id = inv_item_id
                        variant.inventory_quantity = v_inv_qty
                        variant.available = v_inv_qty > 0
                        if v_price is not None:
                            variant.price = v_price
                        variant.unit_cost = final_unit_cost
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
                            unit_cost=final_unit_cost,
                            inventory_quantity=v_inv_qty,
                            available=v_inv_qty > 0,
                            synced_at=now,
                        )
                        self.db.add(variant)

                synced_count += 1

            self.db.commit()

        return synced_count

    def sync_inventory(self) -> int:
        """Fetch inventory levels across locations and record snapshots."""
        cursor: Optional[str] = None
        has_next = True
        snapshot_count = 0
        now = datetime.now(timezone.utc)
        today = date.today()

        while has_next:
            data = self.client.execute(INVENTORY_QUERY, {"cursor": cursor})
            locations_data = data.get("locations", {})
            nodes = locations_data.get("nodes", [])

            for loc in nodes:
                loc_id = str(loc["id"])
                inv_levels = loc.get("inventoryLevels", {})
                inv_nodes = inv_levels.get("nodes", [])
                page_info = inv_levels.get("pageInfo", {})
                has_next = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

                for level_node in inv_nodes:
                    quantities = level_node.get("quantities", [])
                    available_qty = 0
                    for q in quantities:
                        if q.get("name") == "available":
                            available_qty = int(q.get("quantity") or 0)
                            break

                    item_data = level_node.get("item") or {}
                    variant_data = item_data.get("variant") or {}
                    shopify_variant_id = variant_data.get("id")

                    if not shopify_variant_id:
                        continue

                    # Find variant
                    v_stmt = (
                        select(ProductVariant)
                        .join(Product, Product.id == ProductVariant.product_id)
                        .where(
                            Product.store_id == self.store.id,
                            ProductVariant.shopify_variant_id == str(shopify_variant_id),
                        )
                    )
                    variant = self.db.execute(v_stmt).scalar_one_or_none()
                    if variant:
                        variant.inventory_quantity = available_qty
                        variant.available = available_qty > 0

                        # Record snapshot
                        snapshot = InventorySnapshot(
                            variant_id=variant.id,
                            location_id=loc_id,
                            quantity=available_qty,
                            snapshot_date=today,
                            synced_at=now,
                        )
                        self.db.add(snapshot)
                        snapshot_count += 1

            self.db.commit()
            if not nodes:
                break

        return snapshot_count

    def sync_orders(self, days: int = 60) -> int:
        """Fetch orders within the specified lookback window and map to Order & OrderItems."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        query_str = f"created_at:>='{cutoff_date}'"

        cursor: Optional[str] = None
        has_next = True
        synced_count = 0
        now = datetime.now(timezone.utc)

        # Pre-cache products and variants for this store to avoid N+1 queries
        products_cache = {
            p.shopify_product_id: p
            for p in self.db.query(Product).filter(Product.store_id == self.store.id).all()
            if p.shopify_product_id
        }
        variants_cache = {
            v.shopify_variant_id: v
            for v in self.db.query(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .filter(Product.store_id == self.store.id)
            .all()
            if v.shopify_variant_id
        }

        while has_next:
            data = self.client.execute(ORDERS_QUERY, {"cursor": cursor, "query": query_str})
            orders_data = data.get("orders", {})
            nodes = orders_data.get("nodes", [])
            page_info = orders_data.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            for node in nodes:
                shopify_id = str(node["id"])
                order_name = node.get("name")
                created_at_raw = node.get("createdAt")
                created_at = (
                    datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                    if created_at_raw
                    else now
                )

                financial_status = (node.get("displayFinancialStatus") or "paid").lower()
                fulfillment_status = (node.get("displayFulfillmentStatus") or "unfulfilled").lower()
                is_test = bool(node.get("test", False))
                currency = node.get("currencyCode") or "USD"

                cancelled_at_raw = node.get("cancelledAt")
                cancelled_at = (
                    datetime.fromisoformat(cancelled_at_raw.replace("Z", "+00:00"))
                    if cancelled_at_raw
                    else None
                )
                cancel_reason = node.get("cancelReason")

                # Amounts
                total_price = Decimal(str(node.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                subtotal_price = Decimal(str(node.get("subtotalPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                total_discounts = Decimal(str(node.get("totalDiscountsSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                total_tax = Decimal(str(node.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                total_shipping = Decimal(str(node.get("totalShippingPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                total_refunded = Decimal(str(node.get("totalRefundedSet", {}).get("shopMoney", {}).get("amount", "0.00")))

                line_nodes = node.get("lineItems", {}).get("nodes", [])
                item_count = sum(int(item.get("quantity") or 0) for item in line_nodes)

                # Check existing order
                ord_stmt = select(Order).where(
                    Order.store_id == self.store.id,
                    Order.shopify_order_id == shopify_id,
                )
                order = self.db.execute(ord_stmt).scalar_one_or_none()

                if order:
                    order.order_number = order_name
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
                        store_id=self.store.id,
                        shopify_order_id=shopify_id,
                        order_number=order_name,
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
                        order_date=created_at,
                        synced_at=now,
                    )
                    self.db.add(order)
                    self.db.flush()

                # Process line items (clear and recreate or update)
                # For clean sync, remove previous line items if order existed
                if order.items:
                    for old_item in order.items:
                        self.db.delete(old_item)
                    self.db.flush()

                for line in line_nodes:
                    line_shopify_id = str(line["id"])
                    line_title = line.get("title") or "Item"
                    line_qty = int(line.get("quantity") or 1)
                    line_price = Decimal(str(line.get("originalUnitPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")))
                    line_disc = Decimal(str(line.get("totalDiscountSet", {}).get("shopMoney", {}).get("amount", "0.00")))

                    prod_obj = line.get("product") or {}
                    var_obj = line.get("variant") or {}

                    line_prod_shopify_id = str(prod_obj.get("id")) if prod_obj.get("id") else None
                    line_var_shopify_id = str(var_obj.get("id")) if var_obj.get("id") else None
                    line_sku = var_obj.get("sku")

                    matched_prod = products_cache.get(line_prod_shopify_id) if line_prod_shopify_id else None
                    matched_var = variants_cache.get(line_var_shopify_id) if line_var_shopify_id else None

                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=matched_prod.id if matched_prod else None,
                        variant_id=matched_var.id if matched_var else None,
                        shopify_product_id=line_prod_shopify_id,
                        shopify_line_item_id=line_shopify_id,
                        sku=line_sku,
                        title=line_title,
                        quantity=line_qty,
                        price=line_price,
                        total_discount=line_disc,
                    )
                    self.db.add(order_item)

                synced_count += 1

            self.db.commit()

        return synced_count
