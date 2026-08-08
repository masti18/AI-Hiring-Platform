"""Service-level sourcing: candidates supplied by a SourcingAdapter are scored."""

import uuid

import pytest

from app.adapters.sourcing_pool import StaticSourcingAdapter
from app.core.database import AsyncSessionLocal
from app.schemas.requirements import RequirementIntakeRequest
from app.schemas.sourcing import SourcingRunRequest
from app.services.requirements import create_requirement
from app.services.sourcing import RoleRequirementNotFound, run_sourcing

BRIEF = (
    "Platform engineer.\n"
    "STATED: years_experience gte 5\n"
    "HIDDEN: work_authorization eq citizen\n"
)


async def _make_requirement(company_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        req = await create_requirement(
            session,
            RequirementIntakeRequest(company_id=company_id, title="Platform Eng", raw_brief=BRIEF),
        )
        return req.id


@pytest.mark.asyncio
async def test_adapter_sourced_candidates_are_scored(make_company) -> None:
    company = await make_company("Adapter-Co")
    requirement_id = await _make_requirement(company.id)

    adapter = StaticSourcingAdapter(
        pool=[
            {
                "name": "Grace",
                "external_id": "g-1",
                "source": "static",
                "attributes": {"years_experience": 12, "work_authorization": "citizen"},
            }
        ]
    )

    async with AsyncSessionLocal() as session:
        run, candidates = await run_sourcing(
            session,
            requirement_id,
            company.id,
            SourcingRunRequest(),  # no body candidates; all come from the adapter
            adapter=adapter,
        )

    assert run.candidate_count == 1
    assert run.qualified_count == 1
    assert candidates[0].name == "Grace"
    assert candidates[0].source == "static"
    assert candidates[0].status == "qualified"


@pytest.mark.asyncio
async def test_missing_role_raises(make_company) -> None:
    company = await make_company("NoRole-Co")
    async with AsyncSessionLocal() as session:
        with pytest.raises(RoleRequirementNotFound):
            await run_sourcing(
                session, uuid.uuid4(), company.id, SourcingRunRequest(candidates=[])
            )
