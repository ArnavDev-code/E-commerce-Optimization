"""Tests for Shopify GraphQL product, order, and inventory synchronization with manual COGS preservation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.order import Order, OrderItem
from app.models.product import InventorySnapshot, Product, ProductVariant
from app.models.store import ConnectedStore
from app.shopify.client import ShopifyApiError, ShopifyGraphQLClient
from app.shopify.sync import ShopifySynchronizer
from app.utils.security import encrypt_token


class MockGraphQLClient(ShopifyGraphQLClient):
    """Mock client returning deterministic Shopify GraphQL responses."""

    def __init__(self, mock_responses: Optional[Dict[str, Any]] = None):
        super().__init__("mock-store.myshopify.com", "mock_token")
        self.mock_responses = mock_responses or {}
        self.call_history: list = []

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> Dict[str, Any]:
        self.call_history.append({"query": query, "variables": variables})
        if "GetProducts" in query:
            return self.mock_responses.get("products", {"products": {"nodes": [], "pageInfo": {"hasNextPage": False}}})
        elif "GetOrders" in query:
            return self.mock_responses.get("orders", {"orders": {"nodes": [], "pageInfo": {"hasNextPage": False}}})
        elif "GetInventoryLocations" in query:
            return self.mock_responses.get("inventory", {"locations": {"nodes": []}})
        return {}


def test_product_sync_and_manual_cogs_preservation(db: Session) -> None:
    """Verify live Shopify products synchronize and merchant manual COGS are NEVER overwritten."""
    merchant = Merchant(email=f"cogs_test_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="cogs-boutique.myshopify.com",
        access_token_encrypted=encrypt_token("token123"),
        is_active=True,
    )
    db.add(store)
    db.commit()

    # Shopify returns 2 products:
    # Product 1: Botanical Face Cream ($45 selling price, $15.00 Shopify unit cost)
    # Product 2: Silk Sleep Mask ($28 selling price, NO Shopify unit cost)
    mock_products_data = {
        "products": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [
                {
                    "id": "gid://shopify/Product/1001",
                    "title": "Botanical Face Cream",
                    "handle": "botanical-face-cream",
                    "description": "Nourishing face cream",
                    "productType": "Skincare",
                    "vendor": "Glow Co",
                    "status": "ACTIVE",
                    "featuredImage": {"url": "https://example.com/cream.jpg"},
                    "variants": {
                        "nodes": [
                            {
                                "id": "gid://shopify/ProductVariant/2001",
                                "title": "50ml",
                                "sku": "BFC-50",
                                "price": "45.00",
                                "compareAtPrice": "55.00",
                                "inventoryQuantity": 120,
                                "inventoryItem": {
                                    "id": "gid://shopify/InventoryItem/3001",
                                    "unitCost": {"amount": "15.00"},
                                },
                            }
                        ]
                    },
                },
                {
                    "id": "gid://shopify/Product/1002",
                    "title": "Silk Sleep Mask",
                    "handle": "silk-sleep-mask",
                    "description": "Pure mulberry silk",
                    "productType": "Accessories",
                    "vendor": "Glow Co",
                    "status": "ACTIVE",
                    "featuredImage": {"url": "https://example.com/mask.jpg"},
                    "variants": {
                        "nodes": [
                            {
                                "id": "gid://shopify/ProductVariant/2002",
                                "title": "Default",
                                "sku": "SSM-BLK",
                                "price": "28.00",
                                "compareAtPrice": None,
                                "inventoryQuantity": 45,
                                "inventoryItem": {
                                    "id": "gid://shopify/InventoryItem/3002",
                                    "unitCost": None,  # No unit cost in Shopify!
                                },
                            }
                        ]
                    },
                },
            ],
        }
    }

    client = MockGraphQLClient({"products": mock_products_data})
    synchronizer = ShopifySynchronizer(db, store, client=client)

    # Initial sync
    count = synchronizer.sync_products()
    assert count == 2

    # Verify Product 1 received Shopify COGS
    p1 = db.query(Product).filter(Product.shopify_product_id == "gid://shopify/Product/1001").first()
    assert p1 is not None
    assert p1.unit_cost == Decimal("15.00")
    assert p1.cost_source == "shopify"
    assert p1.price == Decimal("45.00")

    # Verify Product 2 has None COGS (not zero!)
    p2 = db.query(Product).filter(Product.shopify_product_id == "gid://shopify/Product/1002").first()
    assert p2 is not None
    assert p2.unit_cost is None
    assert p2.cost_source is None

    # Merchant manually overrides COGS on Product 1 to $18.50 and sets Product 2 to $8.00
    p1.unit_cost = Decimal("18.50")
    p1.cost_source = "manual"
    p2.unit_cost = Decimal("8.00")
    p2.cost_source = "manual"
    db.commit()

    # Re-run sync (e.g. daily catalog update from Shopify)
    synchronizer.sync_products()

    # Verify CRITICAL REQUIREMENT: Manual COGS was PRESERVED!
    db.refresh(p1)
    db.refresh(p2)
    assert p1.unit_cost == Decimal("18.50"), "Manual COGS on Product 1 must not be overwritten by Shopify!"
    assert p1.cost_source == "manual"
    assert p2.unit_cost == Decimal("8.00"), "Manual COGS on Product 2 must be retained!"
    assert p2.cost_source == "manual"


def test_order_sync_and_cancellation_accounting(db: Session) -> None:
    """Verify live order synchronization computes totals accurately and marks cancellations."""
    merchant = Merchant(email=f"order_test_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="order-boutique.myshopify.com",
        access_token_encrypted=encrypt_token("token123"),
        is_active=True,
    )
    db.add(store)
    db.commit()

    mock_orders_data = {
        "orders": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [
                {
                    "id": "gid://shopify/Order/5001",
                    "name": "#1001",
                    "createdAt": "2026-11-20T14:30:00Z",
                    "displayFinancialStatus": "PAID",
                    "displayFulfillmentStatus": "FULFILLED",
                    "cancelledAt": None,
                    "cancelReason": None,
                    "currencyCode": "USD",
                    "test": False,
                    "totalPriceSet": {"shopMoney": {"amount": "95.00"}},
                    "subtotalPriceSet": {"shopMoney": {"amount": "85.00"}},
                    "totalDiscountsSet": {"shopMoney": {"amount": "5.00"}},
                    "totalTaxSet": {"shopMoney": {"amount": "5.00"}},
                    "totalShippingPriceSet": {"shopMoney": {"amount": "10.00"}},
                    "totalRefundedSet": {"shopMoney": {"amount": "0.00"}},
                    "lineItems": {
                        "nodes": [
                            {
                                "id": "gid://shopify/LineItem/6001",
                                "title": "Luminosity Eye Cream",
                                "quantity": 2,
                                "originalUnitPriceSet": {"shopMoney": {"amount": "45.00"}},
                                "totalDiscountSet": {"shopMoney": {"amount": "5.00"}},
                                "product": {"id": "gid://shopify/Product/1001"},
                                "variant": {"id": "gid://shopify/ProductVariant/2001", "sku": "LEC-15"},
                            }
                        ]
                    },
                },
                {
                    "id": "gid://shopify/Order/5002",
                    "name": "#1002",
                    "createdAt": "2026-11-21T10:00:00Z",
                    "displayFinancialStatus": "VOIDED",
                    "displayFulfillmentStatus": "RESTOCKED",
                    "cancelledAt": "2026-11-21T11:00:00Z",
                    "cancelReason": "CUSTOMER",
                    "currencyCode": "USD",
                    "test": False,
                    "totalPriceSet": {"shopMoney": {"amount": "45.00"}},
                    "subtotalPriceSet": {"shopMoney": {"amount": "45.00"}},
                    "totalDiscountsSet": {"shopMoney": {"amount": "0.00"}},
                    "totalTaxSet": {"shopMoney": {"amount": "0.00"}},
                    "totalShippingPriceSet": {"shopMoney": {"amount": "0.00"}},
                    "totalRefundedSet": {"shopMoney": {"amount": "45.00"}},
                    "lineItems": {
                        "nodes": [
                            {
                                "id": "gid://shopify/LineItem/6002",
                                "title": "Silk Headband",
                                "quantity": 1,
                                "originalUnitPriceSet": {"shopMoney": {"amount": "45.00"}},
                                "totalDiscountSet": {"shopMoney": {"amount": "0.00"}},
                                "product": None,
                                "variant": None,
                            }
                        ]
                    },
                },
            ],
        }
    }

    client = MockGraphQLClient({"orders": mock_orders_data})
    synchronizer = ShopifySynchronizer(db, store, client=client)

    orders_count = synchronizer.sync_orders(days=30)
    assert orders_count == 2

    # Verify Order 1 (Paid)
    ord1 = db.query(Order).filter(Order.shopify_order_id == "gid://shopify/Order/5001").first()
    assert ord1 is not None
    assert ord1.total_price == Decimal("95.00")
    assert ord1.financial_status == "paid"
    assert ord1.cancelled_at is None
    assert len(ord1.items) == 1
    assert ord1.items[0].quantity == 2
    assert ord1.items[0].sku == "LEC-15"

    # Verify Order 2 (Cancelled & Refunded)
    ord2 = db.query(Order).filter(Order.shopify_order_id == "gid://shopify/Order/5002").first()
    assert ord2 is not None
    assert ord2.cancelled_at is not None
    assert ord2.cancel_reason == "CUSTOMER"
    assert ord2.financial_status == "voided"
    assert ord2.total_refunded == Decimal("45.00")


def test_inventory_sync_snapshots(db: Session) -> None:
    """Verify inventory synchronization records Location snapshots and updates available stock."""
    merchant = Merchant(email=f"inv_test_{uuid.uuid4().hex[:6]}@example.com", password_hash="testhash", is_demo=False)
    db.add(merchant)
    db.flush()

    store = ConnectedStore(
        merchant_id=merchant.id,
        shop_domain="inv-boutique.myshopify.com",
        access_token_encrypted=encrypt_token("token123"),
        is_active=True,
    )
    db.add(store)
    db.flush()

    prod = Product(
        store_id=store.id,
        shopify_product_id="gid://shopify/Product/999",
        title="Test Inventory Product",
        status="active",
        price=Decimal("50.00"),
    )
    db.add(prod)
    db.flush()

    variant = ProductVariant(
        product_id=prod.id,
        shopify_variant_id="gid://shopify/ProductVariant/888",
        title="Default",
        sku="TIP-01",
        price=Decimal("50.00"),
        inventory_quantity=5,  # initial stock
    )
    db.add(variant)
    db.commit()

    mock_inv_data = {
        "inventory": {
            "locations": {
                "nodes": [
                    {
                        "id": "gid://shopify/Location/7001",
                        "name": "Main Warehouse",
                        "isActive": True,
                        "inventoryLevels": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [
                                {
                                    "id": "gid://shopify/InventoryLevel/6001",
                                    "updatedAt": "2026-11-24T12:00:00Z",
                                    "quantities": [{"name": "available", "quantity": 185}],
                                    "item": {
                                        "id": "gid://shopify/InventoryItem/5001",
                                        "variant": {"id": "gid://shopify/ProductVariant/888"},
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        }
    }

    client = MockGraphQLClient(mock_inv_data)
    synchronizer = ShopifySynchronizer(db, store, client=client)

    count = synchronizer.sync_inventory()
    assert count >= 1

    # Verify variant inventory quantity was updated to 185
    db.refresh(variant)
    assert variant.inventory_quantity == 185
    assert variant.available is True

    # Verify InventorySnapshot was created
    snapshot = db.query(InventorySnapshot).filter(InventorySnapshot.variant_id == variant.id).first()
    assert snapshot is not None
    assert snapshot.quantity == 185
    assert snapshot.location_id == "gid://shopify/Location/7001"
