"""Application configuration loaded from environment variables and .env file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from project root or backend folder if present
env_paths = [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break


class Settings(BaseModel):
    """Central configuration for FunnelLeak AI."""

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./funnelleak.db"
        )
    )

    # ── Security ──────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv(
            "SECRET_KEY", "dev-secret-change-in-production"
        )
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    )
    ENCRYPTION_KEY: str = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", "")
    )

    # ── App behaviour ─────────────────────────────────────────────────────
    DEMO_MODE: bool = Field(
        default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
    )
    CORS_ORIGINS: str = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    )

    # ── Shopify ───────────────────────────────────────────────────────────
    SHOPIFY_API_KEY: str = Field(
        default_factory=lambda: os.getenv("SHOPIFY_API_KEY", "")
    )
    SHOPIFY_API_SECRET: str = Field(
        default_factory=lambda: os.getenv("SHOPIFY_API_SECRET", "")
    )
    SHOPIFY_SCOPES: str = Field(
        default_factory=lambda: os.getenv(
            "SHOPIFY_SCOPES",
            "read_products,read_orders,read_inventory,read_locations",
        )
    )
    SHOPIFY_API_VERSION: str = Field(
        default_factory=lambda: os.getenv("SHOPIFY_API_VERSION", "2026-10")
    )
    SHOPIFY_REDIRECT_URI: str = Field(
        default_factory=lambda: os.getenv("SHOPIFY_REDIRECT_URI", "http://localhost:8000/api/shopify/oauth/callback")
    )
    FRONTEND_URL: str = Field(
        default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:5173")
    )

    # ── Google Analytics 4 ────────────────────────────────────────────────
    GA4_CREDENTIALS_PATH: str = Field(
        default_factory=lambda: os.getenv("GA4_CREDENTIALS_PATH", "")
    )
    GA4_PROPERTY_ID: str = Field(
        default_factory=lambda: os.getenv("GA4_PROPERTY_ID", "")
    )

    # ── LLM / AI ──────────────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "fallback")
    )
    OPENAI_API_KEY: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    ANTHROPIC_API_KEY: str = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    GEMINI_API_KEY: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    LLM_MODEL: str = Field(
        default_factory=lambda: os.getenv("LLM_MODEL", "")
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
