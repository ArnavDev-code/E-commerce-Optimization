"""Recommendation and Diagnosis Pydantic API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AIDiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    leak_id: uuid.UUID
    provider: str
    issue_summary: str
    evidence: List[Any]
    possible_explanations: List[Any]
    missing_information: Optional[List[str]] = None
    recommended_investigation: Optional[List[str]] = None
    further_checks: Optional[List[str]] = None
    recommended_actions: List[str]
    confidence_level: str
    is_fallback: bool
    created_at: datetime


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    leak_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    product_title: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_cost: Optional[Decimal] = None
    title: str
    target_stage: str
    expected_direction: str
    detected_problem: str
    supporting_evidence: Any
    suggested_action: str
    business_reason: str
    potential_impact_estimate: Optional[Decimal] = None
    implementation_effort: str
    confidence_level: str
    priority_score: Optional[Decimal] = None
    priority_breakdown: Optional[Any] = None
    risks_or_prerequisites: Optional[Any] = None
    priority: str
    metric_to_monitor: str
    status: str
    merchant_notes: Optional[str] = None
    created_at: datetime


class RecommendationStatusUpdate(BaseModel):
    status: str = Field(description="new|pending|accepted|approved|rejected|in_progress|completed")
    merchant_notes: Optional[str] = None


class RecommendationGenerateRequest(BaseModel):
    leak_id: Optional[uuid.UUID] = None
