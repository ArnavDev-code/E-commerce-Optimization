"""Tests for product catalog and COGS management."""

from decimal import Decimal
from sqlalchemy.orm import Session

from app.api.products import bulk_update_costs, get_product, list_products, update_product_cost
from app.demo.seed_data import seed_demo_data
from app.models.product import Product
from app.models.store import ConnectedStore
from app.schemas.analytics import BulkCostItem, BulkCostUploadRequest, ProductCostUpdate


def test_list_and_get_products(db: Session) -> None:
    """Test retrieving products with dynamically computed metrics."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    products = list_products(days=30, store=store, db=db)
    assert len(products) == 24
    top_product = products[0]
    assert top_product.views > 0
    assert top_product.title is not None
    assert top_product.price is not None

    # Get single product
    single = get_product(product_id=top_product.id, days=30, store=store, db=db)
    assert single.id == top_product.id
    assert single.title == top_product.title


def test_update_product_cost(db: Session) -> None:
    """Test updating COGS for a product."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    prod = db.query(Product).filter(Product.store_id == store.id).first()
    assert prod is not None

    # Update COGS
    new_cost = Decimal("19.50")
    update_res = update_product_cost(
        product_id=prod.id,
        payload=ProductCostUpdate(unit_cost=new_cost, cost_source="manual"),
        store=store,
        db=db,
    )
    assert update_res["status"] == "updated"
    assert update_res["unit_cost"] == 19.50

    db.refresh(prod)
    assert prod.unit_cost == new_cost
    assert prod.cost_source == "manual"


def test_bulk_update_costs(db: Session) -> None:
    """Test bulk updating unit costs via handle / SKU."""
    seed_demo_data(db, force_reset=True)
    store = db.query(ConnectedStore).first()
    assert store is not None

    prod = db.query(Product).filter(Product.store_id == store.id).first()
    assert prod is not None

    bulk_req = BulkCostUploadRequest(
        items=[
            BulkCostItem(handle=prod.handle, unit_cost=Decimal("22.00")),
        ]
    )
    res = bulk_update_costs(payload=bulk_req, store=store, db=db)
    assert res["status"] == "success"
    assert res["updated_count"] == 1

    db.refresh(prod)
    assert prod.unit_cost == Decimal("22.00")
    assert prod.cost_source == "upload"
