"""Audit trail service.

Gate decisions MUST be persisted with decision + reasoning. Domain tables for
audit land in Milestone 1 migrations; this service defines the contract now.
"""

from typing import Any
from uuid import uuid4

from app.agents.state import GateDecision


async def record_gate_decision(
    *,
    company_id: str,
    run_id: str,
    decision: GateDecision,
    actor: str = "system",
) -> dict[str, Any]:
    """Persist a gate decision. Returns the audit payload (DB write in Milestone 1)."""
    record = {
        "id": str(uuid4()),
        "company_id": company_id,
        "run_id": run_id,
        "gate": decision.get("gate"),
        "action": decision.get("action"),
        "reasoning": decision.get("reasoning"),
        "policy_result": decision.get("policy_result", {}),
        "actor": actor,
        "persisted": False,  # flipped when audit table migration exists
    }
    decision["audited"] = True
    return record
