"""Tests for multi-tenant merchant and store data isolation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_store, register
from app.models.merchant import Merchant
from app.models.store import ConnectedStore
from app.schemas.auth import MerchantRegister


def test_merchant_store_isolation(db: Session) -> None:
    """Verify that every merchant gets an isolated store and cannot access other stores."""
    # 1. Register Merchant A
    res_a = register(
        MerchantRegister(email="alice@store-a.com", password="passwordA123!"),
        db=db,
    )
    merchant_a_id = res_a.merchant.id

    # 2. Register Merchant B
    res_b = register(
        MerchantRegister(email="bob@store-b.com", password="passwordB123!"),
        db=db,
    )
    merchant_b_id = res_b.merchant.id

    # 3. Query DB stores
    store_a = db.execute(
        select(ConnectedStore).where(ConnectedStore.merchant_id == merchant_a_id)
    ).scalar_one()

    store_b = db.execute(
        select(ConnectedStore).where(ConnectedStore.merchant_id == merchant_b_id)
    ).scalar_one()

    assert store_a.id != store_b.id
    assert store_a.shop_domain != store_b.shop_domain
    assert store_a.merchant_id != store_b.merchant_id

    # 4. Verify get_current_store dependency resolves correctly for Merchant A
    merchant_a = db.execute(
        select(Merchant).where(Merchant.id == merchant_a_id)
    ).scalar_one()
    resolved_store_a = get_current_store(merchant=merchant_a, db=db)
    assert resolved_store_a.id == store_a.id
    assert resolved_store_a.id != store_b.id

    # 5. Verify get_current_store dependency resolves correctly for Merchant B
    merchant_b = db.execute(
        select(Merchant).where(Merchant.id == merchant_b_id)
    ).scalar_one()
    resolved_store_b = get_current_store(merchant=merchant_b, db=db)
    assert resolved_store_b.id == store_b.id
    assert resolved_store_b.id != store_a.id
