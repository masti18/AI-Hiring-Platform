"""Swappable LLM provider interface. Default: OpenAI GPT-4.x."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMStructuredResult(BaseModel):
    """All AI outputs must be structured JSON for downstream nodes + audit trail."""

    provider: str
    model: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw_text: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> LLMStructuredResult:
        raise NotImplementedError


class OpenAILLMProvider(LLMProvider):
    """OpenAI adapter. Real API calls land in later milestones; skeleton validates wiring."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.llm_model

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> LLMStructuredResult:
        if not self.api_key:
            # Skeleton mode: return a structured stub so the graph can be developed offline.
            return LLMStructuredResult(
                provider="openai",
                model=self.model,
                data={
                    "stub": True,
                    "message": "OPENAI_API_KEY not set; returning structured stub.",
                    "schema_requested": response_schema is not None,
                    "input_roles": [m.role for m in messages],
                },
                raw_text=None,
                usage={},
            )

        # Real OpenAI call is implemented when Milestone prompts require LLM features.
        # Keeping the import local avoids hard failure when openai is unused in CI.
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[m.model_dump() for m in messages],
            temperature=temperature,
            response_format={"type": "json_object"} if response_schema else None,
        )
        content = response.choices[0].message.content or "{}"
        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {"text": content}

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return LLMStructuredResult(
            provider="openai",
            model=self.model,
            data=data if isinstance(data, dict) else {"value": data},
            raw_text=content,
            usage=usage,
        )


class MockLLMProvider(LLMProvider):
    """Deterministic provider for unit tests."""

    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.canned = canned or {"ok": True}

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> LLMStructuredResult:
        return LLMStructuredResult(
            provider="mock",
            model="mock-1",
            data=self.canned,
            raw_text=None,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
