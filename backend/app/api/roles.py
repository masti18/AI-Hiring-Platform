"""Role / hiring-brief intake endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.core.database import get_db
from app.schemas.role import (
    GenerateJDResponse,
    JobDescription,
    PipelineRunResponse,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.services import role as role_service

router = APIRouter(prefix="/roles")


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    role = await role_service.create_role(
        db,
        company_id=auth.company_id,
        user_id=auth.user_id,
        payload=payload,
    )
    return RoleResponse.model_validate(role)


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoleResponse]:
    roles = await role_service.list_roles(db, company_id=auth.company_id)
    return [RoleResponse.model_validate(r) for r in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    role = await role_service.get_role(db, company_id=auth.company_id, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    payload: RoleUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    role = await role_service.update_role(
        db, company_id=auth.company_id, role_id=role_id, payload=payload
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleResponse.model_validate(role)


@router.post("/{role_id}/generate-jd", response_model=GenerateJDResponse)
async def generate_jd(
    role_id: UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateJDResponse:
    try:
        role, meta = await role_service.generate_jd_for_role(
            db,
            company_id=auth.company_id,
            role_id=role_id,
            actor=str(auth.user_id),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return GenerateJDResponse(
        role_id=role.id,
        jd=JobDescription.model_validate(meta["jd"]),
        provider=meta["provider"],
        model=meta["model"],
        stub=meta["stub"],
    )


@router.post(
    "/{role_id}/runs",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_run(
    role_id: UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    try:
        run = await role_service.start_pipeline_run(
            db,
            company_id=auth.company_id,
            role_id=role_id,
            actor=str(auth.user_id),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PipelineRunResponse.model_validate(run)
