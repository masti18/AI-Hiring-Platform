"""Service-level screening: LLM override and missing-candidate handling."""

import uuid

import pytest

from app.adapters.llm import MockLLMProvider
from app.core.database import AsyncSessionLocal
from app.schemas.requirements import RequirementIntakeRequest
from app.schemas.screening import ScreeningCallRequest
from app.schemas.sourcing import CandidateInput, SourcingRunRequest
from app.services.requirements import create_requirement
from app.services.screening import CandidateNotFound, conduct_screening
from app.services.sourcing import run_sourcing

BRIEF = "Backend engineer.\nSTATED: years_experience gte 5\nHIDDEN: work_authorization eq citizen\n"


async def _setup_candidate(company_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        req = await create_requirement(
            session,
            RequirementIntakeRequest(
                company_id=company_id, title="Backend Engineer", raw_brief=BRIEF
            ),
        )
        _run, candidates = await run_sourcing(
            session,
            req.id,
            company_id,
            SourcingRunRequest(
                candidates=[
                    CandidateInput(
                        name="Ada",
                        attributes={"years_experience": 8, "work_authorization": "citizen"},
                    )
                ]
            ),
        )
        return candidates[0].id


@pytest.mark.asyncio
async def test_llm_override_changes_recommendation(make_company) -> None:
    company = await make_company("LLM-Screen", auto_approve_gate2=True)
    candidate_id = await _setup_candidate(company.id)

    # Weak answers would deterministically reject; the LLM overrides to advance.
    llm = MockLLMProvider(canned={"overall_score": 0.92, "recommendation": "advance"})
    async with AsyncSessionLocal() as session:
        call = await conduct_screening(
            session,
            candidate_id,
            company.id,
            ScreeningCallRequest(answers=[]),
            llm=llm,
        )

    assert call.recommendation == "advance"
    assert call.overall_score == 0.92
    assert call.gate2_decision["action"] == "auto_approve"
    assert call.providers["llm"]["used"] is True


@pytest.mark.asyncio
async def test_missing_candidate_raises(make_company) -> None:
    company = await make_company("NoCand")
    async with AsyncSessionLocal() as session:
        with pytest.raises(CandidateNotFound):
            await conduct_screening(
                session, uuid.uuid4(), company.id, ScreeningCallRequest(answers=[])
            )
