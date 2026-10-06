"""Role / requisition domain service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.pipeline_run import PipelineRun
from app.models.role import Role
from app.schemas.role import RoleCreateRequest, RoleUpdateRequest
from app.schemas.rules import RulePredicate
from app.services import audit as audit_service
from app.services.jd import (
    extract_filters_from_brief,
    generate_job_description,
    split_brief_heuristically,
)


def _preds_to_dicts(preds: list[RulePredicate]) -> list[dict]:
    return [p.model_dump() for p in preds]


async def create_role(
    db: AsyncSession,
    *,
    company_id: UUID,
    user_id: UUID,
    payload: RoleCreateRequest,
) -> Role:
    stated = _preds_to_dicts(payload.stated_filters)
    hidden = _preds_to_dicts(payload.hidden_filters)

    if payload.extract_filters and not stated and not hidden:
        extracted = await extract_filters_from_brief(payload.brief_text)
        if not extracted["stated"] and not extracted["hidden"]:
            extracted = split_brief_heuristically(payload.brief_text)
        stated = extracted["stated"]
        hidden = extracted["hidden"]

    role = Role(
        company_id=company_id,
        created_by_user_id=user_id,
        title=payload.title,
        department=payload.department,
        location=payload.location,
        employment_type=payload.employment_type,
        status="draft",
        brief_text=payload.brief_text,
        hiring_brief={
            "raw_text": payload.brief_text,
            "title": payload.title,
            "department": payload.department,
            "location": payload.location,
            "employment_type": payload.employment_type,
        },
        stated_filters=stated,
        hidden_filters=hidden,
        jd=None,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    await audit_service.record_event(
        db,
        company_id=company_id,
        role_id=role.id,
        event_type="role.created",
        actor=str(user_id),
        payload={
            "title": role.title,
            "stated_count": len(stated),
            "hidden_count": len(hidden),
        },
    )
    return role


async def list_roles(db: AsyncSession, *, company_id: UUID) -> list[Role]:
    result = await db.execute(
        select(Role).where(Role.company_id == company_id).order_by(Role.created_at.desc())
    )
    return list(result.scalars().all())


async def get_role(db: AsyncSession, *, company_id: UUID, role_id: UUID) -> Role | None:
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.company_id == company_id)
    )
    return result.scalar_one_or_none()


async def update_role(
    db: AsyncSession,
    *,
    company_id: UUID,
    role_id: UUID,
    payload: RoleUpdateRequest,
) -> Role | None:
    role = await get_role(db, company_id=company_id, role_id=role_id)
    if role is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "stated_filters" in data and data["stated_filters"] is not None:
        data["stated_filters"] = [RulePredicate.model_validate(p).model_dump() for p in data["stated_filters"]]
    if "hidden_filters" in data and data["hidden_filters"] is not None:
        data["hidden_filters"] = [RulePredicate.model_validate(p).model_dump() for p in data["hidden_filters"]]
    for key, value in data.items():
        setattr(role, key, value)
    if "brief_text" in data:
        brief = dict(role.hiring_brief or {})
        brief["raw_text"] = data["brief_text"]
        role.hiring_brief = brief
    await db.commit()
    await db.refresh(role)
    return role


async def generate_jd_for_role(
    db: AsyncSession,
    *,
    company_id: UUID,
    role_id: UUID,
    actor: str,
) -> tuple[Role, dict]:
    role = await get_role(db, company_id=company_id, role_id=role_id)
    if role is None:
        raise LookupError("Role not found")

    jd, llm_result = await generate_job_description(
        title=role.title,
        brief_text=role.brief_text,
        location=role.location,
        employment_type=role.employment_type,
        stated_filters=list(role.stated_filters or []),
        hidden_filters=list(role.hidden_filters or []),
    )
    role.jd = jd.model_dump()
    role.status = "jd_ready"
    await db.commit()
    await db.refresh(role)

    await audit_service.record_event(
        db,
        company_id=company_id,
        role_id=role.id,
        event_type="role.jd_generated",
        actor=actor,
        payload={
            "provider": llm_result.provider,
            "model": llm_result.model,
            "stub": bool(llm_result.data.get("stub")),
            "jd_title": jd.title,
        },
    )
    return role, {
        "jd": jd,
        "provider": llm_result.provider,
        "model": llm_result.model,
        "stub": bool(llm_result.data.get("stub")),
    }


async def start_pipeline_run(
    db: AsyncSession,
    *,
    company_id: UUID,
    role_id: UUID,
    actor: str,
) -> PipelineRun:
    from app.agents.graph import compile_hiring_graph

    role = await get_role(db, company_id=company_id, role_id=role_id)
    if role is None:
        raise LookupError("Role not found")

    company = await db.get(Company, company_id)
    if company is None:
        raise LookupError("Company not found")

    run = PipelineRun(
        company_id=company_id,
        role_id=role_id,
        status="running",
        graph_state={},
    )
    db.add(run)
    await db.flush()

    initial_state = {
        "company_id": str(company_id),
        "role_id": str(role_id),
        "run_id": str(run.id),
        "hiring_brief": {
            **(role.hiring_brief or {}),
            "auto_approve_gate1": company.auto_approve_gate1,
            "auto_approve_gate2": company.auto_approve_gate2,
        },
        "stated_filters": list(role.stated_filters or []),
        "hidden_filters": list(role.hidden_filters or []),
        "jd": role.jd or {},
        "candidates": [],
        "scores": [],
        "call_evaluations": [],
        "errors": [],
        "status": "starting",
    }

    graph = compile_hiring_graph()
    # Run through intake only for M1; later milestones continue the graph.
    # Full invoke still exercises gate structure when candidates empty.
    final_state = await graph.ainvoke(initial_state)

    run.graph_state = dict(final_state)
    run.status = str(final_state.get("status") or "completed")
    await db.commit()
    await db.refresh(run)

    # Persist gate decisions if present
    for gate_key in ("gate1", "gate2"):
        decision = final_state.get(gate_key)
        if not decision:
            continue
        await audit_service.record_gate_decision(
            db,
            company_id=str(company_id),
            run_id=str(run.id),
            decision=decision,
            actor=actor,
            role_id=str(role_id),
        )

    await audit_service.record_event(
        db,
        company_id=company_id,
        role_id=role_id,
        run_id=run.id,
        event_type="pipeline.run_started",
        actor=actor,
        payload={"status": run.status},
    )
    return run
