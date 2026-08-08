"""Sourcing & scoring contracts.

Candidates are scored against a role's stated + hidden rules. Scores are
structured JSON. Candidate/score data is internal recruiter data.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CandidateInput(BaseModel):
    """A candidate to ingest/score (from a sourcing adapter or direct upload)."""

    external_id: str | None = None
    source: str = "seed"
    name: str = Field(..., min_length=1, max_length=255)
    attributes: dict[str, Any] = Field(default_factory=dict)


class PredicateResult(BaseModel):
    """Outcome of evaluating one rule predicate against a candidate."""

    field: str
    operator: str
    value: Any
    passed: bool
    reason: str | None = None


class CandidateScore(BaseModel):
    """Structured score. `qualified` requires all hidden (hard) rules to pass."""

    overall: float
    qualified: bool
    passed_stated: bool
    passed_hidden: bool
    matched_count: int
    total_count: int
    stated_results: list[PredicateResult] = Field(default_factory=list)
    hidden_results: list[PredicateResult] = Field(default_factory=list)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    role_requirement_id: uuid.UUID
    sourcing_run_id: uuid.UUID | None
    external_id: str | None
    source: str
    name: str
    attributes: dict[str, Any]
    score: dict[str, Any]
    overall_score: float
    status: str
    created_at: datetime
    updated_at: datetime


class GateDecisionModel(BaseModel):
    gate: str
    action: str
    reasoning: str
    policy_result: dict[str, Any] = Field(default_factory=dict)


class SourcingRunRequest(BaseModel):
    """Trigger a sourcing run. Candidates may be supplied directly (e.g. an upload
    or a pre-fetched pool); the sourcing adapter is also queried when configured."""

    limit: int = Field(default=25, ge=1, le=500)
    candidates: list[CandidateInput] = Field(default_factory=list)


class SourcingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    role_requirement_id: uuid.UUID
    status: str
    candidate_count: int
    qualified_count: int
    gate1_decision: GateDecisionModel
    created_at: datetime


class SourcingRunResult(BaseModel):
    """Create response: the run plus the scored candidates it produced."""

    run: SourcingRunResponse
    candidates: list[CandidateResponse] = Field(default_factory=list)
