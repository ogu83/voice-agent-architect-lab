from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable


VoiceGenerator = Callable[[], Awaitable[str]]


@dataclass
class SessionManager:
    active_voice_id: str | None = None
    voice_cache: dict[str, str] = field(default_factory=dict)
    voices: dict[str, dict] = field(default_factory=dict)
    pending_generations: dict[str, asyncio.Task[str]] = field(default_factory=dict)

    def set_voice(self, name: str, persona: dict) -> str:
        voice_id = f"voice_{name}"
        self.voices[voice_id] = persona
        self.active_voice_id = voice_id
        return voice_id

    def get_active(self) -> dict | None:
        if not self.active_voice_id:
            return None
        return self.voices[self.active_voice_id]

    def get_cached_voice(self, entity_name: str) -> str | None:
        return self.voice_cache.get(entity_name)

    def cache_voice(self, entity_name: str, voice_id: str) -> str:
        self.voice_cache[entity_name] = voice_id
        return voice_id

    async def get_or_generate_voice(self, entity_name: str, generator: VoiceGenerator) -> str:
        cached_voice_id = self.get_cached_voice(entity_name)
        if cached_voice_id:
            self.active_voice_id = cached_voice_id
            return cached_voice_id

        task = self.start_voice_generation(entity_name, generator)
        voice_id = await task
        self.active_voice_id = voice_id
        return voice_id

    def start_voice_generation(self, entity_name: str, generator: VoiceGenerator) -> asyncio.Task[str]:
        cached_voice_id = self.get_cached_voice(entity_name)
        if cached_voice_id:
            return _completed_task(cached_voice_id)

        pending = self.pending_generations.get(entity_name)
        if pending:
            return pending

        task = asyncio.create_task(self._generate_and_cache(entity_name, generator))
        self.pending_generations[entity_name] = task
        task.add_done_callback(lambda _: self.pending_generations.pop(entity_name, None))
        return task

    async def _generate_and_cache(self, entity_name: str, generator: VoiceGenerator) -> str:
        voice_id = await generator()
        self.cache_voice(entity_name, voice_id)
        return voice_id


def _completed_task(value: str) -> asyncio.Task[str]:
    async def done() -> str:
        return value

    return asyncio.create_task(done())
