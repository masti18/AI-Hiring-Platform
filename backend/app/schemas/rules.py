"""Structured hidden-rule predicates (machine-evaluable, never leaked into JD text)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RulePredicate(BaseModel):
    """JSON rule object: field / operator / value. Used for internal (hidden) filters."""

    field: str = Field(..., description="Candidate or role attribute path, e.g. commute_miles")
    operator: Literal[
        "eq",
        "neq",
        "lt",
        "lte",
        "gt",
        "gte",
        "in",
        "not_in",
        "contains",
        "between",
    ]
    value: Any
    description: str | None = Field(
        default=None,
        description="Internal-only human note; never rendered into external JD text.",
    )


class FilterSet(BaseModel):
    """Separation of stated (external JD) vs hidden (internal) filters at intake."""

    stated: list[RulePredicate] = Field(default_factory=list)
    hidden: list[RulePredicate] = Field(default_factory=list)
