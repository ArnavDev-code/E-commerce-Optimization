"""Gemini LLM Provider implementation with strict validation and graceful fallback."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import get_settings
from app.llm.base import (
    BaseLLMProvider,
    ConfirmedObservation,
    DiagnosisOutput,
    HypothesisExplanation,
    RecommendationItem,
)
from app.llm.providers.fallback import FallbackLLMProvider

logger = logging.getLogger(__name__)


class GeminiLLMProvider(BaseLLMProvider):
    """Integrates Google Gemini API with fallback guarantees."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.LLM_MODEL or "gemini-2.0-flash"
        self._fallback = FallbackLLMProvider()

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def diagnose_leak(self, context: Dict[str, Any]) -> DiagnosisOutput:
        if not self.is_available():
            return self._fallback.diagnose_leak(context)

        prompt = (
            "You are an expert Shopify CRO and e-commerce analytics diagnostician.\n"
            "Analyze the following detected revenue leak and generate a structured diagnosis.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. NEVER invent or fabricate metrics. Treat all provided observed values, sample sizes, and baselines as immutable verified facts.\n"
            "2. STRICTLY separate verified facts (in 'observations') from speculative root-cause hypotheses (in 'hypotheses').\n"
            "3. Every hypothesis MUST be explicitly marked with its likelihood and supporting signals.\n"
            "4. Return ONLY valid JSON conforming to the requested schema.\n\n"
            f"CONTEXT DATA:\n{json.dumps(context, indent=2, default=str)}\n\n"
            "Required JSON Schema:\n"
            "{\n"
            '  "issue_summary": "string",\n'
            '  "observations": [{"metric": "str", "observed_value": "str", "baseline_value": "str", "sample_size": int, "context": "str"}],\n'
            '  "hypotheses": [{"hypothesis": "str", "supporting_signals": ["str"], "likelihood": "high|medium|low"}],\n'
            '  "missing_information": ["str"],\n'
            '  "recommended_investigation": ["str"],\n'
            '  "recommended_actions": ["str"],\n'
            '  "confidence_level": "high|medium|low"\n'
            "}"
        )

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2,
                },
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                return DiagnosisOutput.model_validate(parsed)
        except Exception as exc:
            logger.warning("Gemini diagnosis generation failed (%s); falling back to deterministic engine.", exc)
            return self._fallback.diagnose_leak(context)

    def generate_recommendations(self, context: Dict[str, Any]) -> List[RecommendationItem]:
        if not self.is_available():
            return self._fallback.generate_recommendations(context)

        prompt = (
            "You are an expert Shopify conversion rate optimization (CRO) engineer.\n"
            "Generate actionable, evidence-backed recommendations for this store leak.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. NEVER promise guaranteed revenue recovery.\n"
            "2. All recommendations must be realistic for a Shopify D2C store.\n"
            "3. Return ONLY a JSON list of recommendation objects conforming to the schema.\n\n"
            f"CONTEXT DATA:\n{json.dumps(context, indent=2, default=str)}\n\n"
            "Required JSON Schema: List of objects with keys:\n"
            "title (str), target_stage ('product_page'|'cart'|'checkout'|'post_purchase'), "
            "expected_direction ('increase'|'decrease'), detected_problem (str), suggested_action (str), "
            "business_reason (str), implementation_effort ('low'|'medium'|'high'), "
            "confidence_level ('high'|'medium'|'low'), risks_or_prerequisites (list of str), metric_to_monitor (str)."
        )

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2,
                },
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                if isinstance(parsed, dict) and "recommendations" in parsed:
                    parsed = parsed["recommendations"]
                if isinstance(parsed, list):
                    return [RecommendationItem.model_validate(item) for item in parsed]
                raise ValueError("Expected JSON array")
        except Exception as exc:
            logger.warning("Gemini recommendation generation failed (%s); falling back to deterministic engine.", exc)
            return self._fallback.generate_recommendations(context)
