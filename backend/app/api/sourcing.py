"""Sourcing & scoring API (Milestone 2).

Triggers sourcing/scoring for a role and exposes the resulting candidates and
sourcing runs (including the post-sourcing gate1 decision). All reads are
tenant-scoped by `company_id`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.sourcing import (
    CandidateResponse,
    SourcingRunRequest,
    SourcingRunResponse,
    SourcingRunResult,
)
from app.services.sourcing import (
    RoleRequirementNotFound,
    get_sourcing_run,
    list_candidates,
    list_sourcing_runs,
    run_sourcing,
)

router = APIRouter(tags=["sourcing"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CompanyScope = Annotated[uuid.UUID, Query(description="Tenant scope")]


@router.post(
    "/requirements/{requirement_id}/sourcing-runs",
    response_model=SourcingRunResult,
    status_code=status.HTTP_201_CREATED,
)
async def create_sourcing_run(
    requirement_id: uuid.UUID,
    payload: SourcingRunRequest,
    company_id: CompanyScope,
    session: DbSession,
) -> SourcingRunResult:
    """Source + score candidates for a role and run the post-sourcing gate."""
    try:
        run, candidates = await run_sourcing(session, requirement_id, company_id, payload)
    except RoleRequirementNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
        ) from exc
    return SourcingRunResult(
        run=SourcingRunResponse.model_validate(run),
        candidates=[CandidateResponse.model_validate(c) for c in candidates],
    )


@router.get(
    "/requirements/{requirement_id}/candidates",
    response_model=list[CandidateResponse],
)
async def list_candidates_endpoint(
    requirement_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> list[CandidateResponse]:
    candidates = await list_candidates(session, requirement_id, company_id)
    return [CandidateResponse.model_validate(c) for c in candidates]


@router.get(
    "/requirements/{requirement_id}/sourcing-runs",
    response_model=list[SourcingRunResponse],
)
async def list_sourcing_runs_endpoint(
    requirement_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> list[SourcingRunResponse]:
    runs = await list_sourcing_runs(session, requirement_id, company_id)
    return [SourcingRunResponse.model_validate(r) for r in runs]


@router.get("/sourcing-runs/{run_id}", response_model=SourcingRunResponse)
async def get_sourcing_run_endpoint(
    run_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> SourcingRunResponse:
    run = await get_sourcing_run(session, run_id, company_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sourcing run not found")
    return SourcingRunResponse.model_validate(run)
