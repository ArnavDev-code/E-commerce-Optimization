"""Product catalog, performance metrics, and COGS management endpoints."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_store
from app.database import get_db
from app.engine.analytics_engine import AnalyticsEngine
from app.models.product import Product, ProductVariant
from app.models.store import ConnectedStore
from app.schemas.analytics import (
    BulkCostUploadRequest,
    ProductCostUpdate,
    ProductResponse,
    VariantResponse,
)

router = APIRouter(prefix="/products", tags=["Products & COGS"])


@router.get("", response_model=List[ProductResponse])
def list_products(
    days: Annotated[int, Query(ge=7, le=90)] = 30,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> List[ProductResponse]:
    """List store products with aggregated views, cart additions, conversion rate, and revenue."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    engine = AnalyticsEngine(db, store.id)
    metric_rows = engine.compute_product_metrics_table(start_date, end_date)

    responses = []
    for row in metric_rows:
        p: Product = row["product"]
        variants = [
            VariantResponse.model_validate(v)
            for v in (p.variants or [])
        ]

        resp = ProductResponse(
            id=p.id,
            store_id=p.store_id,
            shopify_product_id=p.shopify_product_id,
            title=p.title,
            handle=p.handle,
            product_type=p.product_type,
            vendor=p.vendor,
            status=p.status,
            price=p.price,
            compare_at_price=p.compare_at_price,
            unit_cost=p.unit_cost,
            cost_source=p.cost_source,
            image_url=p.image_url,
            created_at=p.created_at,
            synced_at=p.synced_at,
            variants=variants,
            views=row["views"],
            add_to_carts=row["add_to_carts"],
            add_to_cart_rate=row["add_to_cart_rate"],
            purchases=row["purchases"],
            revenue=row["revenue"],
            gross_margin_pct=row["gross_margin_pct"],
        )
        responses.append(resp)

    # Sort by views descending (highest traffic items first)
    responses.sort(key=lambda x: x.views, reverse=True)
    return responses


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    days: Annotated[int, Query(ge=7, le=90)] = 30,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Get single product details with variants and period performance."""
    prod = db.execute(
        select(Product).where(Product.id == product_id, Product.store_id == store.id)
    ).scalar_one_or_none()

    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in this store",
        )

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    engine = AnalyticsEngine(db, store.id)
    all_rows = engine.compute_product_metrics_table(start_date, end_date)
    matching = next((r for r in all_rows if r["product"].id == prod.id), None)

    variants = [VariantResponse.model_validate(v) for v in (prod.variants or [])]

    return ProductResponse(
        id=prod.id,
        store_id=prod.store_id,
        shopify_product_id=prod.shopify_product_id,
        title=prod.title,
        handle=prod.handle,
        product_type=prod.product_type,
        vendor=prod.vendor,
        status=prod.status,
        price=prod.price,
        compare_at_price=prod.compare_at_price,
        unit_cost=prod.unit_cost,
        cost_source=prod.cost_source,
        image_url=prod.image_url,
        created_at=prod.created_at,
        synced_at=prod.synced_at,
        variants=variants,
        views=matching["views"] if matching else 0,
        add_to_carts=matching["add_to_carts"] if matching else 0,
        add_to_cart_rate=matching["add_to_cart_rate"] if matching else None,
        purchases=matching["purchases"] if matching else 0,
        revenue=matching["revenue"] if matching else Decimal("0.00"),
        gross_margin_pct=matching["gross_margin_pct"] if matching else None,
    )


@router.put("/{product_id}/cost")
def update_product_cost(
    product_id: uuid.UUID,
    payload: ProductCostUpdate,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update COGS (unit cost) for a product to enable gross profit and margin calculations."""
    prod = db.execute(
        select(Product).where(Product.id == product_id, Product.store_id == store.id)
    ).scalar_one_or_none()

    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in this store",
        )

    prod.unit_cost = payload.unit_cost
    prod.cost_source = payload.cost_source

    # Update associated variants
    for variant in prod.variants:
        variant.unit_cost = payload.unit_cost

    db.commit()
    return {
        "status": "updated",
        "product_id": str(prod.id),
        "title": prod.title,
        "unit_cost": float(prod.unit_cost),
        "cost_source": prod.cost_source,
    }


@router.post("/costs/bulk")
def bulk_update_costs(
    payload: BulkCostUploadRequest,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Bulk update product unit costs by Product ID, SKU, or Handle."""
    updated_count = 0

    for item in payload.items:
        prod = None
        if item.product_id:
            prod = db.execute(
                select(Product).where(Product.id == item.product_id, Product.store_id == store.id)
            ).scalar_one_or_none()
        elif item.handle:
            prod = db.execute(
                select(Product).where(Product.handle == item.handle, Product.store_id == store.id)
            ).scalar_one_or_none()
        elif item.sku:
            variant = db.execute(
                select(ProductVariant)
                .join(Product)
                .where(ProductVariant.sku == item.sku, Product.store_id == store.id)
            ).scalar_one_or_none()
            if variant:
                prod = variant.product

        if prod:
            prod.unit_cost = item.unit_cost
            prod.cost_source = "upload"
            for v in prod.variants:
                v.unit_cost = item.unit_cost
            updated_count += 1

    db.commit()
    return {
        "status": "success",
        "updated_count": updated_count,
        "total_requested": len(payload.items),
    }
