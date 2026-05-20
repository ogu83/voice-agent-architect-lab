from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import httpx


ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
DEFAULT_VOICE_DESIGN_MODEL = "eleven_multilingual_ttv_v2"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_GENERIC_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

ROMAN_STATUE_DESCRIPTION = (
    "A mature male voice with a grave, resonant baritone and slow ceremonial pacing. "
    "The tone is ancient, reflective, and authoritative, like a weathered Roman river "
    "deity speaking from carved marble. The delivery should feel calm and monumental, "
    "with a slight roughness that suggests stone, age, and command."
)

ROMAN_PREVIEW_TEXT = (
    "I have watched the river carry the memory of Rome through stone, empire, and ruin. "
    "Ask your question, and I will answer with the patience of old waters and the weight "
    "of a city that learned to endure."
)


@dataclass
class VoicePersona:
    description: str
    accent: str
    timbre: str


@dataclass
class VoicePreview:
    generated_voice_id: str
    audio_bytes: bytes
    media_type: str


@dataclass
class VoiceGenerationResult:
    voice_id: str
    generated_voice_id: str
    preview_audio_path: Path
    description: str
    preview_text: str


def build_voice_persona(label: str, era: str, mood: str) -> VoicePersona:
    description = f"{mood} {era} {label} narrator"
    accent = "neutral"
    timbre = "warm" if mood in {"calm", "friendly"} else "bright"
    return VoicePersona(description=description, accent=accent, timbre=timbre)


def build_voice_description(name: str, period: str, context: str, traits: list[str]) -> str:
    trait_text = ", ".join(traits)
    return (
        f"A character voice for {name}, from {period}, in the context of {context}. "
        f"The voice should sound {trait_text}. Use a specific vocal register, texture, "
        "pacing, and accent rather than a generic narrator voice."
    )


def design_voice_preview(
    description: str,
    *,
    preview_text: str = ROMAN_PREVIEW_TEXT,
    api_key: str | None = None,
    client: Any | None = None,
    model_id: str = DEFAULT_VOICE_DESIGN_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> VoicePreview:
    client = client or httpx.Client(timeout=60)
    response = client.post(
        f"{ELEVENLABS_BASE_URL}/v1/text-to-voice/design",
        headers=_elevenlabs_headers(api_key),
        params={"output_format": output_format},
        json={
            "voice_description": description,
            "text": preview_text,
            "model_id": model_id,
            "loudness": 0.0,
        },
    )
    _raise_for_elevenlabs_error(response)
    data = response.json()
    previews = data.get("previews") or []
    if not previews:
        raise RuntimeError("ElevenLabs returned no voice previews.")

    preview = previews[0]
    generated_voice_id = preview.get("generated_voice_id")
    audio_base64 = preview.get("audio_base_64")
    if not generated_voice_id or not audio_base64:
        raise RuntimeError("ElevenLabs preview response is missing generated_voice_id or audio.")

    return VoicePreview(
        generated_voice_id=generated_voice_id,
        audio_bytes=base64.b64decode(audio_base64),
        media_type=preview.get("media_type", "audio/mpeg"),
    )


def create_voice_from_preview(
    *,
    voice_name: str,
    description: str,
    generated_voice_id: str,
    api_key: str | None = None,
    client: Any | None = None,
) -> str:
    client = client or httpx.Client(timeout=60)
    response = client.post(
        f"{ELEVENLABS_BASE_URL}/v1/text-to-voice",
        headers=_elevenlabs_headers(api_key),
        json={
            "voice_name": voice_name,
            "voice_description": description,
            "generated_voice_id": generated_voice_id,
        },
    )
    _raise_for_elevenlabs_error(response)
    voice_id = response.json().get("voice_id")
    if not voice_id:
        raise RuntimeError("ElevenLabs create voice response did not include voice_id.")
    return voice_id


def generate_voice(
    description: str,
    *,
    voice_name: str,
    api_key: str | None = None,
    client: Any | None = None,
    output_dir: str | Path = "ep3-voice-design/artifacts",
    preview_text: str = ROMAN_PREVIEW_TEXT,
) -> VoiceGenerationResult:
    preview = design_voice_preview(
        description,
        preview_text=preview_text,
        api_key=api_key,
        client=client,
    )
    output_path = _preview_audio_path(output_dir, voice_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(preview.audio_bytes)

    voice_id = create_voice_from_preview(
        voice_name=voice_name,
        description=description,
        generated_voice_id=preview.generated_voice_id,
        api_key=api_key,
        client=client,
    )
    return VoiceGenerationResult(
        voice_id=voice_id,
        generated_voice_id=preview.generated_voice_id,
        preview_audio_path=output_path,
        description=description,
        preview_text=preview_text,
    )


def synthesize_speech(
    *,
    voice_id: str,
    text: str,
    output_path: str | Path,
    api_key: str | None = None,
    client: Any | None = None,
    model_id: str = DEFAULT_TTS_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> Path:
    client = client or httpx.Client(timeout=60)
    response = client.post(
        f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{voice_id}",
        headers=_elevenlabs_headers(api_key),
        params={"output_format": output_format},
        json={"text": text, "model_id": model_id},
    )
    _raise_for_elevenlabs_error(response)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def _elevenlabs_headers(api_key: str | None = None) -> dict[str, str]:
    selected_api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not selected_api_key:
        raise RuntimeError("Set ELEVENLABS_API_KEY before running the voice design demo.")
    return {"xi-api-key": selected_api_key, "Content-Type": "application/json"}


def _raise_for_elevenlabs_error(response: Any) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text[:600]
        raise RuntimeError(f"ElevenLabs API error {response.status_code}: {body}") from exc


def _preview_audio_path(output_dir: str | Path, voice_name: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", voice_name).strip("-").lower()
    return Path(output_dir) / f"{slug}-generated-preview.mp3"
