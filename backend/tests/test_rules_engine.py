"""Rule predicate evaluation across all supported operators."""

import pytest

from app.schemas.rules import RulePredicate
from app.services.rules_engine import evaluate_predicate

ATTRS = {
    "years_experience": 8,
    "commute_miles": 12,
    "work_authorization": "citizen",
    "skills": ["python", "kubernetes"],
    "seniority": "staff",
}


@pytest.mark.parametrize(
    ("operator", "field", "value", "expected"),
    [
        ("eq", "work_authorization", "citizen", True),
        ("eq", "work_authorization", "visa", False),
        ("neq", "seniority", "junior", True),
        ("lt", "commute_miles", 20, True),
        ("lt", "commute_miles", 5, False),
        ("lte", "commute_miles", 12, True),
        ("gt", "years_experience", 5, True),
        ("gte", "years_experience", 8, True),
        ("gte", "years_experience", 9, False),
        ("in", "seniority", ["staff", "principal"], True),
        ("in", "seniority", ["junior", "mid"], False),
        ("not_in", "seniority", ["junior", "mid"], True),
        ("contains", "skills", "python", True),
        ("contains", "skills", "golang", False),
        ("between", "commute_miles", [10, 20], True),
        ("between", "commute_miles", [0, 5], False),
    ],
)
def test_operator_matrix(operator, field, value, expected) -> None:
    rule = RulePredicate(field=field, operator=operator, value=value)
    passed, _reason = evaluate_predicate(rule, ATTRS)
    assert passed is expected


def test_missing_attribute_fails() -> None:
    rule = RulePredicate(field="clearance_level", operator="eq", value="secret")
    passed, reason = evaluate_predicate(rule, ATTRS)
    assert passed is False
    assert "missing attribute" in reason


def test_non_numeric_comparison_fails_gracefully() -> None:
    rule = RulePredicate(field="work_authorization", operator="gte", value=5)
    passed, reason = evaluate_predicate(rule, ATTRS)
    assert passed is False
    assert "comparable" in reason
