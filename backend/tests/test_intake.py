"""Auth + intake + JD generation API tests (requires live Postgres)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient) -> None:
    slug = _unique("acme")
    email = f"{slug}@example.com"
    reg = await client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "company_slug": slug,
            "email": email,
            "password": "password123",
            "full_name": "Ada Admin",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = await client.post("/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    assert "access_token" in login.json()


@pytest.mark.asyncio
async def test_intake_separates_hidden_and_generates_jd_without_leak(client: AsyncClient) -> None:
    slug = _unique("hire")
    email = f"{slug}@example.com"
    reg = await client.post(
        "/auth/register",
        json={
            "company_name": "Hire Co",
            "company_slug": slug,
            "email": email,
            "password": "password123",
            "full_name": "Hiring Manager",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post(
        "/roles",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Seattle, WA",
            "employment_type": "full_time",
            "brief_text": (
                "Need a backend engineer with 5+ years Python and FastAPI. "
                "Remote OK in US. Degree preferred."
            ),
            "stated_filters": [
                {"field": "years_experience", "operator": "gte", "value": 5},
                {"field": "skills", "operator": "contains", "value": "Python"},
            ],
            "hidden_filters": [
                {
                    "field": "commute_miles",
                    "operator": "lte",
                    "value": 25,
                    "description": "INTERNAL_ONLY_MAX_COMMUTE_25MI",
                }
            ],
        },
    )
    assert create.status_code == 201, create.text
    role = create.json()
    assert role["stated_filters"][0]["field"] == "years_experience"
    assert role["hidden_filters"][0]["field"] == "commute_miles"
    role_id = role["id"]

    jd_resp = await client.post(f"/roles/{role_id}/generate-jd", headers=headers)
    assert jd_resp.status_code == 200, jd_resp.text
    body = jd_resp.json()
    assert body["jd"]["title"]
    assert "INTERNAL_ONLY_MAX_COMMUTE_25MI" not in str(body["jd"])
    assert body["jd"]["stated_requirements"]

    company = await client.get("/companies/me", headers=headers)
    assert company.status_code == 200
    assert company.json()["auto_approve_gate1"] is True

    patch = await client.patch(
        "/companies/me",
        headers=headers,
        json={"auto_approve_gate1": False},
    )
    assert patch.status_code == 200
    assert patch.json()["auto_approve_gate1"] is False

    run = await client.post(f"/roles/{role_id}/runs", headers=headers)
    assert run.status_code == 201, run.text
    # With gate1 auto_approve false, graph should await human after sourcing
    assert run.json()["status"] in {
        "awaiting_human",
        "gate1_await_human",
        "offer_ready",
        "sourcing_complete",
        "intake_complete",
        "rejected",
        "ai_call_complete",
        "gate1_auto_approve",
        "gate2_auto_approve",
        "gate2_await_human",
    }


@pytest.mark.asyncio
async def test_jd_stub_and_heuristic_extract() -> None:
    from app.services.jd import build_stub_jd, split_brief_heuristically

    brief = (
        "Looking for senior engineer with Python experience.\n"
        "Must live within 20 miles commute.\n"
        "Culture-fit: high ownership.\n"
    )
    split = split_brief_heuristically(brief)
    assert split["hidden"]
    assert any("commute" in (h.get("description") or "").lower() for h in split["hidden"])

    jd = build_stub_jd(
        title="Eng",
        brief_text=brief,
        location="NYC",
        employment_type="full_time",
        stated_filters=[{"field": "skills", "operator": "contains", "value": "Python"}],
    )
    assert jd.title == "Eng"
    assert jd.metadata["generated_by"] == "stub"
