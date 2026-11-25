"""LLM Provider abstraction and structured diagnosis/recommendation contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConfirmedObservation(BaseModel):
    """Fact verified directly from store analytics or database records."""
    metric: str
    observed_value: str
    baseline_value: str
    sample_size: int
    context: str = ""


class HypothesisExplanation(BaseModel):
    """Potential reason requiring merchant validation; strictly distinguished from facts."""
    hypothesis: str
    supporting_signals: List[str] = Field(default_factory=list)
    likelihood: str = Field(default="medium", description="high|medium|low")


class DiagnosisOutput(BaseModel):
    """Structured output returned by diagnosis engine / LLM provider."""
    issue_summary: str
    observations: List[ConfirmedObservation] = Field(default_factory=list)
    hypotheses: List[HypothesisExplanation] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_investigation: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    confidence_level: str = Field(default="medium", description="high|medium|low")


class RecommendationItem(BaseModel):
    """Structured CRO recommendation produced by recommendation engine / LLM."""
    title: str
    target_stage: str = Field(default="product_page", description="product_page|cart|checkout|post_purchase")
    expected_direction: str = Field(default="increase", description="increase|decrease")
    detected_problem: str
    suggested_action: str
    business_reason: str
    implementation_effort: str = Field(default="medium", description="low|medium|high")
    confidence_level: str = Field(default="medium", description="high|medium|low")
    risks_or_prerequisites: List[str] = Field(default_factory=list)
    metric_to_monitor: str


class BaseLLMProvider(ABC):
    """Abstract interface for LLM diagnosis and recommendation generation."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'fallback', 'openai', 'gemini')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider credentials and network prerequisites are configured."""
        pass

    @abstractmethod
    def diagnose_leak(self, context: Dict[str, Any]) -> DiagnosisOutput:
        """Generate structured diagnosis distinguishing verified facts from hypotheses."""
        pass

    @abstractmethod
    def generate_recommendations(self, context: Dict[str, Any]) -> List[RecommendationItem]:
        """Generate prioritized CRO recommendations tailored to context."""
        pass
