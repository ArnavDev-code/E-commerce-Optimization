"""FunnelLeak AI — FastAPI Backend Application Entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.database import SessionLocal, create_tables
from app.demo.seed_data import seed_demo_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("funnelleak")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: manage database tables and initial demo seeding."""
    import os
    if not os.environ.get("TESTING") and not os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("Initializing FunnelLeak AI database tables...")
        create_tables()

        if settings.DEMO_MODE:
            logger.info("DEMO_MODE is active. Bootstrapping realistic demo store dataset...")
            db = SessionLocal()
            try:
                seed_result = seed_demo_data(db, force_reset=False)
                logger.info("Demo bootstrap result: %s", seed_result.get("status"))
            except Exception as e:
                logger.error("Error bootstrapping demo data: %s", e, exc_info=True)
            finally:
                db.close()

    yield
    logger.info("Shutting down FunnelLeak AI backend...")


app = FastAPI(
    title="FunnelLeak AI API",
    description=(
        "Shopify revenue recovery intelligence platform. "
        "Detects product-level funnel dropoffs, diagnoses root causes via verified evidence, "
        "recommends prioritized CRO interventions, and tracks experiment outcomes."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS setup for frontend local development and production
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main API router
app.include_router(api_router)


@app.get("/", tags=["System"])
def root_status() -> dict[str, str]:
    """Root status endpoint."""
    return {
        "app": "FunnelLeak AI API",
        "version": "0.1.0",
        "docs": "/docs",
        "demo_mode": str(settings.DEMO_MODE),
    }
