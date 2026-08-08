"""Rule predicate evaluation.

Evaluates a `RulePredicate` against a candidate's structured attributes. Used for
both stated (external) and hidden (internal) rule enforcement at scoring time.
A missing attribute fails the predicate (candidates must positively satisfy rules).
"""

from __future__ import annotations

from typing import Any

from app.schemas.rules import RulePredicate

_MISSING = object()


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def evaluate_predicate(rule: RulePredicate, attributes: dict[str, Any]) -> tuple[bool, str]:
    """Return (passed, reason) for a single predicate against candidate attributes."""
    attr = attributes.get(rule.field, _MISSING)
    if attr is _MISSING:
        return False, f"missing attribute '{rule.field}'"

    op = rule.operator
    value = rule.value

    if op == "eq":
        return (attr == value), f"{rule.field} == {value}"
    if op == "neq":
        return (attr != value), f"{rule.field} != {value}"

    if op in {"lt", "lte", "gt", "gte"}:
        left, right = _as_number(attr), _as_number(value)
        if left is None or right is None:
            return False, f"{rule.field} not numerically comparable to {value}"
        result = {
            "lt": left < right,
            "lte": left <= right,
            "gt": left > right,
            "gte": left >= right,
        }[op]
        return result, f"{rule.field} {op} {value}"

    if op == "in":
        options = value if isinstance(value, list) else [value]
        return (attr in options), f"{rule.field} in {options}"
    if op == "not_in":
        options = value if isinstance(value, list) else [value]
        return (attr not in options), f"{rule.field} not in {options}"

    if op == "contains":
        if isinstance(attr, list | tuple | set):
            return (value in attr), f"{rule.field} contains {value}"
        return (str(value) in str(attr)), f"{rule.field} contains {value}"

    if op == "between":
        if not isinstance(value, list) or len(value) != 2:
            return False, f"between requires [low, high], got {value}"
        target = _as_number(attr)
        low, high = _as_number(value[0]), _as_number(value[1])
        if target is None or low is None or high is None:
            return False, f"{rule.field} not numerically comparable for between"
        return (low <= target <= high), f"{low} <= {rule.field} <= {high}"

    return False, f"unsupported operator '{op}'"
