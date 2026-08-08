"""Sourcing API: scoring, the post-sourcing gate (auto/await/reject), isolation, audit."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.schemas.requirements import RequirementIntakeRequest
from app.services.requirements import create_requirement

BRIEF = (
    "Backend role for our payments team.\n"
    "STATED: years_experience gte 5\n"
    "HIDDEN: commute_miles lte 30\n"
    "HIDDEN: work_authorization eq citizen\n"
)

ADA = {
    "name": "Ada",
    "external_id": "ada-1",
    "attributes": {"years_experience": 8, "commute_miles": 10, "work_authorization": "citizen"},
}
BOB = {  # fails a hidden rule (work_authorization)
    "name": "Bob",
    "external_id": "bob-1",
    "attributes": {"years_experience": 9, "commute_miles": 10, "work_authorization": "visa"},
}
CID = {  # fails the stated rule (years_experience)
    "name": "Cid",
    "external_id": "cid-1",
    "attributes": {"years_experience": 2, "commute_miles": 10, "work_authorization": "citizen"},
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_requirement(company_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        req = await create_requirement(
            session,
            RequirementIntakeRequest(
                company_id=company_id, title="Backend Engineer", raw_brief=BRIEF
            ),
        )
        return req.id


@pytest.mark.asyncio
async def test_auto_approve_scores_and_persists(make_company) -> None:
    company = await make_company("Sourcing-Auto", auto_approve_gate1=True)
    requirement_id = await _make_requirement(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company.id)},
            json={"candidates": [ADA, BOB]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

        assert body["run"]["gate1_decision"]["gate"] == "gate1_post_sourcing"
        assert body["run"]["gate1_decision"]["action"] == "auto_approve"
        assert body["run"]["candidate_count"] == 2
        assert body["run"]["qualified_count"] == 1

        by_name = {c["name"]: c for c in body["candidates"]}
        assert by_name["Ada"]["status"] == "qualified"
        assert by_name["Ada"]["score"]["qualified"] is True
        assert by_name["Bob"]["status"] == "rejected"
        assert by_name["Bob"]["score"]["passed_hidden"] is False

        listed = await client.get(
            f"/requirements/{requirement_id}/candidates",
            params={"company_id": str(company.id)},
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 2


@pytest.mark.asyncio
async def test_gate_awaits_human_when_flag_disabled(make_company) -> None:
    company = await make_company("Sourcing-Manual", auto_approve_gate1=False)
    requirement_id = await _make_requirement(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company.id)},
            json={"candidates": [ADA]},
        )
        assert resp.status_code == 201
        decision = resp.json()["run"]["gate1_decision"]
        assert decision["action"] == "await_human"
        assert resp.json()["run"]["qualified_count"] == 1


@pytest.mark.asyncio
async def test_gate_rejects_when_no_qualified(make_company) -> None:
    company = await make_company("Sourcing-Reject", auto_approve_gate1=True)
    requirement_id = await _make_requirement(company.id)

    async with _client() as client:
        resp = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company.id)},
            json={"candidates": [BOB, CID]},  # neither qualifies
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["run"]["qualified_count"] == 0
        assert body["run"]["gate1_decision"]["action"] == "reject"
        assert all(c["status"] == "rejected" for c in body["candidates"])


@pytest.mark.asyncio
async def test_tenant_isolation(make_company) -> None:
    company_a = await make_company("Tenant-A")
    company_b = await make_company("Tenant-B")
    requirement_id = await _make_requirement(company_a.id)

    async with _client() as client:
        # Company B cannot source against Company A's role.
        cross = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company_b.id)},
            json={"candidates": [ADA]},
        )
        assert cross.status_code == 404

        # Run under A, then confirm B sees no candidates.
        ok = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company_a.id)},
            json={"candidates": [ADA]},
        )
        assert ok.status_code == 201

        b_view = await client.get(
            f"/requirements/{requirement_id}/candidates",
            params={"company_id": str(company_b.id)},
        )
        assert b_view.json() == []


@pytest.mark.asyncio
async def test_gate_decision_is_audited(make_company) -> None:
    company = await make_company("Sourcing-Audit")
    requirement_id = await _make_requirement(company.id)

    async with _client() as client:
        await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company.id)},
            json={"candidates": [ADA]},
        )

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.company_id == company.id,
                    AuditLog.action == "gate1_post_sourcing",
                )
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].entity_type == "sourcing_run"
    assert rows[0].payload["qualified_count"] == 1


@pytest.mark.asyncio
async def test_get_sourcing_run_scoped(make_company) -> None:
    company = await make_company("Sourcing-Get")
    other = await make_company("Sourcing-Other")
    requirement_id = await _make_requirement(company.id)

    async with _client() as client:
        created = await client.post(
            f"/requirements/{requirement_id}/sourcing-runs",
            params={"company_id": str(company.id)},
            json={"candidates": [ADA]},
        )
        run_id = created.json()["run"]["id"]

        ok = await client.get(
            f"/sourcing-runs/{run_id}", params={"company_id": str(company.id)}
        )
        assert ok.status_code == 200

        cross = await client.get(
            f"/sourcing-runs/{run_id}", params={"company_id": str(other.id)}
        )
        assert cross.status_code == 404
