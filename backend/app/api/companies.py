"""Company endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.core.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyResponse, CompanyUpdateRequest

router = APIRouter(prefix="/companies")


@router.get("/me", response_model=CompanyResponse)
async def get_my_company(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    company = await db.get(Company, auth.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.patch("/me", response_model=CompanyResponse)
async def update_my_company(
    payload: CompanyUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    company = await db.get(Company, auth.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)
