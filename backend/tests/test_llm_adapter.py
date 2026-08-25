"""LLM provider interface tests."""

import pytest

from app.adapters.llm import LLMMessage, MockLLMProvider, OpenAILLMProvider


@pytest.mark.asyncio
async def test_mock_llm_returns_structured_json() -> None:
    provider = MockLLMProvider(canned={"score": 0.9})
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.provider == "mock"
    assert result.data["score"] == 0.9


@pytest.mark.asyncio
async def test_openai_stub_without_api_key() -> None:
    provider = OpenAILLMProvider(api_key="", model="gpt-4o")
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.data["stub"] is True
    assert result.provider == "openai"
