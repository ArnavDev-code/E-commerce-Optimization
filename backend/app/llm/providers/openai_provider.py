"""OpenAI LLM Provider implementation with strict validation and graceful fallback."""

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


class OpenAILLMProvider(BaseLLMProvider):
    """Integrates OpenAI Chat Completion API with fallback guarantees."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.LLM_MODEL or "gpt-4o-mini"
        self._fallback = FallbackLLMProvider()

    @property
    def provider_name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def diagnose_leak(self, context: Dict[str, Any]) -> DiagnosisOutput:
        if not self.is_available():
            return self._fallback.diagnose_leak(context)

        system_prompt = (
            "You are an expert Shopify CRO and e-commerce analytics diagnostician.\n"
            "Analyze the detected revenue leak and return valid JSON conforming to the schema.\n"
            "CONSTRAINTS:\n"
            "1. NEVER fabricate metrics. All numbers provided are immutable facts.\n"
            "2. Strictly separate verified observations from speculative hypotheses."
        )
        user_prompt = f"CONTEXT DATA:\n{json.dumps(context, indent=2, default=str)}"

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                res.raise_for_status()
                data = res.json()
                raw_text = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw_text)
                return DiagnosisOutput.model_validate(parsed)
        except Exception as exc:
            logger.warning("OpenAI diagnosis generation failed (%s); falling back to deterministic engine.", exc)
            return self._fallback.diagnose_leak(context)

    def generate_recommendations(self, context: Dict[str, Any]) -> List[RecommendationItem]:
        if not self.is_available():
            return self._fallback.generate_recommendations(context)

        system_prompt = (
            "You are an expert Shopify conversion rate optimization (CRO) engineer.\n"
            "Generate actionable, evidence-backed recommendations for this store leak.\n"
            "Return a JSON object with key 'recommendations' containing an array of recommendation objects."
        )
        user_prompt = f"CONTEXT DATA:\n{json.dumps(context, indent=2, default=str)}"

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                res.raise_for_status()
                data = res.json()
                raw_text = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw_text)
                items = parsed.get("recommendations", parsed)
                if isinstance(items, list):
                    return [RecommendationItem.model_validate(item) for item in items]
                raise ValueError("Expected list in recommendations key")
        except Exception as exc:
            logger.warning("OpenAI recommendation generation failed (%s); falling back to deterministic engine.", exc)
            return self._fallback.generate_recommendations(context)
