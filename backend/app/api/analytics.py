"""Analytics endpoints for store-level overview and funnel visualizations."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_store
from app.database import get_db
from app.engine.analytics_engine import AnalyticsEngine
from app.models.store import ConnectedStore
from app.schemas.analytics import AnalyticsOverviewResponse, FunnelAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    days: Annotated[int, Query(ge=7, le=90, description="Reporting period in days")] = 30,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """Get calculated store-level KPIs (sessions, revenue, AOV, conversion rate, gross profit).
    
    All figures are computed deterministically from underlying events and orders.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    engine = AnalyticsEngine(db, store.id)
    return engine.compute_overview_kpis(start_date, end_date)


@router.get("/funnel", response_model=FunnelAnalyticsResponse)
def get_funnel_analytics(
    days: Annotated[int, Query(ge=7, le=90, description="Reporting period in days")] = 30,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> FunnelAnalyticsResponse:
    """Get calculated funnel progression stages and device/traffic segmentations."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    engine = AnalyticsEngine(db, store.id)
    return engine.compute_funnel_breakdown(start_date, end_date)
