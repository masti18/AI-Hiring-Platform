"""Auth service: register company+user, login."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


async def register(db: AsyncSession, payload: RegisterRequest) -> TokenResponse:
    company = Company(name=payload.company_name, slug=payload.company_slug)
    user = User(
        company=company,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="admin",
    )
    db.add(company)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("Company slug or email already exists") from exc
    await db.refresh(user)
    await db.refresh(company)
    token = create_access_token(subject=str(user.id), company_id=str(company.id))
    return TokenResponse(
        access_token=token,
        company_id=company.id,
        user_id=user.id,
    )


async def login(db: AsyncSession, payload: LoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise ValueError("Invalid email or password")
    token = create_access_token(subject=str(user.id), company_id=str(user.company_id))
    return TokenResponse(
        access_token=token,
        company_id=user.company_id,
        user_id=user.id,
    )
