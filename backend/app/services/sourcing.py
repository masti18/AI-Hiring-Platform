"""Sourcing & scoring orchestration (Milestone 2).

Pipeline for one role requirement:
    load role (tenant-scoped)
      -> gather candidates (sourcing adapter + any directly supplied pool)
      -> score each candidate against stated + hidden rules
      -> persist a sourcing_run + scored candidates
      -> run the post-sourcing auto-gate (gate1): ALWAYS evaluate + audit;
         blocking is config-driven via company.auto_approve_gate1
      -> return the run and candidates

External integrations stay behind the `SourcingAdapter` interface so the stage is
mockable/swappable.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.adapters.sourcing import MockSourcingAdapter, SourcingAdapter
from app.agents.gates import evaluate_gate_policy
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.role_requirement import RoleRequirement
from app.models.sourcing_run import SourcingRun
from app.schemas.rules import RulePredicate
from app.schemas.sourcing import CandidateInput, SourcingRunRequest
from app.services.audit import record_audit_event
from app.services.scoring import score_candidate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MIN_QUALIFIED_CANDIDATES = 1


class RoleRequirementNotFound(LookupError):
    """Raised when the target role requirement does not exist for the tenant."""


def _normalize_sourced(raw: dict[str, Any]) -> CandidateInput:
    """Coerce a raw adapter result into a CandidateInput."""
    known = {"external_id", "source", "name", "attributes"}
    attributes = raw.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {k: v for k, v in raw.items() if k not in known}
    return CandidateInput(
        external_id=raw.get("external_id"),
        source=raw.get("source", "adapter"),
        name=raw.get("name", "Unknown"),
        attributes=attributes,
    )


async def _gather_candidates(
    adapter: SourcingAdapter,
    stated_filters: list[RulePredicate],
    request: SourcingRunRequest,
) -> list[CandidateInput]:
    query = {
        "filters": [rule.model_dump() for rule in stated_filters],
        "limit": request.limit,
    }
    sourced = await adapter.search(query, limit=request.limit)
    candidates = [_normalize_sourced(item) for item in sourced]
    candidates.extend(request.candidates)
    return candidates[: request.limit]


async def run_sourcing(
    session: AsyncSession,
    requirement_id: uuid.UUID,
    company_id: uuid.UUID,
    request: SourcingRunRequest,
    *,
    adapter: SourcingAdapter | None = None,
) -> tuple[SourcingRun, list[Candidate]]:
    """Source, score, persist, and run the post-sourcing gate for a role."""
    role = (
        await session.execute(
            select(RoleRequirement).where(
                RoleRequirement.id == requirement_id,
                RoleRequirement.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if role is None:
        raise RoleRequirementNotFound(str(requirement_id))

    company = (
        await session.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    auto_approve = bool(company.auto_approve_gate1) if company is not None else True

    stated = [RulePredicate.model_validate(f) for f in role.stated_filters]
    hidden = [RulePredicate.model_validate(f) for f in role.hidden_filters]

    adapter = adapter or MockSourcingAdapter()
    inputs = await _gather_candidates(adapter, stated, request)

    scored: list[tuple[CandidateInput, Any]] = []
    qualified_count = 0
    for candidate in inputs:
        score = score_candidate(
            attributes=candidate.attributes,
            stated_filters=stated,
            hidden_filters=hidden,
        )
        if score.qualified:
            qualified_count += 1
        scored.append((candidate, score))

    passed = qualified_count >= MIN_QUALIFIED_CANDIDATES
    policy_result = {
        "passed": passed,
        "checks": [
            {
                "name": "min_qualified_candidates",
                "ok": passed,
                "qualified": qualified_count,
                "required": MIN_QUALIFIED_CANDIDATES,
            }
        ],
    }
    decision = await evaluate_gate_policy(
        gate="gate1_post_sourcing",
        state={"company_id": str(company_id), "role_id": str(requirement_id)},
        auto_approve=auto_approve,
        policy_result=policy_result,
    )

    run = SourcingRun(
        company_id=company_id,
        role_requirement_id=requirement_id,
        status="completed",
        candidate_count=len(scored),
        qualified_count=qualified_count,
        gate1_decision=dict(decision),
    )
    session.add(run)
    await session.flush()

    candidates: list[Candidate] = []
    for candidate_input, score in scored:
        candidate = Candidate(
            company_id=company_id,
            role_requirement_id=requirement_id,
            sourcing_run_id=run.id,
            external_id=candidate_input.external_id,
            source=candidate_input.source,
            name=candidate_input.name,
            attributes=candidate_input.attributes,
            score=score.model_dump(),
            overall_score=score.overall,
            status="qualified" if score.qualified else "rejected",
        )
        session.add(candidate)
        candidates.append(candidate)
    await session.flush()

    await record_audit_event(
        session,
        company_id=company_id,
        action="gate1_post_sourcing",
        entity_type="sourcing_run",
        entity_id=run.id,
        payload={
            "gate": decision["gate"],
            "action": decision["action"],
            "reasoning": decision["reasoning"],
            "candidate_count": len(scored),
            "qualified_count": qualified_count,
        },
    )

    await session.commit()
    await session.refresh(run)
    for candidate in candidates:
        await session.refresh(candidate)
    return run, candidates


async def list_candidates(
    session: AsyncSession,
    requirement_id: uuid.UUID,
    company_id: uuid.UUID,
) -> list[Candidate]:
    stmt = (
        select(Candidate)
        .where(
            Candidate.role_requirement_id == requirement_id,
            Candidate.company_id == company_id,
        )
        .order_by(Candidate.overall_score.desc(), Candidate.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_sourcing_runs(
    session: AsyncSession,
    requirement_id: uuid.UUID,
    company_id: uuid.UUID,
) -> list[SourcingRun]:
    stmt = (
        select(SourcingRun)
        .where(
            SourcingRun.role_requirement_id == requirement_id,
            SourcingRun.company_id == company_id,
        )
        .order_by(SourcingRun.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_sourcing_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    company_id: uuid.UUID,
) -> SourcingRun | None:
    stmt = select(SourcingRun).where(
        SourcingRun.id == run_id,
        SourcingRun.company_id == company_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()
