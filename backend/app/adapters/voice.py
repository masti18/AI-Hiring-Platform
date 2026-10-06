"""Voice adapters: Deepgram (STT), ElevenLabs (TTS), LiveKit (transport).

Implementations stay stubbed until voice milestones. Interfaces keep the pipeline mockable.
"""

from abc import ABC, abstractmethod
from typing import Any


class SpeechToTextAdapter(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> dict[str, Any]:
        raise NotImplementedError


class TextToSpeechAdapter(ABC):
    @abstractmethod
    async def synthesize(self, text: str, *, voice_id: str | None = None) -> bytes:
        raise NotImplementedError


class CallTransportAdapter(ABC):
    @abstractmethod
    async def create_room(self, room_name: str) -> dict[str, Any]:
        raise NotImplementedError


class MockSTTAdapter(SpeechToTextAdapter):
    async def transcribe(self, audio_bytes: bytes, *, language: str = "en") -> dict[str, Any]:
        return {
            "provider": "mock-deepgram",
            "language": language,
            "transcript": "",
            "words": [],
            "bytes_received": len(audio_bytes),
        }


class MockTTSAdapter(TextToSpeechAdapter):
    async def synthesize(self, text: str, *, voice_id: str | None = None) -> bytes:
        return text.encode("utf-8")


class MockCallTransportAdapter(CallTransportAdapter):
    async def create_room(self, room_name: str) -> dict[str, Any]:
        return {"provider": "mock-livekit", "room": room_name, "url": "mock://room"}
