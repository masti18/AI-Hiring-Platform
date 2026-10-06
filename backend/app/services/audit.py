"""Audit trail service.

Gate decisions MUST be persisted with decision + reasoning.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import GateDecision
from app.models.audit import AuditEvent


async def record_event(
    db: AsyncSession,
    *,
    company_id: UUID,
    event_type: str,
    actor: str = "system",
    run_id: UUID | None = None,
    role_id: UUID | None = None,
    gate: str | None = None,
    action: str | None = None,
    reasoning: str | None = None,
    policy_result: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        company_id=company_id,
        run_id=run_id,
        role_id=role_id,
        event_type=event_type,
        gate=gate,
        action=action,
        reasoning=reasoning,
        policy_result=policy_result or {},
        payload=payload or {},
        actor=actor,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def record_gate_decision(
    db: AsyncSession | None = None,
    *,
    company_id: str,
    run_id: str,
    decision: GateDecision,
    actor: str = "system",
    role_id: str | None = None,
) -> dict[str, Any]:
    """Persist a gate decision. When db is provided, writes to audit_events."""
    record = {
        "company_id": company_id,
        "run_id": run_id,
        "role_id": role_id,
        "gate": decision.get("gate"),
        "action": decision.get("action"),
        "reasoning": decision.get("reasoning"),
        "policy_result": decision.get("policy_result", {}),
        "actor": actor,
        "persisted": False,
    }
    if db is not None:
        event = await record_event(
            db,
            company_id=UUID(company_id),
            run_id=UUID(run_id) if run_id else None,
            role_id=UUID(role_id) if role_id else None,
            event_type="gate.decision",
            gate=str(decision.get("gate") or ""),
            action=str(decision.get("action") or ""),
            reasoning=decision.get("reasoning"),
            policy_result=dict(decision.get("policy_result") or {}),
            actor=actor,
            payload={"audited": True},
        )
        record["id"] = str(event.id)
        record["persisted"] = True
    decision["audited"] = True
    return record
