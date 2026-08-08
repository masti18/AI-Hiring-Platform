"""Requirement Intake API.

Endpoints to create and read structured hiring roles. The internal view exposes
hidden filters; the `/job-description` view is external-facing and omits them.
Multi-tenant: `company_id` scopes every read (auth wiring lands in a later milestone).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.requirements import (
    ExternalJobDescriptionResponse,
    RequirementIntakeRequest,
    RoleRequirementResponse,
)
from app.services.requirements import (
    create_requirement,
    get_requirement,
    list_requirements,
)

router = APIRouter(prefix="/requirements", tags=["requirements"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CompanyScope = Annotated[uuid.UUID, Query(description="Tenant scope")]


@router.post("", response_model=RoleRequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_requirement_endpoint(
    payload: RequirementIntakeRequest,
    session: DbSession,
) -> RoleRequirementResponse:
    """Run intake on a raw brief and persist the structured role."""
    requirement = await create_requirement(session, payload)
    return RoleRequirementResponse.model_validate(requirement)


@router.get("", response_model=list[RoleRequirementResponse])
async def list_requirements_endpoint(
    company_id: CompanyScope,
    session: DbSession,
) -> list[RoleRequirementResponse]:
    requirements = await list_requirements(session, company_id)
    return [RoleRequirementResponse.model_validate(r) for r in requirements]


@router.get("/{requirement_id}", response_model=RoleRequirementResponse)
async def get_requirement_endpoint(
    requirement_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> RoleRequirementResponse:
    requirement = await get_requirement(session, requirement_id, company_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return RoleRequirementResponse.model_validate(requirement)


@router.get("/{requirement_id}/job-description", response_model=ExternalJobDescriptionResponse)
async def get_external_job_description(
    requirement_id: uuid.UUID,
    company_id: CompanyScope,
    session: DbSession,
) -> ExternalJobDescriptionResponse:
    """External-facing JD. Hidden filters are never included in this response."""
    requirement = await get_requirement(session, requirement_id, company_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return ExternalJobDescriptionResponse(
        id=requirement.id,
        company_id=requirement.company_id,
        title=requirement.title,
        job_description=requirement.job_description,
        stated_filters=requirement.stated_filters,
    )
