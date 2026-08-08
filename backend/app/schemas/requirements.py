"""Requirement Intake contracts.

Turns a raw hiring brief into a structured role: separated stated/hidden filters
and a structured job description. Hidden filters are internal-only and are never
included in the external job-description response.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rules import RulePredicate


class JobDescription(BaseModel):
    """Structured JD. Built only from stated (external) information."""

    title: str
    summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    location: str | None = None
    employment_type: str | None = None


class RequirementIntakeRequest(BaseModel):
    """Input to the intake pipeline.

    `raw_brief` is the free-text hiring brief. Callers may also pass explicit
    structured filters; inline `HIDDEN:` / `STATED:` directives in the brief are
    parsed too. Hidden filters never leak into generated JD text.
    """

    company_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    raw_brief: str = Field(..., min_length=1)
    stated_filters: list[RulePredicate] = Field(default_factory=list)
    hidden_filters: list[RulePredicate] = Field(default_factory=list)
    location: str | None = None
    employment_type: str | None = None


class IntakeResult(BaseModel):
    """Pure (DB-free) output of the extraction step."""

    stated_filters: list[RulePredicate] = Field(default_factory=list)
    hidden_filters: list[RulePredicate] = Field(default_factory=list)
    job_description: JobDescription
    llm_metadata: dict = Field(default_factory=dict)


class RoleRequirementResponse(BaseModel):
    """Full internal view of a stored role requirement (includes hidden filters)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    status: str
    raw_brief: str
    stated_filters: list[RulePredicate] = Field(default_factory=list)
    hidden_filters: list[RulePredicate] = Field(default_factory=list)
    job_description: JobDescription
    created_at: datetime
    updated_at: datetime


class ExternalJobDescriptionResponse(BaseModel):
    """External-facing JD. Intentionally omits hidden filters entirely."""

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    job_description: JobDescription
    stated_filters: list[RulePredicate] = Field(default_factory=list)
