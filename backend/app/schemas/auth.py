"""Auth request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    company_slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    company_id: UUID
    user_id: UUID


class UserResponse(BaseModel):
    id: UUID
    company_id: UUID
    email: EmailStr
    full_name: str
    role: str

    model_config = {"from_attributes": True}
