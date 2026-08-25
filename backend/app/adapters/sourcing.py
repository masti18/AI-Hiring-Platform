"""Candidate sourcing adapters (LinkedIn, etc.). Implementations land in sourcing milestones."""

from abc import ABC, abstractmethod
from typing import Any


class SourcingAdapter(ABC):
    @abstractmethod
    async def search(self, query: dict[str, Any], *, limit: int = 25) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockSourcingAdapter(SourcingAdapter):
    async def search(self, query: dict[str, Any], *, limit: int = 25) -> list[dict[str, Any]]:
        return []


class LinkedInSourcingAdapter(SourcingAdapter):
    """Placeholder for LinkedIn / Recruiter API integration behind the interface."""

    async def search(self, query: dict[str, Any], *, limit: int = 25) -> list[dict[str, Any]]:
        raise NotImplementedError("LinkedIn sourcing adapter not implemented yet")
