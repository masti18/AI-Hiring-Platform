"""Health checks against infra dependencies."""

from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine


async def check_postgres() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 — health endpoint must never raise
        return f"error: {exc.__class__.__name__}"


async def check_redis() -> str:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        try:
            pong = await client.ping()
            return "ok" if pong else "error: no pong"
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


async def check_qdrant() -> str:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.qdrant_url}/readyz")
            if response.status_code == 200:
                return "ok"
            return f"error: status_{response.status_code}"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


async def collect_service_status() -> dict[str, Any]:
    return {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "qdrant": await check_qdrant(),
    }
