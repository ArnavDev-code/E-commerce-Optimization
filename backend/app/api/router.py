"""Central API router registry."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.analytics import router as analytics_router
from app.api.products import router as products_router
from app.api.leaks import router as leaks_router
from app.api.recommendations import router as recommendations_router
from app.api.shopify import router as shopify_router
from app.api.ga4 import router as ga4_router

api_router = APIRouter(prefix="/api")

# Active Routers
api_router.include_router(auth_router)
api_router.include_router(analytics_router)
api_router.include_router(products_router)
api_router.include_router(leaks_router)
api_router.include_router(recommendations_router)
api_router.include_router(shopify_router)
api_router.include_router(ga4_router)


@api_router.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Basic service health check."""
    return {"status": "ok", "service": "FunnelLeak AI Backend"}
