from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.conversation import DEFAULT_DEMO_QUESTION, build_character_reply
from pipeline.session_manager import SessionManager
from pipeline.vision import EntityClassification, classify_entity
from pipeline.voice_designer import (
    build_voice_description,
    design_voice_preview,
    generate_voice,
    synthesize_speech,
)


DEFAULT_CACHE_PATH = Path("ep3-voice-design/artifacts/full-pipeline-voice-cache.json")
DEFAULT_OUTPUT_DIR = Path("ep3-voice-design/artifacts/full-pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the EP3 Slide 9 image-to-character-voice pipeline demo."
    )
    parser.add_argument(
        "images",
        type=Path,
        nargs="+",
        help="One or more exhibit images. Use three images for the Slide 9 recording.",
    )
    parser.add_argument("--question", default=DEFAULT_DEMO_QUESTION)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force-voices", action="store_true", help="Ignore cached voice IDs.")
    parser.add_argument("--preview-only", action="store_true", help="Use Voice Design preview audio without persisting voice IDs.")
    parser.add_argument("--no-pause", action="store_true", help="Do not pause before each classify/play step.")
    parser.add_argument("--play", action="store_true", help="Open each generated MP3 during the demo.")
    return parser.parse_args()


async def run_demo(args: argparse.Namespace) -> list[dict[str, Any]]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache_data = load_cache(args.cache)
    if args.force_voices:
        cache_data = {}

    manager = SessionManager(
        voice_cache={
            entity_name: entry["voice_id"]
            for entity_name, entry in cache_data.items()
            if isinstance(entry, dict) and entry.get("voice_id")
        }
    )

    results: list[dict[str, Any]] = []
    for index, image_path in enumerate(args.images, start=1):
        result = await run_entity_pipeline(index, image_path, args, manager, cache_data)
        results.append(result)

    save_cache(args.cache, cache_data)
    return results


async def run_entity_pipeline(
    index: int,
    image_path: Path,
    args: argparse.Namespace,
    manager: SessionManager,
    cache_data: dict[str, Any],
) -> dict[str, Any]:
    resolved_image = image_path.resolve()
    if not resolved_image.exists():
        raise FileNotFoundError(f"Image file not found: {resolved_image}")

    print()
    print(f"=== Exhibit {index}: {resolved_image.name} ===")
    pause(args, f"[demo] Press Enter to classify exhibit {index}...")

    stage_start = time.perf_counter()
    print(f"[vision] image: {resolved_image}")
    entity = await asyncio.to_thread(classify_entity, resolved_image)
    print("[vision] EntityClassification:")
    print(entity.model_dump_json(indent=2))

    description = build_voice_description(entity.name, entity.period, entity.context, entity.traits)
    print("[voice_description]")
    print(description)

    reply = build_character_reply(entity, args.question)
    print("[conversation] question:")
    print(args.question)
    print("[conversation] character reply:")
    print(reply)

    slug = slugify(entity.name)
    if args.preview_only:
        audio_path, voice_id, cache_status = await generate_preview_only_audio(
            entity=entity,
            description=description,
            reply=reply,
            output_dir=args.output_dir,
            slug=slug,
        )
        generated_voice_id = voice_id
    else:
        voice_id, generated_voice_id, cache_status = await get_or_create_voice(
            entity=entity,
            description=description,
            reply=reply,
            output_dir=args.output_dir,
            manager=manager,
            cache_data=cache_data,
        )
        audio_path = await asyncio.to_thread(
            synthesize_speech,
            voice_id=voice_id,
            text=reply,
            output_path=args.output_dir / f"{slug}-character-reply.mp3",
        )

    elapsed = time.perf_counter() - stage_start
    print(f"[audio] character voice: {audio_path.resolve()}")
    print(f"[timing] exhibit {index}: {elapsed:.2f}s ({cache_status})")
    if args.play:
        pause(args, f"[demo] Press Enter to play {entity.name}...")
        open_audio(audio_path)

    return {
        "image": str(resolved_image),
        "entity": entity.model_dump(),
        "voice_id": voice_id,
        "generated_voice_id": generated_voice_id,
        "audio": str(audio_path.resolve()),
        "cache_status": cache_status,
        "elapsed_seconds": round(elapsed, 2),
    }


async def get_or_create_voice(
    *,
    entity: EntityClassification,
    description: str,
    reply: str,
    output_dir: Path,
    manager: SessionManager,
    cache_data: dict[str, Any],
) -> tuple[str, str, str]:
    cached_voice_id = manager.get_cached_voice(entity.name)
    if cached_voice_id:
        generated_voice_id = cache_data.get(entity.name, {}).get("generated_voice_id", "")
        print(f"[cache] hit: {entity.name} -> {cached_voice_id}")
        return cached_voice_id, generated_voice_id, "cache hit"

    print(f"[cache] miss: {entity.name}")
    print("[elevenlabs] generating voice...")
    result_holder: dict[str, Any] = {}

    async def generator() -> str:
        result = await asyncio.to_thread(
            generate_voice,
            description,
            voice_name=entity.name,
            output_dir=output_dir,
            preview_text=reply,
        )
        result_holder["result"] = result
        return result.voice_id

    try:
        voice_id = await manager.get_or_generate_voice(entity.name, generator)
    except RuntimeError as exc:
        if "feature_not_available" in str(exc):
            raise RuntimeError(
                "ElevenLabs refused persisted voice creation. Upgrade to a paid plan "
                "or rerun with --preview-only for a recording fallback."
            ) from exc
        raise

    result = result_holder["result"]
    cache_data[entity.name] = {
        "voice_id": result.voice_id,
        "generated_voice_id": result.generated_voice_id,
        "description": result.description,
        "preview_audio_path": str(result.preview_audio_path),
    }
    print(f"[elevenlabs] generated_voice_id: {result.generated_voice_id}")
    print(f"[elevenlabs] voice_id: {voice_id}")
    print(f"[cache] stored: {entity.name} -> {voice_id}")
    return voice_id, result.generated_voice_id, "cache miss"


async def generate_preview_only_audio(
    *,
    entity: EntityClassification,
    description: str,
    reply: str,
    output_dir: Path,
    slug: str,
) -> tuple[Path, str, str]:
    print("[cache] preview-only: skipping persisted voice_id cache")
    preview = await asyncio.to_thread(
        design_voice_preview,
        description,
        preview_text=reply,
    )
    audio_path = output_dir / f"{slug}-preview-only-reply.mp3"
    audio_path.write_bytes(preview.audio_bytes)
    print(f"[elevenlabs] generated_voice_id: {preview.generated_voice_id}")
    return audio_path, preview.generated_voice_id, "preview only"


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def save_cache(cache_path: Path, cache_data: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def pause(args: argparse.Namespace, message: str) -> None:
    if args.no_pause:
        print(message)
        return
    input(message)


def open_audio(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path.resolve())  # type: ignore[attr-defined]
        return
    print(f"[play] open manually: {path.resolve()}")


def main() -> int:
    load_dotenv()
    args = parse_args()
    results = asyncio.run(run_demo(args))
    print()
    print("[summary]")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
