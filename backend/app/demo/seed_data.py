"""Comprehensive demo dataset generator with realistic conversion problems."""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.analytics import FunnelMetric, GA4Metric
from app.models.event import StorefrontEvent
from app.models.experiment import Experiment, ExperimentResult
from app.models.leak import AIDiagnosis, DetectedLeak, Recommendation
from app.models.merchant import Merchant
from app.models.order import Order, OrderItem
from app.models.product import InventorySnapshot, Product, ProductVariant
from app.models.store import ConnectedStore
from app.models.sync import SyncLog
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@funnelleak.ai"
DEMO_SHOP_DOMAIN = "demo-store.myshopify.com"


def seed_demo_data(db: Session, force_reset: bool = False) -> dict[str, Any]:
    """Seed the database with realistic demo store data.
    
    Idempotent: if demo data exists and force_reset=False, returns existing stats.
    """
    random.seed(42)  # Deterministic seed for reproducible testing

    existing_merchant = db.execute(
        select(Merchant).where(Merchant.email == DEMO_EMAIL)
    ).scalar_one_or_none()

    if existing_merchant and not force_reset:
        logger.info("Demo data already exists. Skipping seed.")
        return {"status": "already_seeded", "merchant_id": str(existing_merchant.id)}

    if existing_merchant and force_reset:
        logger.info("Cleaning up existing demo merchant data for fresh seed...")
        db.delete(existing_merchant)
        db.commit()

    # 1. Create Demo Merchant
    merchant = Merchant(
        email=DEMO_EMAIL,
        password_hash=hash_password("demo123"),
        name="Lumina & Aura Retail (Demo)",
        is_demo=True,
    )
    db.add(merchant)
    db.flush()

    # 2. Create Connected Store
    store = ConnectedStore(
        merchant_id=merchant.id,
        platform="shopify",
        shop_domain=DEMO_SHOP_DOMAIN,
        access_token_encrypted="demo_token_mocked_for_sandbox",
        scopes="read_products,read_orders,read_inventory,read_analytics",
        is_active=True,
    )
    db.add(store)
    db.flush()

    # 3. Load Products from JSON
    json_path = Path(__file__).parent / "demo_products.json"
    with open(json_path, "r", encoding="utf-8") as f:
        products_json = json.load(f)

    db_products: list[Product] = []
    db_variants: list[ProductVariant] = []

    for p_data in products_json:
        prod = Product(
            store_id=store.id,
            shopify_product_id=f"gid://shopify/Product/{random.randint(7000000000, 7999999999)}",
            title=p_data["title"],
            handle=p_data["handle"],
            product_type=p_data["product_type"],
            vendor=p_data["vendor"],
            status="active",
            price=Decimal(str(p_data["price"])),
            compare_at_price=Decimal(str(p_data["compare_at_price"])) if p_data.get("compare_at_price") else None,
            unit_cost=Decimal(str(p_data["unit_cost"])) if p_data.get("unit_cost") else None,
            cost_source=p_data.get("cost_source", "manual"),
            image_url=p_data.get("image_url"),
            synced_at=datetime.now(timezone.utc),
        )
        db.add(prod)
        db.flush()
        db_products.append(prod)

        for v_data in p_data["variants"]:
            variant = ProductVariant(
                product_id=prod.id,
                shopify_variant_id=f"gid://shopify/ProductVariant/{random.randint(40000000000, 49999999999)}",
                sku=v_data.get("sku"),
                title=v_data.get("title"),
                price=Decimal(str(v_data.get("price", p_data["price"]))),
                unit_cost=Decimal(str(v_data.get("unit_cost", p_data["unit_cost"]))),
                inventory_quantity=v_data.get("inventory_quantity", 100),
                available=True,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(variant)
            db.flush()
            db_variants.append(variant)

    db.commit()

    # 4. Generate Inventory Snapshots (past 30 days)
    today = date.today()
    for variant in db_variants:
        base_qty = variant.inventory_quantity
        for days_ago in range(30, -1, -1):
            snap_date = today - timedelta(days=days_ago)
            # slight jitter
            jitter = random.randint(-2, 3) if days_ago > 0 else 0
            qty = max(0, base_qty + (days_ago * random.choice([1, 2])) + jitter)
            snap = InventorySnapshot(
                variant_id=variant.id,
                quantity=qty,
                snapshot_date=snap_date,
            )
            db.add(snap)

    db.commit()

    # 5. Generate 60 Days of Storefront Events & Orders (to support prior period decline analysis)
    devices = ["mobile", "desktop", "tablet"]
    device_weights = [0.65, 0.28, 0.07]

    sources = ["organic_search", "paid_social", "direct", "email", "paid_search"]
    source_weights = [0.35, 0.28, 0.18, 0.10, 0.09]

    now = datetime.now(timezone.utc)
    order_num = 1001

    events_to_insert: list[StorefrontEvent] = []
    orders_to_insert: list[Order] = []
    order_items_to_insert: list[OrderItem] = []

    # Map problem types to product handles
    problem_map = {p["handle"]: p.get("problem_flag") for p in products_json}

    for days_ago in range(60, -1, -1):
        day_date = now - timedelta(days=days_ago)

        for prod in db_products:
            p_flag = problem_map.get(prod.handle)

            # Baseline daily views (calibrated for snappy dev/demo startup and robust samples)
            if prod.handle in ["vitamin-c-brightening-serum", "hydrolyzed-marine-collagen-peptides", "hyaluronic-acid-intense-moisturizer"]:
                daily_views = random.randint(25, 40)
            elif prod.handle in ["cashmere-blend-oversized-knit-sweater", "retinol-recovery-night-cream", "organic-rosehip-face-oil"]:
                daily_views = random.randint(18, 28)
            else:
                daily_views = random.randint(6, 12)

            for _ in range(daily_views):
                session_id = f"sess_{uuid.uuid4().hex[:12]}"
                device = random.choices(devices, weights=device_weights)[0]
                source = random.choices(sources, weights=source_weights)[0]
                event_time = day_date.replace(
                    hour=random.randint(0, 23),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                )

                # Event 1: Product Viewed
                view_ev = StorefrontEvent(
                    store_id=store.id,
                    event_type="product_viewed",
                    session_id=session_id,
                    shopify_product_id=prod.shopify_product_id,
                    page_url=f"https://demo-store.myshopify.com/products/{prod.handle}",
                    device_category=device,
                    traffic_source=source,
                    event_timestamp=event_time,
                )
                events_to_insert.append(view_ev)

                # Determine ATC probability based on product characteristics
                if p_flag == "low_atc_rate":
                    atc_prob = 0.012  # Deliberate leak: 1.2%
                elif p_flag == "atc_rate_decline":
                    # First 30 days normal (5.2%), last 30 days plummeted (2.1%)
                    atc_prob = 0.052 if days_ago > 30 else 0.021
                elif p_flag == "mobile_leak":
                    atc_prob = 0.009 if device == "mobile" else 0.045
                elif p_flag == "overstocked_underperformer":
                    atc_prob = 0.015
                elif p_flag == "stockout_risk":
                    atc_prob = 0.065
                else:
                    atc_prob = random.uniform(0.040, 0.058)

                if random.random() > atc_prob:
                    continue  # Did not add to cart

                # Event 2: Product Added to Cart
                atc_time = event_time + timedelta(seconds=random.randint(20, 180))
                atc_ev = StorefrontEvent(
                    store_id=store.id,
                    event_type="product_added_to_cart",
                    session_id=session_id,
                    shopify_product_id=prod.shopify_product_id,
                    page_url=f"https://demo-store.myshopify.com/products/{prod.handle}",
                    device_category=device,
                    traffic_source=source,
                    event_timestamp=atc_time,
                )
                events_to_insert.append(atc_ev)

                # Determine checkout progression probability
                if p_flag == "high_atc_low_checkout":
                    checkout_prob = 0.14  # Deliberate leak: dropoff before checkout start
                else:
                    checkout_prob = random.uniform(0.60, 0.72)

                if random.random() > checkout_prob:
                    continue

                # Event 3: Checkout Started
                chk_time = atc_time + timedelta(seconds=random.randint(30, 240))
                chk_ev = StorefrontEvent(
                    store_id=store.id,
                    event_type="checkout_started",
                    session_id=session_id,
                    shopify_product_id=prod.shopify_product_id,
                    device_category=device,
                    traffic_source=source,
                    event_timestamp=chk_time,
                )
                events_to_insert.append(chk_ev)

                # Determine purchase completion probability
                if p_flag == "low_purchase_completion":
                    purchase_prob = 0.22  # Deliberate leak: payment stage dropoff
                else:
                    purchase_prob = random.uniform(0.68, 0.78)

                if random.random() > purchase_prob:
                    continue

                # Event 4: Checkout Completed (Purchase)
                pur_time = chk_time + timedelta(seconds=random.randint(60, 300))
                pur_ev = StorefrontEvent(
                    store_id=store.id,
                    event_type="checkout_completed",
                    session_id=session_id,
                    shopify_product_id=prod.shopify_product_id,
                    device_category=device,
                    traffic_source=source,
                    event_timestamp=pur_time,
                )
                events_to_insert.append(pur_ev)

                # Create Order and OrderItem
                qty = 1 if random.random() > 0.15 else 2
                item_total = prod.price * qty
                order_id = uuid.uuid4()
                order = Order(
                    id=order_id,
                    store_id=store.id,
                    shopify_order_id=f"gid://shopify/Order/{random.randint(5000000000, 5999999999)}",
                    order_number=f"#{order_num}",
                    total_price=item_total,
                    subtotal_price=item_total,
                    total_discounts=Decimal("0.00"),
                    financial_status="paid",
                    fulfillment_status="fulfilled",
                    item_count=qty,
                    traffic_source=source,
                    device_category=device,
                    order_date=pur_time,
                    synced_at=now,
                )
                orders_to_insert.append(order)

                order_item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    product_id=prod.id,
                    shopify_product_id=prod.shopify_product_id,
                    title=prod.title,
                    quantity=qty,
                    price=prod.price,
                    total_discount=Decimal("0.00"),
                )
                order_items_to_insert.append(order_item)
                order_num += 1

    # Batch save events and orders to keep memory clean
    logger.info("Inserting %d storefront events...", len(events_to_insert))
    db.bulk_save_objects(events_to_insert)
    db.commit()

    logger.info("Inserting %d orders...", len(orders_to_insert))
    db.bulk_save_objects(orders_to_insert)
    db.bulk_save_objects(order_items_to_insert)
    db.commit()

    # 6. Aggregate Weekly Funnel Metrics (last 12 weeks)
    logger.info("Computing demo weekly funnel metrics...")
    from collections import defaultdict
    weekly_counts = defaultdict(lambda: {"views": 0, "atcs": 0, "chks": 0, "purchases": 0})

    for e in events_to_insert:
        days_diff = (now.date() - e.event_timestamp.date()).days
        week_idx = days_diff // 7
        if 0 <= week_idx < 12 and e.shopify_product_id:
            key = (week_idx, e.shopify_product_id)
            if e.event_type == "product_viewed":
                weekly_counts[key]["views"] += 1
            elif e.event_type == "product_added_to_cart":
                weekly_counts[key]["atcs"] += 1
            elif e.event_type == "checkout_started":
                weekly_counts[key]["chks"] += 1
            elif e.event_type == "checkout_completed":
                weekly_counts[key]["purchases"] += 1

    for week_idx in range(8):
        w_start = (now - timedelta(days=(week_idx + 1) * 7)).date()
        w_end = (now - timedelta(days=week_idx * 7)).date()

        for prod in db_products:
            c = weekly_counts.get((week_idx, prod.shopify_product_id), {"views": 0, "atcs": 0, "chks": 0, "purchases": 0})
            p_views = c["views"]
            p_atcs = c["atcs"]
            p_chks = c["chks"]
            p_purchases = c["purchases"]

            atc_rate = Decimal(str(round((p_atcs / p_views * 100) if p_views > 0 else 0, 4)))
            chk_rate = Decimal(str(round((p_chks / p_atcs * 100) if p_atcs > 0 else 0, 4)))
            pur_rate = Decimal(str(round((p_purchases / p_chks * 100) if p_chks > 0 else 0, 4)))

            p_revenue = Decimal(str(round(p_purchases * float(prod.price), 2)))
            rpv = Decimal(str(round((float(p_revenue) / p_views) if p_views > 0 else 0, 4)))
            aov = prod.price if p_purchases > 0 else Decimal("0.00")

            gross_profit = None
            gp_per_visitor = None
            if prod.unit_cost is not None:
                unit_margin = prod.price - prod.unit_cost
                gross_profit = Decimal(str(round(p_purchases * float(unit_margin), 2)))
                gp_per_visitor = Decimal(str(round((float(gross_profit) / p_views) if p_views > 0 else 0, 4)))

            funnel_metric = FunnelMetric(
                store_id=store.id,
                product_id=prod.id,
                data_source="pixel",
                period_start=w_start,
                period_end=w_end,
                segment_type="overall",
                segment_value="all",
                product_views=p_views,
                add_to_carts=p_atcs,
                add_to_cart_rate=atc_rate,
                checkout_starts=p_chks,
                checkout_rate=chk_rate,
                purchases=p_purchases,
                purchase_rate=pur_rate,
                revenue=p_revenue,
                aov=aov,
                revenue_per_visitor=rpv,
                gross_profit=gross_profit,
                gross_profit_per_visitor=gp_per_visitor,
            )
            db.add(funnel_metric)

    db.commit()

    # 7. Pre-seed Detected Leaks for the 4 Active Rules
    recent_30_start = (now - timedelta(days=30)).date()
    recent_30_end = now.date()

    prod_by_handle = {p.handle: p for p in db_products}

    # Leak 1: Low ATC rate (Rule 1)
    vit_c = prod_by_handle["vitamin-c-brightening-serum"]
    leak_1 = DetectedLeak(
        store_id=store.id,
        product_id=vit_c.id,
        leak_type="low_atc_rate",
        metric_affected="add_to_cart_rate",
        observed_value=Decimal("1.25"),
        baseline_value=Decimal("4.80"),
        sample_size=4280,
        period_start=recent_30_start,
        period_end=recent_30_end,
        severity="critical",
        confidence_score=Decimal("0.96"),
        evidence_quality="strong",
        reason="Add-to-cart rate (1.25%) is 74% below the store category median (4.80%) across 4,280 verified visits.",
        status="new",
    )
    db.add(leak_1)
    db.flush()

    diag_1 = AIDiagnosis(
        leak_id=leak_1.id,
        provider="fallback",
        issue_summary="Severe Add-to-Cart Friction on High-Traffic Hero Serum",
        evidence=[
            {"fact": "Observed ATC rate: 1.25%", "verified_by": "Web Pixel"},
            {"fact": "Category baseline: 4.80%", "verified_by": "Store catalog benchmark"},
            {"fact": "Sample size: 4,280 views in past 30 days", "verified_by": "Web Pixel"},
            {"fact": "Mobile traffic share: 74.2%", "verified_by": "Session breakdown"},
        ],
        possible_explanations=[
            {"hypothesis": "Mobile fold issue: CTA button below the second screen on standard iOS viewports", "likelihood": "High"},
            {"hypothesis": "Lack of immediate trust signals (dermatologist tested badge, ingredient % clarity)", "likelihood": "Medium"},
            {"hypothesis": "Ad creative mismatch (social ad highlights acne clearing, but landing hero copy emphasizes anti-aging)", "likelihood": "Medium"},
        ],
        further_checks=[
            "Inspect mobile viewport rendering for iPhone 13/14/15 screens",
            "Verify whether customer reviews widget is loading asynchronously or being blocked",
            "Review Google PageSpeed insights for product page image LCP",
        ],
        recommended_actions=[
            {"action": "Deploy sticky Add-to-Cart bar on mobile viewport", "expected_impact": "+15-25% mobile ATC rate"},
            {"action": "Display key active ingredients (15% Pure L-Ascorbic Acid) directly below title", "expected_impact": "Enhanced clarity"},
            {"action": "Add 3 concise customer review pull-quotes above the fold", "expected_impact": "Trust reinforcement"},
        ],
        confidence_level="high",
        is_fallback=True,
    )
    db.add(diag_1)

    rec_1 = Recommendation(
        store_id=store.id,
        leak_id=leak_1.id,
        product_id=vit_c.id,
        detected_problem="Vitamin C Serum Add-to-Cart rate is 74% below store average despite driving 4,280 views.",
        supporting_evidence={"observed_atc": 1.25, "baseline_atc": 4.80, "views": 4280, "mobile_share": 74.2},
        suggested_action="Implement sticky Add-to-Cart mobile button and reinforce active ingredient concentration above the fold.",
        business_reason="With $48 AOV and 65% gross margin, lifting ATC rate to 3.0% recovers an estimated $3,600/month in lost margin.",
        priority="critical",
        metric_to_monitor="add_to_cart_rate",
        status="pending",
    )
    db.add(rec_1)

    # Leak 2: ATC Rate Decline (Rule 2)
    retinol = prod_by_handle["retinol-recovery-night-cream"]
    leak_2 = DetectedLeak(
        store_id=store.id,
        product_id=retinol.id,
        leak_type="atc_rate_decline",
        metric_affected="add_to_cart_rate",
        observed_value=Decimal("2.10"),
        baseline_value=Decimal("5.20"),
        sample_size=2150,
        period_start=recent_30_start,
        period_end=recent_30_end,
        severity="high",
        confidence_score=Decimal("0.92"),
        evidence_quality="strong",
        reason="Add-to-cart rate declined by 59.6% compared to the prior 30-day baseline (from 5.20% down to 2.10%, p < 0.001).",
        status="new",
    )
    db.add(leak_2)
    db.flush()

    rec_2 = Recommendation(
        store_id=store.id,
        leak_id=leak_2.id,
        product_id=retinol.id,
        detected_problem="Retinol Night Cream conversion dropped sharply from 5.2% to 2.1% over the past 30 days.",
        supporting_evidence={"prior_atc": 5.20, "recent_atc": 2.10, "decline_pct": 59.6, "sample_size": 2150},
        suggested_action="Audit recent theme modifications, review negative reviews regarding formula redesign, and verify variant availability.",
        business_reason="Product was historically top 3 profit generator. Addressing sudden degradation prevents further brand equity erosion.",
        priority="high",
        metric_to_monitor="add_to_cart_rate",
        status="pending",
    )
    db.add(rec_2)

    # Leak 3: High ATC, Low Checkout Progression (Rule 3)
    hyaluronic = prod_by_handle["hyaluronic-acid-intense-moisturizer"]
    leak_3 = DetectedLeak(
        store_id=store.id,
        product_id=hyaluronic.id,
        leak_type="high_atc_low_checkout",
        metric_affected="checkout_rate",
        observed_value=Decimal("14.20"),
        baseline_value=Decimal("64.50"),
        sample_size=340,
        period_start=recent_30_start,
        period_end=recent_30_end,
        severity="high",
        confidence_score=Decimal("0.90"),
        evidence_quality="strong",
        reason="Strong initial purchase intent (6.5% ATC), but only 14.2% progress to checkout (store benchmark: 64.5%).",
        status="new",
    )
    db.add(leak_3)
    db.flush()

    rec_3 = Recommendation(
        store_id=store.id,
        leak_id=leak_3.id,
        product_id=hyaluronic.id,
        detected_problem="85.8% of users who add Hyaluronic Moisturizer to cart abandon before reaching the checkout page.",
        supporting_evidence={"atc_count": 340, "checkout_rate": 14.20, "benchmark_rate": 64.50},
        suggested_action="Inspect cart drawer: verify free shipping progress bar threshold and check for unexpected cart-level fee alerts.",
        business_reason="Users love the product enough to cart it, but experience sticker shock or navigation friction inside the cart drawer.",
        priority="high",
        metric_to_monitor="checkout_rate",
        status="pending",
    )
    db.add(rec_3)

    # Leak 4: Low Purchase Completion from Checkout (Rule 4)
    rose_oil = prod_by_handle["organic-rosehip-face-oil"]
    leak_4 = DetectedLeak(
        store_id=store.id,
        product_id=rose_oil.id,
        leak_type="low_purchase_completion",
        metric_affected="purchase_rate",
        observed_value=Decimal("22.50"),
        baseline_value=Decimal("72.00"),
        sample_size=180,
        period_start=recent_30_start,
        period_end=recent_30_end,
        severity="medium",
        confidence_score=Decimal("0.85"),
        evidence_quality="moderate",
        reason="Checkout initiation is healthy, but 77.5% abandon during payment step (observed purchase rate: 22.5% vs 72.0% store baseline).",
        status="new",
    )
    db.add(leak_4)
    db.flush()

    rec_4 = Recommendation(
        store_id=store.id,
        leak_id=leak_4.id,
        product_id=rose_oil.id,
        detected_problem="Checkout started but purchase completion is 22.5% (store baseline 72.0%).",
        supporting_evidence={"checkout_starts": 180, "purchase_rate": 22.50, "store_baseline": 72.00},
        suggested_action="Enable 1-click accelerated checkout buttons (Shop Pay, Apple Pay) and surface hassle-free 30-day refund guarantee at payment step.",
        business_reason="Merchants lose paid customer acquisition dollars at the very finish line of the checkout.",
        priority="medium",
        metric_to_monitor="purchase_rate",
        status="pending",
    )
    db.add(rec_4)

    # 8. Create Sample Completed Experiment (Before / After Intervention)
    # Statistical integrity: conversion counts and denominators are exact integers
    # Control: 25 conversions out of 2,000 views (1.25%)
    # Treatment: 60 conversions out of 2,100 views (2.857%)
    # Two-proportion z = 3.6099, p-value = 0.0003
    exp = Experiment(
        store_id=store.id,
        recommendation_id=rec_1.id,
        product_id=vit_c.id,
        name="Vitamin C Mobile Sticky Add-to-Cart Intervention",
        experiment_type="before_after",
        hypothesis="Adding a sticky, high-contrast Add-to-Cart bar on mobile will reduce friction and lift mobile ATC rate from 1.25% towards the 3.0% target.",
        control_description="Baseline 14-day pre-intervention period (standard theme product page layout)",
        treatment_description="14-day post-intervention period (sticky Add-to-Cart footer bar active on mobile viewports < 768px)",
        change_made="Enabled responsive sticky CTA bar in theme settings with direct variant price display",
        status="completed",
        start_date=recent_30_start,
        end_date=recent_30_start + timedelta(days=28),
        metric_to_track="add_to_cart_rate",
    )
    db.add(exp)
    db.flush()

    exp_result = ExperimentResult(
        experiment_id=exp.id,
        metric_name="add_to_cart_rate",
        control_value=Decimal("1.25"),
        treatment_value=Decimal("2.86"),
        absolute_change=Decimal("1.61"),
        relative_change_pct=Decimal("128.80"),
        control_sample_size=2000,
        treatment_sample_size=2100,
        is_statistically_significant=True,
        p_value=Decimal("0.0003"),
        merchant_conclusion="Sticky mobile button successfully improved Add-to-Cart rate from 1.25% (25/2000) to 2.86% (60/2100) (+128.8% relative lift). Keeping this change permanently active on mobile.",
    )
    db.add(exp_result)

    # 9. Sync Log entry
    sync_log = SyncLog(
        store_id=store.id,
        sync_type="pixel",
        status="completed",
        records_synced=len(events_to_insert),
        started_at=now - timedelta(minutes=5),
        completed_at=now,
    )
    db.add(sync_log)

    db.commit()

    logger.info("Demo data seeding completed successfully.")
    return {
        "status": "success",
        "merchant": DEMO_EMAIL,
        "store": DEMO_SHOP_DOMAIN,
        "products_count": len(db_products),
        "events_count": len(events_to_insert),
        "orders_count": len(orders_to_insert),
        "leaks_count": 4,
        "experiments_count": 1,
    }
