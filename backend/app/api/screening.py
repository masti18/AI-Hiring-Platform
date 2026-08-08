"""AI screening call API (Milestone 3).

Conducts an AI screening call for a candidate and exposes the resulting calls
(structured transcript + evaluation + gate2 decision). All reads are tenant-scoped.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.screening import ScreeningCallRequest, ScreeningCallResponse
from app.services.screening import (
    CandidateNotFound,
    conduct_screening,
    get_screening_call,
    list_screening_calls,
)

router = APIRouter(tags=["screening"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CompanyScope = Annotated[uuid.UUID, Query(description="Tenant scope")]


@router.post(
    "/candidates/{candidate_id}/screening-calls",
    response_model=ScreeningCallResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_call(
    candidate_id: uuid.UUID,
    payload: ScreeningCallRequest,
    company_id: CompanyScope,
    session: DbSession,
) -> ScreeningCallResponse:
    """Conduct an AI screening call and evaluate it through the post-call gate."""
    try:
        call = await conduct_screening(session, candidate_id, company_id, payload)
    except CandidateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        ) from exc
    return ScreeningCallResponse.model_validate(call)


@router.get(
    "/candidates/{candidate_id}/screening-calls",
    response_model=list[ScreeningCallResponse],
)
async def list_screening_calls_endpoint(
    candidate_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> list[ScreeningCallResponse]:
    calls = await list_screening_calls(session, candidate_id, company_id)
    return [ScreeningCallResponse.model_validate(c) for c in calls]


@router.get("/screening-calls/{call_id}", response_model=ScreeningCallResponse)
async def get_screening_call_endpoint(
    call_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> ScreeningCallResponse:
    call = await get_screening_call(session, call_id, company_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Screening call not found"
        )
    return ScreeningCallResponse.model_validate(call)
