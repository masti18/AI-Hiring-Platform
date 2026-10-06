"""Company schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    auto_approve_gate1: bool
    auto_approve_gate2: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    auto_approve_gate1: bool | None = None
    auto_approve_gate2: bool | None = None
    notes: str | None = None
