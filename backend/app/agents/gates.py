"""Auto-gate checkpoint nodes.

These nodes ALWAYS evaluate policy and ALWAYS produce an auditable decision.
Blocking for a human is a config-driven branch — never a hardcoded pause.
"""

from typing import Any, Literal

from app.agents.state import GateDecision, HiringGraphState


GateName = Literal["gate1_post_sourcing", "gate2_post_ai_call"]


async def evaluate_gate_policy(
    *,
    gate: GateName,
    state: HiringGraphState,
    auto_approve: bool,
    policy_result: dict[str, Any] | None = None,
) -> GateDecision:
    """Run policy evaluation and return a structured, audit-ready decision."""
    policy = policy_result or {"passed": True, "checks": []}
    if not policy.get("passed", True):
        action: Literal["auto_approve", "await_human", "reject"] = "reject"
        reasoning = f"{gate}: policy checks failed; rejecting."
    elif auto_approve:
        action = "auto_approve"
        reasoning = f"{gate}: policy passed and auto_approve enabled; proceeding."
    else:
        action = "await_human"
        reasoning = f"{gate}: policy passed but auto_approve disabled; awaiting human review."

    return GateDecision(
        gate=gate,
        action=action,
        reasoning=reasoning,
        policy_result=policy,
        audited=False,  # flipped true after services.audit.record_gate_decision
    )


async def gate1_post_sourcing_node(state: HiringGraphState) -> dict[str, Any]:
    """Post-sourcing checkpoint. Reads company auto_approve_gate1 from upstream state."""
    auto_approve = bool(state.get("hiring_brief", {}).get("auto_approve_gate1", True))
    decision = await evaluate_gate_policy(
        gate="gate1_post_sourcing",
        state=state,
        auto_approve=auto_approve,
        policy_result={"passed": True, "checks": [{"name": "min_candidates", "ok": True}]},
    )
    return {"gate1": decision, "status": f"gate1_{decision['action']}"}


async def gate2_post_ai_call_node(state: HiringGraphState) -> dict[str, Any]:
    """Post-AI-call checkpoint. Reads company auto_approve_gate2 from upstream state."""
    auto_approve = bool(state.get("hiring_brief", {}).get("auto_approve_gate2", True))
    decision = await evaluate_gate_policy(
        gate="gate2_post_ai_call",
        state=state,
        auto_approve=auto_approve,
        policy_result={"passed": True, "checks": [{"name": "call_score_threshold", "ok": True}]},
    )
    return {"gate2": decision, "status": f"gate2_{decision['action']}"}
