import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.session_manager import SessionManager


def test_get_or_generate_voice_returns_cache_hit_without_calling_generator():
    async def run():
        manager = SessionManager(voice_cache={"Marcus Aurelius": "voice_cached"})
        calls = []

        async def generator():
            calls.append("called")
            return "voice_new"

        voice_id = await manager.get_or_generate_voice("Marcus Aurelius", generator)

        assert voice_id == "voice_cached"
        assert calls == []

    asyncio.run(run())


def test_get_or_generate_voice_caches_miss_result():
    async def run():
        manager = SessionManager()

        async def generator():
            return "voice_generated"

        voice_id = await manager.get_or_generate_voice("River Tiber God", generator)

        assert voice_id == "voice_generated"
        assert manager.voice_cache["River Tiber God"] == "voice_generated"

    asyncio.run(run())


def test_start_voice_generation_runs_background_cache_miss_once():
    async def run():
        manager = SessionManager()
        calls = []

        async def generator():
            calls.append("called")
            await asyncio.sleep(0)
            return "voice_background"

        first = manager.start_voice_generation("River Tiber God", generator)
        second = manager.start_voice_generation("River Tiber God", generator)
        voice_id = await second

        assert first is second
        assert voice_id == "voice_background"
        assert calls == ["called"]
        assert manager.voice_cache["River Tiber God"] == "voice_background"

    asyncio.run(run())
