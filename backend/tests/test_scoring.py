"""Candidate scoring: stated + hidden rule enforcement and qualification."""

from app.schemas.rules import RulePredicate
from app.services.scoring import score_candidate

STATED = [RulePredicate(field="years_experience", operator="gte", value=5)]
HIDDEN = [
    RulePredicate(field="commute_miles", operator="lte", value=30),
    RulePredicate(field="work_authorization", operator="eq", value="citizen"),
]


def test_fully_qualified_candidate() -> None:
    score = score_candidate(
        attributes={"years_experience": 8, "commute_miles": 10, "work_authorization": "citizen"},
        stated_filters=STATED,
        hidden_filters=HIDDEN,
    )
    assert score.qualified is True
    assert score.passed_stated is True
    assert score.passed_hidden is True
    assert score.overall == 1.0
    assert score.matched_count == 3
    assert score.total_count == 3


def test_hidden_rule_failure_disqualifies() -> None:
    score = score_candidate(
        attributes={"years_experience": 9, "commute_miles": 10, "work_authorization": "visa"},
        stated_filters=STATED,
        hidden_filters=HIDDEN,
    )
    assert score.qualified is False
    assert score.passed_hidden is False
    # Stated rule still passed, so overall is partial, not zero.
    assert 0 < score.overall < 1


def test_stated_rule_failure_disqualifies() -> None:
    score = score_candidate(
        attributes={"years_experience": 2, "commute_miles": 10, "work_authorization": "citizen"},
        stated_filters=STATED,
        hidden_filters=HIDDEN,
    )
    assert score.qualified is False
    assert score.passed_stated is False
    assert score.passed_hidden is True


def test_no_rules_means_qualified() -> None:
    score = score_candidate(attributes={}, stated_filters=[], hidden_filters=[])
    assert score.qualified is True
    assert score.overall == 1.0
    assert score.total_count == 0
