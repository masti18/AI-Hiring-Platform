"""Shared LangGraph state for the hiring pipeline."""

from typing import Any, Literal, TypedDict


class GateDecision(TypedDict, total=False):
    gate: Literal["gate1_post_sourcing", "gate2_post_ai_call"]
    action: Literal["auto_approve", "await_human", "reject"]
    reasoning: str
    policy_result: dict[str, Any]
    audited: bool


class HiringGraphState(TypedDict, total=False):
    """Pipeline state. AI outputs live as structured JSON for downstream consumption."""

    company_id: str
    role_id: str
    run_id: str

    hiring_brief: dict[str, Any]
    stated_filters: list[dict[str, Any]]
    hidden_filters: list[dict[str, Any]]

    jd: dict[str, Any]
    candidates: list[dict[str, Any]]
    scores: list[dict[str, Any]]
    call_evaluations: list[dict[str, Any]]
    offer: dict[str, Any]

    gate1: GateDecision
    gate2: GateDecision

    errors: list[str]
    status: str
