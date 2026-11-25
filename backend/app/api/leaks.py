"""Revenue leak detection and monitoring API."""

import uuid
from datetime import date, timedelta
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_store
from app.database import get_db
from app.engine.diagnosis_engine import DiagnosisEngine
from app.engine.leak_detector import LeakDetectionConfig, LeakDetector
from app.models.leak import AIDiagnosis, DetectedLeak
from app.models.product import Product
from app.models.store import ConnectedStore
from app.schemas.analytics import DetectedLeakResponse, LeakDetectRequest
from app.schemas.recommendations import AIDiagnosisResponse

router = APIRouter(prefix="/leaks", tags=["Revenue Leaks"])


@router.get("", response_model=List[DetectedLeakResponse])
def list_detected_leaks(
    status_filter: Annotated[str | None, Query(description="new|reviewed|resolved|dismissed")] = None,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> List[DetectedLeakResponse]:
    """List detected revenue and conversion leaks for the authenticated store."""
    query = (
        select(DetectedLeak, Product)
        .outerjoin(Product, Product.id == DetectedLeak.product_id)
        .where(DetectedLeak.store_id == store.id)
        .order_by(DetectedLeak.detected_at.desc())
    )

    if status_filter:
        query = query.where(DetectedLeak.status == status_filter)

    rows = db.execute(query).all()

    responses = []
    for leak, prod in rows:
        resp = DetectedLeakResponse(
            id=leak.id,
            store_id=leak.store_id,
            product_id=leak.product_id,
            product_title=prod.title if prod else "Store Overall",
            product_handle=prod.handle if prod else None,
            product_price=prod.price if prod else None,
            product_cost=prod.unit_cost if prod else None,
            leak_type=leak.leak_type,
            metric_affected=leak.metric_affected,
            observed_value=leak.observed_value,
            baseline_value=leak.baseline_value,
            sample_size=leak.sample_size,
            period_start=leak.period_start,
            period_end=leak.period_end,
            severity=leak.severity,
            confidence_score=leak.confidence_score,
            evidence_quality=leak.evidence_quality,
            reason=leak.reason,
            status=leak.status,
            detected_at=leak.detected_at,
        )
        responses.append(resp)

    return responses


@router.get("/{leak_id}", response_model=DetectedLeakResponse)
def get_leak_detail(
    leak_id: uuid.UUID,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> DetectedLeakResponse:
    """Get single leak details and associated diagnostic context."""
    row = db.execute(
        select(DetectedLeak, Product)
        .outerjoin(Product, Product.id == DetectedLeak.product_id)
        .where(DetectedLeak.id == leak_id, DetectedLeak.store_id == store.id)
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detected leak not found in this store",
        )

    leak, prod = row
    return DetectedLeakResponse(
        id=leak.id,
        store_id=leak.store_id,
        product_id=leak.product_id,
        product_title=prod.title if prod else "Store Overall",
        product_handle=prod.handle if prod else None,
        product_price=prod.price if prod else None,
        product_cost=prod.unit_cost if prod else None,
        leak_type=leak.leak_type,
        metric_affected=leak.metric_affected,
        observed_value=leak.observed_value,
        baseline_value=leak.baseline_value,
        sample_size=leak.sample_size,
        period_start=leak.period_start,
        period_end=leak.period_end,
        severity=leak.severity,
        confidence_score=leak.confidence_score,
        evidence_quality=leak.evidence_quality,
        reason=leak.reason,
        status=leak.status,
        detected_at=leak.detected_at,
    )


@router.post("/detect", response_model=List[DetectedLeakResponse])
def run_leak_detection(
    payload: LeakDetectRequest,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> List[DetectedLeakResponse]:
    """Execute the 4-rule leak detection engine across store products."""
    end_date = date.today()
    start_date = end_date - timedelta(days=payload.days)

    config = LeakDetectionConfig(min_sample_views=payload.min_sample_size)
    detector = LeakDetector(db, store.id, config=config)

    detected = detector.run_detection(start_date, end_date, save_to_db=True)

    # Return refreshed list
    return list_detected_leaks(status_filter=None, store=store, db=db)


@router.post("/{leak_id}/diagnose", response_model=AIDiagnosisResponse)
def diagnose_leak_endpoint(
    leak_id: uuid.UUID,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> AIDiagnosisResponse:
    """Run diagnosis engine for the given leak and return structured verified facts vs hypotheses."""
    engine = DiagnosisEngine(db, store.id)
    try:
        diagnosis = engine.diagnose_leak(leak_id, save_to_db=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return AIDiagnosisResponse.model_validate(diagnosis)


@router.get("/{leak_id}/diagnosis", response_model=AIDiagnosisResponse)
def get_leak_diagnosis_endpoint(
    leak_id: uuid.UUID,
    store: ConnectedStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> AIDiagnosisResponse:
    """Get the latest diagnosis for a specific leak, generating one if not yet created."""
    leak = db.execute(
        select(DetectedLeak).where(DetectedLeak.id == leak_id, DetectedLeak.store_id == store.id)
    ).scalar_one_or_none()
    if not leak:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leak not found in this store")

    diag = db.execute(
        select(AIDiagnosis)
        .where(AIDiagnosis.leak_id == leak.id)
        .order_by(AIDiagnosis.created_at.desc())
    ).scalar_one_or_none()

    if not diag:
        engine = DiagnosisEngine(db, store.id)
        diag = engine.diagnose_leak(leak_id, save_to_db=True)

    return AIDiagnosisResponse.model_validate(diag)

