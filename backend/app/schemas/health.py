"""Health check response schema."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    version: str = Field(examples=["0.1.0"])
    app_env: str = Field(examples=["development"])
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Lightweight dependency status map (postgres/redis/qdrant).",
    )
