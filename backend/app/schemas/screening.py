"""AI screening call contracts (Milestone 3).

The evaluation is structured JSON (dimensions + overall + recommendation +
reasoning), consumed by the post-AI-call gate and downstream offer stage.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sourcing import GateDecisionModel

Recommendation = Literal["advance", "hold", "reject"]


class TranscriptTurn(BaseModel):
    speaker: Literal["interviewer", "candidate"]
    text: str = ""


class CallDimension(BaseModel):
    name: str
    score: float
    notes: str | None = None


class CallEvaluation(BaseModel):
    """Structured screening evaluation."""

    overall_score: float
    recommendation: Recommendation
    dimensions: list[CallDimension] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    reasoning: str = ""


class ScreeningCallRequest(BaseModel):
    """Trigger a screening call. Candidate answers drive the (mock) call; a full
    transcript may be supplied directly instead."""

    questions: list[str] | None = None
    answers: list[str] = Field(default_factory=list)
    transcript: list[TranscriptTurn] | None = None


class ScreeningCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    role_requirement_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str
    transcript: list[dict[str, Any]]
    evaluation: CallEvaluation
    overall_score: float
    recommendation: str
    gate2_decision: GateDecisionModel
    providers: dict[str, Any]
    created_at: datetime
    updated_at: datetime
