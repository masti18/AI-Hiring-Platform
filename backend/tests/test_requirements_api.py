"""Requirement Intake API: happy path, tenant isolation, hidden-rule protection."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.audit_log import AuditLog

BRIEF = (
    "Own the core matching service end to end.\n"
    "- Ship reliable async pipelines\n"
    "STATED: years_experience gte 4\n"
    "HIDDEN: commute_miles lte 25\n"
)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_create_and_fetch_requirement(make_company) -> None:
    company = await make_company("Northwind")

    async with _client() as client:
        create = await client.post(
            "/requirements",
            json={
                "company_id": str(company.id),
                "title": "Staff Engineer",
                "raw_brief": BRIEF,
            },
        )
        assert create.status_code == 201, create.text
        body = create.json()
        requirement_id = body["id"]

        assert body["status"] == "intake_complete"
        assert body["job_description"]["title"] == "Staff Engineer"
        assert any(r["field"] == "years_experience" for r in body["stated_filters"])
        assert any(r["field"] == "commute_miles" for r in body["hidden_filters"])

        fetched = await client.get(
            f"/requirements/{requirement_id}", params={"company_id": str(company.id)}
        )
        assert fetched.status_code == 200
        assert fetched.json()["id"] == requirement_id


@pytest.mark.asyncio
async def test_tenant_isolation(make_company) -> None:
    company_a = await make_company("Alpha")
    company_b = await make_company("Bravo")

    async with _client() as client:
        created = await client.post(
            "/requirements",
            json={"company_id": str(company_a.id), "title": "SRE", "raw_brief": BRIEF},
        )
        assert created.status_code == 201
        requirement_id = created.json()["id"]

        list_a = await client.get("/requirements", params={"company_id": str(company_a.id)})
        list_b = await client.get("/requirements", params={"company_id": str(company_b.id)})
        assert len(list_a.json()) == 1
        assert list_b.json() == []

        # Company B cannot read Company A's requirement.
        cross = await client.get(
            f"/requirements/{requirement_id}", params={"company_id": str(company_b.id)}
        )
        assert cross.status_code == 404


@pytest.mark.asyncio
async def test_external_job_description_omits_hidden(make_company) -> None:
    company = await make_company("Cipher")

    async with _client() as client:
        created = await client.post(
            "/requirements",
            json={"company_id": str(company.id), "title": "Backend Eng", "raw_brief": BRIEF},
        )
        requirement_id = created.json()["id"]

        external = await client.get(
            f"/requirements/{requirement_id}/job-description",
            params={"company_id": str(company.id)},
        )
        assert external.status_code == 200
        payload = external.text.lower()

    assert "hidden_filters" not in external.json()
    assert "commute_miles" not in payload
    # Stated filters remain visible externally.
    assert any(r["field"] == "years_experience" for r in external.json()["stated_filters"])


@pytest.mark.asyncio
async def test_intake_writes_audit_record(make_company) -> None:
    company = await make_company("Delta")

    async with _client() as client:
        created = await client.post(
            "/requirements",
            json={"company_id": str(company.id), "title": "Data Eng", "raw_brief": BRIEF},
        )
        assert created.status_code == 201

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.company_id == company.id)
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].action == "requirement.intake_completed"
    assert rows[0].entity_type == "role_requirement"
    assert rows[0].payload["hidden_filter_count"] == 1
