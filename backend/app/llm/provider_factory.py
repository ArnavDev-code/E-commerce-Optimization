"""LLM Provider factory returning configured or fallback instance."""

from __future__ import annotations

from typing import Optional
from app.config import get_settings
from app.llm.base import BaseLLMProvider
from app.llm.providers.fallback import FallbackLLMProvider
from app.llm.providers.gemini_provider import GeminiLLMProvider
from app.llm.providers.openai_provider import OpenAILLMProvider


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """Instantiate the requested or configured LLM provider with fallback safety."""
    settings = get_settings()
    name = (provider_name or settings.LLM_PROVIDER or "fallback").lower().strip()

    if name == "gemini":
        gemini = GeminiLLMProvider()
        if gemini.is_available():
            return gemini
        return FallbackLLMProvider()

    elif name == "openai":
        openai_p = OpenAILLMProvider()
        if openai_p.is_available():
            return openai_p
        return FallbackLLMProvider()

    return FallbackLLMProvider()
