"""Top-level API router."""

from fastapi import APIRouter

from app.api import health, requirements, sourcing

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(requirements.router)
api_router.include_router(sourcing.router)
