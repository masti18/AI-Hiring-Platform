"""Email adapter interface (SMTP / ESP implementations swap in later)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, EmailStr


class EmailMessage(BaseModel):
    to: EmailStr
    subject: str
    body_text: str
    body_html: str | None = None


class EmailAdapter(ABC):
    @abstractmethod
    async def send(self, message: EmailMessage) -> dict:
        raise NotImplementedError


class ConsoleEmailAdapter(EmailAdapter):
    """Dev stub that logs instead of sending."""

    async def send(self, message: EmailMessage) -> dict:
        return {
            "status": "logged",
            "to": str(message.to),
            "subject": message.subject,
            "adapter": "console",
        }
