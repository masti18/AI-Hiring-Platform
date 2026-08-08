"""Requirement Intake extraction logic (no database)."""

import pytest

from app.adapters.llm import MockLLMProvider, OpenAILLMProvider
from app.schemas.requirements import JobDescription, RequirementIntakeRequest
from app.schemas.rules import RulePredicate
from app.services.requirements import (
    RequirementIntakeService,
    RequirementLeakError,
    _assert_no_leak,
)

COMPANY_ID = "11111111-1111-1111-1111-111111111111"


def _request(**overrides) -> RequirementIntakeRequest:
    base = {
        "company_id": COMPANY_ID,
        "title": "Senior Backend Engineer",
        "raw_brief": (
            "We need a senior backend engineer to own our payments service.\n"
            "- Design and operate high-throughput APIs\n"
            "- Mentor mid-level engineers\n"
            "STATED: years_experience gte 5\n"
            "HIDDEN: commute_miles lte 30\n"
            "HIDDEN: internal_referral_only eq true\n"
        ),
    }
    base.update(overrides)
    return RequirementIntakeRequest(**base)


def test_parse_separates_stated_and_hidden() -> None:
    result = RequirementIntakeService().parse(_request())

    stated_fields = {r.field for r in result.stated_filters}
    hidden_fields = {r.field for r in result.hidden_filters}

    assert "years_experience" in stated_fields
    assert hidden_fields == {"commute_miles", "internal_referral_only"}


def test_explicit_filters_merge_with_inline() -> None:
    extra = RulePredicate(field="salary_ceiling", operator="lte", value=180000)
    result = RequirementIntakeService().parse(_request(hidden_filters=[extra]))
    hidden_fields = {r.field for r in result.hidden_filters}
    assert "salary_ceiling" in hidden_fields
    assert "commute_miles" in hidden_fields


def test_job_description_built_from_stated_only() -> None:
    result = RequirementIntakeService().parse(_request())
    jd = result.job_description

    assert jd.title == "Senior Backend Engineer"
    assert "Design and operate high-throughput APIs" in jd.responsibilities
    # STATED filter is rendered into requirements...
    assert any("years_experience" in req for req in jd.requirements)
    # ...but HIDDEN directive lines are not surfaced as responsibilities.
    assert all("commute" not in r.lower() for r in jd.responsibilities)


def test_hidden_rules_never_leak_into_jd() -> None:
    result = RequirementIntakeService().parse(_request())
    serialized = result.job_description.model_dump_json().lower()

    assert "commute_miles" not in serialized
    assert "internal_referral_only" not in serialized


def test_leak_guard_raises_on_exposure() -> None:
    jd = JobDescription(title="Role", summary="Must live within commute_miles of office")
    hidden = [RulePredicate(field="commute_miles", operator="lte", value=30)]
    with pytest.raises(RequirementLeakError):
        _assert_no_leak(jd, hidden)


@pytest.mark.asyncio
async def test_llm_enrichment_updates_summary() -> None:
    provider = MockLLMProvider(canned={"summary": "Own payments at scale."})
    service = RequirementIntakeService(llm=provider)
    result = await service.parse_async(_request())

    assert result.job_description.summary == "Own payments at scale."
    assert result.llm_metadata["used"] is True
    assert result.llm_metadata["provider"] == "mock"


@pytest.mark.asyncio
async def test_stub_llm_does_not_enrich() -> None:
    service = RequirementIntakeService(llm=OpenAILLMProvider(api_key="", model="gpt-4o"))
    result = await service.parse_async(_request())

    assert result.llm_metadata["used"] is False
    # Deterministic summary is the first prose paragraph of the brief.
    assert result.job_description.summary.startswith("We need a senior backend engineer")
