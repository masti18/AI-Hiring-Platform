"""Screening API: evaluation, the post-AI-call gate (gate2), isolation, audit."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.schemas.requirements import RequirementIntakeRequest
from app.schemas.sourcing import CandidateInput, SourcingRunRequest
from app.services.requirements import create_requirement
from app.services.sourcing import run_sourcing

BRIEF = (
    "Backend engineer for the payments platform.\n"
    "STATED: years_experience gte 5\n"
    "HIDDEN: work_authorization eq citizen\n"
)
QUALIFYING = CandidateInput(
    name="Ada",
    external_id="ada-1",
    attributes={"years_experience": 8, "work_authorization": "citizen"},
)
STRONG_ANSWERS = [
    (
        "As a backend engineer I bring eight years of hands-on experience designing "
        "reliable payment platforms, scalable APIs, and strong on-call ownership across "
        "several engineering teams."
    ),
    (
        "I cut backend latency in half over years of experience by redesigning the data "
        "access layer, adding caching, and load-testing every change before we shipped it "
        "to production safely."
    ),
    (
        "I am excited about this backend engineer role because it matches my years of "
        "experience building resilient distributed systems and mentoring other engineers "
        "every single week."
    ),
]


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _setup_candidate(company_id: uuid.UUID) -> uuid.UUID:
    """Create a role + a qualified candidate via the M1/M2 services."""
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
            SourcingRunRequest(candidates=[QUALIFYING]),
        )
        return candidates[0].id


@pytest.mark.asyncio
async def test_advance_auto_approves(make_company) -> None:
    company = await make_company("Screen-Auto", auto_approve_gate2=True)
    candidate_id = await _setup_candidate(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company.id)},
            json={"answers": STRONG_ANSWERS},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["recommendation"] == "advance"
        assert body["overall_score"] >= 0.6
        assert body["gate2_decision"]["gate"] == "gate2_post_ai_call"
        assert body["gate2_decision"]["action"] == "auto_approve"
        assert body["providers"]["transport"] == "mock-livekit"
        assert len(body["transcript"]) == 6  # 3 Q + 3 A


@pytest.mark.asyncio
async def test_await_human_when_flag_disabled(make_company) -> None:
    company = await make_company("Screen-Manual", auto_approve_gate2=False)
    candidate_id = await _setup_candidate(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company.id)},
            json={"answers": STRONG_ANSWERS},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["recommendation"] == "advance"
        assert body["gate2_decision"]["action"] == "await_human"


@pytest.mark.asyncio
async def test_reject_when_weak(make_company) -> None:
    company = await make_company("Screen-Reject", auto_approve_gate2=True)
    candidate_id = await _setup_candidate(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company.id)},
            json={"answers": []},  # no answers -> weak call
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["recommendation"] == "reject"
        assert body["gate2_decision"]["action"] == "reject"


@pytest.mark.asyncio
async def test_tenant_isolation(make_company) -> None:
    company_a = await make_company("Screen-A")
    company_b = await make_company("Screen-B")
    candidate_id = await _setup_candidate(company_a.id)

    async with _client() as client:
        cross = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company_b.id)},
            json={"answers": STRONG_ANSWERS},
        )
        assert cross.status_code == 404

        ok = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company_a.id)},
            json={"answers": STRONG_ANSWERS},
        )
        assert ok.status_code == 201

        b_view = await client.get(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company_b.id)},
        )
        assert b_view.json() == []


@pytest.mark.asyncio
async def test_gate2_is_audited(make_company) -> None:
    company = await make_company("Screen-Audit")
    candidate_id = await _setup_candidate(company.id)

    async with _client() as client:
        await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company.id)},
            json={"answers": STRONG_ANSWERS},
        )

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.company_id == company.id,
                    AuditLog.action == "gate2_post_ai_call",
                )
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].entity_type == "screening_call"
    assert rows[0].payload["recommendation"] == "advance"


@pytest.mark.asyncio
async def test_get_screening_call_scoped(make_company) -> None:
    company = await make_company("Screen-Get")
    other = await make_company("Screen-Other")
    candidate_id = await _setup_candidate(company.id)

    async with _client() as client:
        created = await client.post(
            f"/candidates/{candidate_id}/screening-calls",
            params={"company_id": str(company.id)},
            json={"answers": STRONG_ANSWERS},
        )
        call_id = created.json()["id"]

        ok = await client.get(
            f"/screening-calls/{call_id}", params={"company_id": str(company.id)}
        )
        assert ok.status_code == 200

        cross = await client.get(
            f"/screening-calls/{call_id}", params={"company_id": str(other.id)}
        )
        assert cross.status_code == 404
