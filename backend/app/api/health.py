"""Health endpoints."""

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.services.health import collect_service_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    services = await collect_service_status()
    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthResponse(
        status=overall,
        version=__version__,
        app_env=settings.app_env,
        services=services,
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Process liveness — does not probe dependencies."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        app_env=settings.app_env,
        services={},
    )
