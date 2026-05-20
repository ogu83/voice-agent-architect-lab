from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.parallel_gen import generate_group
from pipeline.session_manager import SessionManager
from pipeline.vision import (
    DEFAULT_VISION_MODEL,
    EntityClassification,
    classify_entity,
    encode_image_as_data_url,
)


async def build_voice_demo(entity: EntityClassification) -> dict:
    primary_trait = entity.traits[0] if entity.traits else "measured"
    personas = await generate_group(
        [
            (entity.name, entity.period, primary_trait),
            ("narrator", "modern", "friendly"),
        ]
    )
    mgr = SessionManager()
    active = mgr.set_voice(entity.name, personas[entity.name])
    return {
        "entity": entity.model_dump(),
        "active_voice": active,
        "voice": mgr.get_active(),
    }


async def run_demo(image_path: str | Path, *, model: str | None = None) -> dict:
    entity = classify_entity(image_path, model=model)
    return await build_voice_demo(entity)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the EP3 live Vision demo against a local statue/exhibit image."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to a .jpg, .jpeg, .png, or .webp image captured from your phone.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL),
        help="OpenAI vision model to use. Defaults to OPENAI_VISION_MODEL or GPT-4o.",
    )
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Stop after printing the EntityClassification JSON for the Slide 4 demo.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    image_path = args.image.resolve()
    if not image_path.exists():
        print(f"[error] Image file not found: {image_path}", file=sys.stderr)
        return 2

    print(f"[vision] image: {image_path}")
    print(f"[vision] bytes: {image_path.stat().st_size:,}")
    data_url = encode_image_as_data_url(image_path)
    print(f"[vision] base64 data URL: {data_url.split(',', 1)[0]},... ({len(data_url):,} chars)")
    print(f"[vision] model: {args.model}")
    print("[vision] calling OpenAI...")

    entity = classify_entity(image_path, model=args.model)
    print("[vision] EntityClassification JSON:")
    print(entity.model_dump_json(indent=2))

    if args.classify_only:
        return 0

    print("[pipeline] building local voice persona scaffold...")
    result = asyncio.run(build_voice_demo(entity))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
