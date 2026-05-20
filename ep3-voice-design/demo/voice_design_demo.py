from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.session_manager import SessionManager
from pipeline.voice_designer import (
    DEFAULT_GENERIC_VOICE_ID,
    ROMAN_PREVIEW_TEXT,
    ROMAN_STATUE_DESCRIPTION,
    generate_voice,
    synthesize_speech,
)


DEFAULT_ENTITY_NAME = "River Tiber God Statue"
DEFAULT_CACHE_PATH = Path("ep3-voice-design/artifacts/voice-cache.json")
DEFAULT_OUTPUT_DIR = Path("ep3-voice-design/artifacts")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the EP3 Slide 6 ElevenLabs Voice Design demo."
    )
    parser.add_argument("--entity-name", default=DEFAULT_ENTITY_NAME)
    parser.add_argument("--voice-name", default=DEFAULT_ENTITY_NAME)
    parser.add_argument("--description", default=ROMAN_STATUE_DESCRIPTION)
    parser.add_argument("--preview-text", default=ROMAN_PREVIEW_TEXT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--generic-voice-id", default=DEFAULT_GENERIC_VOICE_ID)
    parser.add_argument("--force", action="store_true", help="Ignore cache and generate a new voice.")
    parser.add_argument("--play", action="store_true", help="Open the generic and generated MP3 files.")
    return parser.parse_args()


async def run_demo(args: argparse.Namespace) -> dict[str, Any]:
    cache_data = load_cache(args.cache)
    manager = SessionManager(
        voice_cache={
            entity_name: entry["voice_id"]
            for entity_name, entry in cache_data.items()
            if isinstance(entry, dict) and entry.get("voice_id")
        }
    )
    if args.force:
        manager.voice_cache.pop(args.entity_name, None)
        cache_data.pop(args.entity_name, None)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.entity_name)
    generic_path = args.output_dir / f"{slug}-generic-reference.mp3"

    print("[generic] synthesizing neutral reference voice...")
    if args.force or not generic_path.exists():
        synthesize_speech(
            voice_id=args.generic_voice_id,
            text=args.preview_text,
            output_path=generic_path,
        )
    print(f"[generic] audio: {generic_path.resolve()}")

    cached_voice_id = manager.get_cached_voice(args.entity_name)
    if cached_voice_id:
        print(f"[cache] hit: {args.entity_name} -> {cached_voice_id}")
        generated_path = await ensure_generated_audio_for_cache_hit(
            voice_id=cached_voice_id,
            preview_text=args.preview_text,
            output_path=args.output_dir / f"{slug}-generated-from-cache.mp3",
        )
        voice_id = cached_voice_id
        generated_voice_id = cache_data.get(args.entity_name, {}).get("generated_voice_id", "")
    else:
        print(f"[cache] miss: {args.entity_name}")
        print("[session] starting background voice generation...")

        result_holder: dict[str, Any] = {}

        async def generator() -> str:
            result = await asyncio.to_thread(
                generate_voice,
                args.description,
                voice_name=args.voice_name,
                output_dir=args.output_dir,
                preview_text=args.preview_text,
            )
            result_holder["result"] = result
            return result.voice_id

        voice_id = await manager.get_or_generate_voice(args.entity_name, generator)
        result = result_holder["result"]
        generated_voice_id = result.generated_voice_id
        generated_path = result.preview_audio_path
        cache_data[args.entity_name] = {
            "voice_id": result.voice_id,
            "generated_voice_id": result.generated_voice_id,
            "preview_audio_path": str(result.preview_audio_path),
            "description": result.description,
            "preview_text": result.preview_text,
        }
        save_cache(args.cache, cache_data)
        print(f"[elevenlabs] generated_voice_id: {generated_voice_id}")
        print(f"[elevenlabs] voice_id: {voice_id}")
        print(f"[cache] stored: {args.entity_name} -> {voice_id}")

    print(f"[generated] audio: {generated_path.resolve()}")
    if args.play:
        print("[play] opening generic reference audio...")
        open_audio(generic_path)
        input("[play] press Enter to open generated statue voice...")
        open_audio(generated_path)

    return {
        "entity_name": args.entity_name,
        "voice_id": voice_id,
        "generated_voice_id": generated_voice_id,
        "generic_audio": str(generic_path.resolve()),
        "generated_audio": str(generated_path.resolve()),
        "cache": str(args.cache.resolve()),
    }


async def ensure_generated_audio_for_cache_hit(
    *,
    voice_id: str,
    preview_text: str,
    output_path: Path,
) -> Path:
    if output_path.exists():
        return output_path
    return await asyncio.to_thread(
        synthesize_speech,
        voice_id=voice_id,
        text=preview_text,
        output_path=output_path,
    )


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def save_cache(cache_path: Path, cache_data: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def open_audio(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path.resolve())  # type: ignore[attr-defined]
        return
    print(f"[play] open manually: {path.resolve()}")


def main() -> int:
    load_dotenv()
    args = parse_args()
    result = asyncio.run(run_demo(args))
    print("[result]")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
