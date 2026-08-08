"""Candidate scoring.

Applies a role's stated + hidden rules to a candidate and produces a structured
score. Hidden rules are hard internal filters: a candidate must pass ALL hidden
rules to be `qualified`. `overall` is the fraction of all predicates satisfied.
"""

from __future__ import annotations

from typing import Any

from app.schemas.rules import RulePredicate
from app.schemas.sourcing import CandidateScore, PredicateResult
from app.services.rules_engine import evaluate_predicate


def _evaluate_set(
    rules: list[RulePredicate], attributes: dict[str, Any]
) -> tuple[list[PredicateResult], int]:
    results: list[PredicateResult] = []
    passed_count = 0
    for rule in rules:
        passed, reason = evaluate_predicate(rule, attributes)
        if passed:
            passed_count += 1
        results.append(
            PredicateResult(
                field=rule.field,
                operator=rule.operator,
                value=rule.value,
                passed=passed,
                reason=reason,
            )
        )
    return results, passed_count


def score_candidate(
    *,
    attributes: dict[str, Any],
    stated_filters: list[RulePredicate],
    hidden_filters: list[RulePredicate],
) -> CandidateScore:
    """Score one candidate against stated + hidden rules."""
    stated_results, stated_passed = _evaluate_set(stated_filters, attributes)
    hidden_results, hidden_passed = _evaluate_set(hidden_filters, attributes)

    total = len(stated_filters) + len(hidden_filters)
    matched = stated_passed + hidden_passed
    overall = (matched / total) if total else 1.0

    passed_stated = stated_passed == len(stated_filters)
    passed_hidden = hidden_passed == len(hidden_filters)
    # Hidden rules are hard filters; stated rules also required to qualify.
    qualified = passed_hidden and passed_stated

    return CandidateScore(
        overall=round(overall, 4),
        qualified=qualified,
        passed_stated=passed_stated,
        passed_hidden=passed_hidden,
        matched_count=matched,
        total_count=total,
        stated_results=stated_results,
        hidden_results=hidden_results,
    )
