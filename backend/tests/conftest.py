"""Shared test fixtures.

Uses the application's async engine against the local Postgres. Schema is created
idempotently from model metadata, and the engine pool is disposed per test so each
test runs cleanly on its own event loop.
"""

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import text

import app.models  # noqa: F401 — register all ORM models on Base.metadata
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.company import Company


@pytest_asyncio.fixture(autouse=True)
async def _prepare_database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSessionLocal]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def make_company() -> AsyncIterator[Callable]:
    """Factory that creates Company rows and cleans them up (cascades to children)."""
    created: list[uuid.UUID] = []

    async def _make(
        name: str = "Acme",
        *,
        auto_approve_gate1: bool = True,
        auto_approve_gate2: bool = True,
    ) -> Company:
        company = Company(
            id=uuid.uuid4(),
            name=name,
            slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}",
            auto_approve_gate1=auto_approve_gate1,
            auto_approve_gate2=auto_approve_gate2,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async with AsyncSessionLocal() as session:
            session.add(company)
            await session.commit()
            await session.refresh(company)
        created.append(company.id)
        return company

    yield _make

    async with AsyncSessionLocal() as session:
        for company_id in created:
            await session.execute(
                text("DELETE FROM companies WHERE id = :id"), {"id": str(company_id)}
            )
        await session.commit()
