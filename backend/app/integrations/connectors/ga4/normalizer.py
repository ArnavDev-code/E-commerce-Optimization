"""Normalizer for Google Analytics 4 report data into GA4Metric models."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List
import uuid

logger = logging.getLogger(__name__)


def parse_ga4_date(date_str: str) -> date:
    """Parse GA4 date format (YYYYMMDD) into Python date object."""
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except Exception:
        return date.today()


def normalize_ga4_report(
    store_id: uuid.UUID,
    report_data: Dict[str, Any],
    dimension_type: str = "overall",
    dimension_name_key: str = "date",
) -> List[Dict[str, Any]]:
    """Normalize raw GA4 runReport response into list of GA4Metric attribute dictionaries.
    
    Args:
        store_id: Connected store UUID.
        report_data: Raw JSON response from runReport.
        dimension_type: 'overall' | 'device' | 'source' | 'product'.
        dimension_name_key: Secondary dimension name (e.g. 'deviceCategory', 'sessionDefaultChannelGroup').
    """
    dimension_headers = [d.get("name", "") for d in report_data.get("dimensionHeaders", [])]
    metric_headers = [m.get("name", "") for m in report_data.get("metricHeaders", [])]
    rows = report_data.get("rows", [])

    normalized: List[Dict[str, Any]] = []

    for row in rows:
        dim_values = [v.get("value", "") for v in row.get("dimensionValues", [])]
        met_values = [v.get("value", "0") for v in row.get("metricValues", [])]

        dim_map = dict(zip(dimension_headers, dim_values))
        met_map = dict(zip(metric_headers, met_values))

        # Parse date
        report_date_str = dim_map.get("date", "")
        report_date = parse_ga4_date(report_date_str)

        # Parse dimension value
        dim_value = None
        if dimension_type != "overall" and dimension_name_key in dim_map:
            dim_value = dim_map[dimension_name_key].lower().strip()

        # Parse metrics with safety fallbacks
        def _get_int(key: str) -> int:
            try:
                return int(float(met_map.get(key, 0)))
            except (ValueError, TypeError):
                return 0

        def _get_decimal(key: str) -> Decimal:
            try:
                return Decimal(str(round(float(met_map.get(key, 0)), 2)))
            except (ValueError, TypeError):
                return Decimal("0.00")

        record = {
            "store_id": store_id,
            "report_date": report_date,
            "dimension_type": dimension_type,
            "dimension_value": dim_value,
            "sessions": _get_int("sessions"),
            "users": _get_int("totalUsers") or _get_int("activeUsers"),
            "page_views": _get_int("screenPageViews"),
            "product_views": _get_int("itemsViewed") or _get_int("view_item"),
            "add_to_carts": _get_int("itemsAddedToCart") or _get_int("add_to_cart"),
            "checkouts": _get_int("itemsCheckedOut") or _get_int("begin_checkout"),
            "purchases": _get_int("ecommercePurchases") or _get_int("purchase"),
            "revenue": _get_decimal("purchaseRevenue"),
        }
        normalized.append(record)

    return normalized
