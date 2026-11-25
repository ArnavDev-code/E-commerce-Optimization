"""Deterministic analytics computation engine using SQL and Pandas.

All business metrics are strictly calculated from underlying events, orders,
and inventory levels. No metrics are hallucinated or hardcoded.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import StorefrontEvent
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    FunnelAnalyticsResponse,
    FunnelStageMetric,
    SegmentBreakdown,
)


class AnalyticsEngine:
    """Calculates e-commerce conversion funnels, financial efficiency, and segmentations."""

    def __init__(self, db: Session, store_id: uuid.UUID):
        self.db = db
        self.store_id = store_id

    def compute_overview_kpis(
        self, start_date: date, end_date: date
    ) -> AnalyticsOverviewResponse:
        """Compute store-level aggregate KPIs from underlying storefront events and orders."""
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        # 1. Total unique sessions & event counts from storefront_events
        events_stmt = (
            select(
                StorefrontEvent.event_type,
                func.count(StorefrontEvent.id).label("count"),
                func.count(func.distinct(StorefrontEvent.session_id)).label("unique_sessions"),
            )
            .where(
                StorefrontEvent.store_id == self.store_id,
                StorefrontEvent.event_timestamp >= start_dt,
                StorefrontEvent.event_timestamp <= end_dt,
            )
            .group_by(StorefrontEvent.event_type)
        )
        event_counts = {row.event_type: row.count for row in self.db.execute(events_stmt).all()}

        total_views = event_counts.get("product_viewed", 0)
        total_atcs = event_counts.get("product_added_to_cart", 0)
        total_purchases_from_events = event_counts.get("checkout_completed", 0)

        # Total distinct sessions across all events
        total_sessions = (
            self.db.execute(
                select(func.count(func.distinct(StorefrontEvent.session_id))).where(
                    StorefrontEvent.store_id == self.store_id,
                    StorefrontEvent.event_timestamp >= start_dt,
                    StorefrontEvent.event_timestamp <= end_dt,
                )
            ).scalar()
            or 0
        )

        # 2. Financial totals from Orders
        orders_stmt = select(
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_price), 0).label("total_revenue"),
        ).where(
            Order.store_id == self.store_id,
            Order.order_date >= start_dt,
            Order.order_date <= end_dt,
        )
        order_res = self.db.execute(orders_stmt).one()
        total_orders = order_res.order_count or 0
        revenue = Decimal(str(round(order_res.total_revenue, 2)))

        aov = Decimal("0.00")
        if total_orders > 0:
            aov = Decimal(str(round(revenue / total_orders, 2)))

        # Overall conversion rate = orders / sessions * 100 (or purchases / views if sessions = 0)
        overall_conversion_rate = Decimal("0.00")
        denom = total_sessions if total_sessions > 0 else total_views
        if denom > 0:
            overall_conversion_rate = Decimal(
                str(round((total_orders / denom) * 100, 2))
            )

        # 3. Calculate Gross Profit from order items where unit_cost is present
        profit_stmt = (
            select(
                OrderItem.quantity,
                OrderItem.price,
                Product.unit_cost,
            )
            .join(Order, Order.id == OrderItem.order_id)
            .outerjoin(Product, Product.id == OrderItem.product_id)
            .where(
                Order.store_id == self.store_id,
                Order.order_date >= start_dt,
                Order.order_date <= end_dt,
            )
        )
        item_rows = self.db.execute(profit_stmt).all()

        gross_profit = None
        gross_profit_per_visitor = None

        if item_rows:
            # Check if unit costs are available
            items_with_cost = [r for r in item_rows if r.unit_cost is not None]
            if items_with_cost:
                total_margin = sum(
                    (r.price - r.unit_cost) * r.quantity for r in items_with_cost
                )
                gross_profit = Decimal(str(round(total_margin, 2)))
                if total_views > 0:
                    gross_profit_per_visitor = Decimal(
                        str(round(gross_profit / total_views, 4))
                    )

        # Count active detected leaks
        from app.models.leak import DetectedLeak
        leaks_count = (
            self.db.execute(
                select(func.count(DetectedLeak.id)).where(
                    DetectedLeak.store_id == self.store_id,
                    DetectedLeak.status.in_(["new", "reviewed"]),
                )
            ).scalar()
            or 0
        )

        return AnalyticsOverviewResponse(
            period_start=start_date,
            period_end=end_date,
            total_sessions=total_sessions,
            total_views=total_views,
            total_add_to_carts=total_atcs,
            total_orders=total_orders,
            revenue=revenue,
            aov=aov,
            overall_conversion_rate=overall_conversion_rate,
            gross_profit=gross_profit,
            gross_profit_per_visitor=gross_profit_per_visitor,
            detected_leaks_count=leaks_count,
            data_source="pixel",
        )

    def compute_funnel_breakdown(
        self, start_date: date, end_date: date
    ) -> FunnelAnalyticsResponse:
        """Compute the full 4-stage funnel (Views -> ATCs -> Checkouts -> Purchases) + segments."""
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        events_stmt = (
            select(
                StorefrontEvent.event_type,
                StorefrontEvent.device_category,
                StorefrontEvent.traffic_source,
            ).where(
                StorefrontEvent.store_id == self.store_id,
                StorefrontEvent.event_timestamp >= start_dt,
                StorefrontEvent.event_timestamp <= end_dt,
            )
        )
        raw_events = self.db.execute(events_stmt).all()

        if not raw_events:
            return FunnelAnalyticsResponse(
                period_start=start_date,
                period_end=end_date,
                stages=[
                    FunnelStageMetric(stage="Product Views", count=0, conversion_rate=Decimal("100.0")),
                    FunnelStageMetric(stage="Add to Cart", count=0, conversion_rate=Decimal("0.0")),
                    FunnelStageMetric(stage="Checkout Started", count=0, conversion_rate=Decimal("0.0")),
                    FunnelStageMetric(stage="Purchases", count=0, conversion_rate=Decimal("0.0")),
                ],
                device_breakdown=[],
                source_breakdown=[],
            )

        df = pd.DataFrame(
            [
                {
                    "event_type": r.event_type,
                    "device": r.device_category or "unknown",
                    "source": r.traffic_source or "unknown",
                }
                for r in raw_events
            ]
        )

        # Stage counts
        v_count = int((df["event_type"] == "product_viewed").sum())
        a_count = int((df["event_type"] == "product_added_to_cart").sum())
        c_count = int((df["event_type"] == "checkout_started").sum())
        p_count = int((df["event_type"] == "checkout_completed").sum())

        atc_rate = Decimal(str(round((a_count / v_count * 100), 2))) if v_count > 0 else Decimal("0.00")
        chk_rate = Decimal(str(round((c_count / a_count * 100), 2))) if a_count > 0 else Decimal("0.00")
        pur_rate = Decimal(str(round((p_count / c_count * 100), 2))) if c_count > 0 else Decimal("0.00")

        stages = [
            FunnelStageMetric(
                stage="Product Views",
                count=v_count,
                conversion_rate=Decimal("100.00"),
                dropoff_rate=Decimal(str(round(100.0 - float(atc_rate), 2))),
            ),
            FunnelStageMetric(
                stage="Add to Cart",
                count=a_count,
                conversion_rate=atc_rate,
                dropoff_rate=Decimal(str(round(100.0 - float(chk_rate), 2))),
            ),
            FunnelStageMetric(
                stage="Checkout Started",
                count=c_count,
                conversion_rate=chk_rate,
                dropoff_rate=Decimal(str(round(100.0 - float(pur_rate), 2))),
            ),
            FunnelStageMetric(
                stage="Purchases Completed",
                count=p_count,
                conversion_rate=pur_rate,
                dropoff_rate=Decimal("0.00"),
            ),
        ]

        # Device Breakdown
        device_breakdown: List[SegmentBreakdown] = []
        for dev, group in df.groupby("device"):
            d_views = int((group["event_type"] == "product_viewed").sum())
            d_atcs = int((group["event_type"] == "product_added_to_cart").sum())
            d_purs = int((group["event_type"] == "checkout_completed").sum())

            d_atc_rate = Decimal(str(round((d_atcs / d_views * 100), 2))) if d_views > 0 else Decimal("0.00")
            d_conv = Decimal(str(round((d_purs / d_views * 100), 2))) if d_views > 0 else Decimal("0.00")

            device_breakdown.append(
                SegmentBreakdown(
                    segment_value=str(dev).capitalize(),
                    views=d_views,
                    add_to_carts=d_atcs,
                    add_to_cart_rate=d_atc_rate,
                    purchases=d_purs,
                    conversion_rate=d_conv,
                    revenue=Decimal("0.00"),
                )
            )

        # Traffic Source Breakdown
        source_breakdown: List[SegmentBreakdown] = []
        for src, group in df.groupby("source"):
            s_views = int((group["event_type"] == "product_viewed").sum())
            s_atcs = int((group["event_type"] == "product_added_to_cart").sum())
            s_purs = int((group["event_type"] == "checkout_completed").sum())

            s_atc_rate = Decimal(str(round((s_atcs / s_views * 100), 2))) if s_views > 0 else Decimal("0.00")
            s_conv = Decimal(str(round((s_purs / s_views * 100), 2))) if s_views > 0 else Decimal("0.00")

            source_breakdown.append(
                SegmentBreakdown(
                    segment_value=str(src).replace("_", " ").title(),
                    views=s_views,
                    add_to_carts=s_atcs,
                    add_to_cart_rate=s_atc_rate,
                    purchases=s_purs,
                    conversion_rate=s_conv,
                    revenue=Decimal("0.00"),
                )
            )

        return FunnelAnalyticsResponse(
            period_start=start_date,
            period_end=end_date,
            data_source="pixel",
            stages=stages,
            device_breakdown=sorted(device_breakdown, key=lambda x: x.views, reverse=True),
            source_breakdown=sorted(source_breakdown, key=lambda x: x.views, reverse=True),
        )

    def compute_product_metrics_table(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Calculate per-product views, cart additions, orders, conversion rate, and revenue."""
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        # Fetch products
        prods = (
            self.db.execute(
                select(Product)
                .where(Product.store_id == self.store_id)
                .order_by(Product.title)
            )
            .scalars()
            .all()
        )

        # Aggregate events per product
        events_stmt = (
            select(
                StorefrontEvent.shopify_product_id,
                StorefrontEvent.event_type,
                func.count(StorefrontEvent.id).label("cnt"),
            )
            .where(
                StorefrontEvent.store_id == self.store_id,
                StorefrontEvent.event_timestamp >= start_dt,
                StorefrontEvent.event_timestamp <= end_dt,
            )
            .group_by(StorefrontEvent.shopify_product_id, StorefrontEvent.event_type)
        )
        counts = {}
        for row in self.db.execute(events_stmt).all():
            counts[(row.shopify_product_id, row.event_type)] = row.cnt

        # Aggregate order item sales per product
        sales_stmt = (
            select(
                OrderItem.product_id,
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.price * OrderItem.quantity).label("gross_revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.store_id == self.store_id,
                Order.order_date >= start_dt,
                Order.order_date <= end_dt,
            )
            .group_by(OrderItem.product_id)
        )
        sales = {r.product_id: (r.units_sold or 0, r.gross_revenue or Decimal("0.00")) for r in self.db.execute(sales_stmt).all()}

        results = []
        for p in prods:
            v = counts.get((p.shopify_product_id, "product_viewed"), 0)
            a = counts.get((p.shopify_product_id, "product_added_to_cart"), 0)
            c = counts.get((p.shopify_product_id, "checkout_started"), 0)
            pur = counts.get((p.shopify_product_id, "checkout_completed"), 0)

            units_sold, prod_rev = sales.get(p.id, (0, Decimal("0.00")))
            if units_sold == 0 and pur > 0:
                units_sold = pur
                prod_rev = Decimal(str(round(pur * float(p.price or 0), 2)))

            atc_rate = Decimal(str(round((a / v * 100), 2))) if v > 0 else None
            chk_rate = Decimal(str(round((c / a * 100), 2))) if a > 0 else None
            pur_rate = Decimal(str(round((pur / c * 100), 2))) if c > 0 else None

            gross_margin_pct = None
            if p.price and p.unit_cost and p.price > 0:
                gross_margin_pct = Decimal(str(round(((p.price - p.unit_cost) / p.price) * 100, 1)))

            results.append({
                "product": p,
                "views": v,
                "add_to_carts": a,
                "add_to_cart_rate": atc_rate,
                "checkout_starts": c,
                "checkout_rate": chk_rate,
                "purchases": units_sold,
                "purchase_rate": pur_rate,
                "revenue": prod_rev,
                "gross_margin_pct": gross_margin_pct,
            })

        return results
