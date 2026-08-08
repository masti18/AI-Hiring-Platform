"""Audit trail service.

Gate decisions MUST be persisted with decision + reasoning. The audit table lands
in the Milestone 1 migration; `record_audit_event` persists structured records to
it. `record_gate_decision` keeps its in-memory contract for the (not-yet-wired)
graph and can be persisted via `record_audit_event` by callers that hold a session.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.agents.state import GateDecision
from app.models.audit_log import AuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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


async def record_audit_event(
    session: "AsyncSession",
    *,
    company_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    actor: str = "system",
) -> AuditLog:
    """Persist a structured audit record. Flushes so the caller sees the row id.

    The surrounding unit of work is responsible for committing.
    """
    entry = AuditLog(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload=payload or {},
        actor=actor,
    )
    session.add(entry)
    await session.flush()
    return entry
