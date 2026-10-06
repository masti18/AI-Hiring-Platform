"""Role / hiring-brief intake schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.rules import RulePredicate


class RoleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=50)
    brief_text: str = Field(..., min_length=10)
    # Optional explicit filters; if omitted, intake service may extract via LLM
    stated_filters: list[RulePredicate] = Field(default_factory=list)
    hidden_filters: list[RulePredicate] = Field(default_factory=list)
    extract_filters: bool = Field(
        default=False,
        description="If true, LLM extracts stated/hidden predicates from brief_text.",
    )


class RoleUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    brief_text: str | None = Field(default=None, min_length=10)
    stated_filters: list[RulePredicate] | None = None
    hidden_filters: list[RulePredicate] | None = None
    status: str | None = None


class JobDescription(BaseModel):
    """Structured JD — never includes hidden filter fields."""

    title: str
    summary: str
    responsibilities: list[str] = Field(default_factory=list)
    required_qualifications: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    location: str | None = None
    employment_type: str | None = None
    benefits: list[str] = Field(default_factory=list)
    stated_requirements: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoleResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    status: str
    brief_text: str
    hiring_brief: dict[str, Any]
    stated_filters: list[dict[str, Any]]
    hidden_filters: list[dict[str, Any]]
    jd: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateJDResponse(BaseModel):
    role_id: UUID
    jd: JobDescription
    provider: str
    model: str
    stub: bool = False


class PipelineRunResponse(BaseModel):
    id: UUID
    company_id: UUID
    role_id: UUID
    status: str
    graph_state: dict[str, Any]
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
