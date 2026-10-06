"""Outbound messaging adapters (WhatsApp, SMS). Stubbed until outreach milestones."""

from abc import ABC, abstractmethod
from typing import Any


class MessagingAdapter(ABC):
    @abstractmethod
    async def send(self, to: str, body: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError


class ConsoleMessagingAdapter(MessagingAdapter):
    async def send(self, to: str, body: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": "logged", "to": to, "channel": "console", "metadata": metadata or {}}


class WhatsAppMessagingAdapter(MessagingAdapter):
    """Placeholder for WhatsApp Business API behind the interface."""

    async def send(self, to: str, body: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError("WhatsApp messaging adapter not implemented yet")
