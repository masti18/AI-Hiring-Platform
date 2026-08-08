"""Additive sourcing adapters for offline/dev use.

Implements the Milestone 0 `SourcingAdapter` interface without modifying it. A
`StaticSourcingAdapter` returns a fixed candidate pool, which keeps the sourcing
stage runnable and testable before a real provider (LinkedIn, etc.) is wired in.
"""

from __future__ import annotations

from typing import Any

from app.adapters.sourcing import SourcingAdapter


class StaticSourcingAdapter(SourcingAdapter):
    """Returns a caller-provided candidate pool (normalized adapter output shape)."""

    def __init__(self, pool: list[dict[str, Any]] | None = None) -> None:
        self.pool = pool or []

    async def search(self, query: dict[str, Any], *, limit: int = 25) -> list[dict[str, Any]]:
        return self.pool[:limit]
