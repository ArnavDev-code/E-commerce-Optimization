"""Recommendations API for FunnelLeak AI.

Provides prioritized CRO recommendations with multi-factor scoring breakdowns,
profit impact estimates, and merchant approval workflows.
"""

from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_store
from app.database import get_db
from app.engine.recommendation_engine import RecommendationEngine
from app.models.leak import Recommendation
from app.models.product import Product
from app.models.store import ConnectedStore
from app.schemas.recommendations import (
    RecommendationGenerateRequest,
    RecommendationResponse,
    RecommendationStatusUpdate,
)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=List[RecommendationResponse])
def list_recommendations(
    priority: Annotated[Optional[str], Query(description="high|medium|low")] = None,
    rec_status: Annotated[Optional[str], Query(alias="status", description="new|accepted|rejected|in_progress|completed")] = None,
    stage: Annotated[Optional[str], Query(description="product_page|cart|checkout|post_purchase")] = None,
    product_id: Annotated[Optional[uuid.UUID], Query()] = None,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> List[RecommendationResponse]:
    """List prioritized CRO recommendations for the authenticated store."""
    query = (
        select(Recommendation, Product)
        .outerjoin(Product, Product.id == Recommendation.product_id)
        .where(Recommendation.store_id == store.id)
    )

    if priority:
        query = query.where(Recommendation.priority == priority.lower())
    if rec_status:
        query = query.where(Recommendation.status == rec_status.lower())
    if stage:
        query = query.where(Recommendation.target_stage == stage.lower())
    if product_id:
        query = query.where(Recommendation.product_id == product_id)

    query = query.order_by(Recommendation.priority_score.desc().nullslast(), Recommendation.created_at.desc())
    rows = db.execute(query).all()

    responses = []
    for rec, prod in rows:
        responses.append(
            RecommendationResponse(
                id=rec.id,
                store_id=rec.store_id,
                leak_id=rec.leak_id,
                product_id=rec.product_id,
                product_title=prod.title if prod else None,
                product_price=prod.price if prod else None,
                product_cost=prod.unit_cost if prod else None,
                title=rec.title,
                target_stage=rec.target_stage,
                expected_direction=rec.expected_direction,
                detected_problem=rec.detected_problem,
                supporting_evidence=rec.supporting_evidence,
                suggested_action=rec.suggested_action,
                business_reason=rec.business_reason,
                potential_impact_estimate=rec.potential_impact_estimate,
                implementation_effort=rec.implementation_effort,
                confidence_level=rec.confidence_level,
                priority_score=rec.priority_score,
                priority_breakdown=rec.priority_breakdown,
                risks_or_prerequisites=rec.risks_or_prerequisites,
                priority=rec.priority,
                metric_to_monitor=rec.metric_to_monitor,
                status=rec.status,
                merchant_notes=rec.merchant_notes,
                created_at=rec.created_at,
            )
        )
    return responses


@router.get("/{rec_id}", response_model=RecommendationResponse)
def get_recommendation_detail(
    rec_id: uuid.UUID,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Retrieve details and transparent scoring breakdown for a single recommendation."""
    row = db.execute(
        select(Recommendation, Product)
        .outerjoin(Product, Product.id == Recommendation.product_id)
        .where(Recommendation.id == rec_id, Recommendation.store_id == store.id)
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found in this store",
        )

    rec, prod = row
    return RecommendationResponse(
        id=rec.id,
        store_id=rec.store_id,
        leak_id=rec.leak_id,
        product_id=rec.product_id,
        product_title=prod.title if prod else None,
        product_price=prod.price if prod else None,
        product_cost=prod.unit_cost if prod else None,
        title=rec.title,
        target_stage=rec.target_stage,
        expected_direction=rec.expected_direction,
        detected_problem=rec.detected_problem,
        supporting_evidence=rec.supporting_evidence,
        suggested_action=rec.suggested_action,
        business_reason=rec.business_reason,
        potential_impact_estimate=rec.potential_impact_estimate,
        implementation_effort=rec.implementation_effort,
        confidence_level=rec.confidence_level,
        priority_score=rec.priority_score,
        priority_breakdown=rec.priority_breakdown,
        risks_or_prerequisites=rec.risks_or_prerequisites,
        priority=rec.priority,
        metric_to_monitor=rec.metric_to_monitor,
        status=rec.status,
        merchant_notes=rec.merchant_notes,
        created_at=rec.created_at,
    )


@router.post("/generate", response_model=List[RecommendationResponse])
def generate_recommendations(
    payload: RecommendationGenerateRequest,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> List[RecommendationResponse]:
    """Trigger generation and prioritization of recommendations for active leaks."""
    engine = RecommendationEngine(db, store.id)
    if payload.leak_id:
        engine.generate_recommendations_for_leak(payload.leak_id, save_to_db=True)
    else:
        engine.generate_all_recommendations(save_to_db=True)

    return list_recommendations(
        priority=None,
        rec_status=None,
        stage=None,
        product_id=None,
        store=store,
        db=db,
    )


@router.patch("/{rec_id}/status", response_model=RecommendationResponse)
def update_recommendation_status(
    rec_id: uuid.UUID,
    payload: RecommendationStatusUpdate,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Update recommendation workflow status (accept, reject, in progress, complete)."""
    rec = db.execute(
        select(Recommendation).where(
            Recommendation.id == rec_id,
            Recommendation.store_id == store.id,
        )
    ).scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found in this store",
        )

    # Normalize status: accept/approved/accepted -> accepted
    raw_status = payload.status.lower().strip()
    status_map = {
        "accept": "accepted",
        "approved": "accepted",
        "approve": "accepted",
        "reject": "rejected",
        "rejected": "rejected",
        "new": "new",
        "pending": "new",
        "in_progress": "in_progress",
        "completed": "completed",
    }
    normalized_status = status_map.get(raw_status, raw_status)

    rec.status = normalized_status
    if payload.merchant_notes is not None:
        rec.merchant_notes = payload.merchant_notes

    db.commit()
    db.refresh(rec)

    prod = None
    if rec.product_id:
        prod = db.execute(select(Product).where(Product.id == rec.product_id)).scalar_one_or_none()

    return RecommendationResponse(
        id=rec.id,
        store_id=rec.store_id,
        leak_id=rec.leak_id,
        product_id=rec.product_id,
        product_title=prod.title if prod else None,
        product_price=prod.price if prod else None,
        product_cost=prod.unit_cost if prod else None,
        title=rec.title,
        target_stage=rec.target_stage,
        expected_direction=rec.expected_direction,
        detected_problem=rec.detected_problem,
        supporting_evidence=rec.supporting_evidence,
        suggested_action=rec.suggested_action,
        business_reason=rec.business_reason,
        potential_impact_estimate=rec.potential_impact_estimate,
        implementation_effort=rec.implementation_effort,
        confidence_level=rec.confidence_level,
        priority_score=rec.priority_score,
        priority_breakdown=rec.priority_breakdown,
        risks_or_prerequisites=rec.risks_or_prerequisites,
        priority=rec.priority,
        metric_to_monitor=rec.metric_to_monitor,
        status=rec.status,
        merchant_notes=rec.merchant_notes,
        created_at=rec.created_at,
    )
