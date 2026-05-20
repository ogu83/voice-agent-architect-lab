from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_VISION_MODEL = "gpt-4o-2024-08-06"

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

CLASSIFY_SYSTEM_PROMPT = """\
You classify museum-like visual entities for a multi-character voice agent demo.
Return only structured JSON that matches the requested schema.
Use the image content as evidence. If the exact person is uncertain, use a concise
visual label instead of inventing a famous identity.
"""

CLASSIFY_USER_PROMPT = """\
Classify the entity in this image for downstream voice design.

Return:
- name: the specific historical/public figure if visually credible, otherwise a concise entity label
- period: the historical era or approximate time period
- context: one short phrase describing cultural, social, or historical context
- traits: 3 to 5 adjectives describing how this entity should sound when speaking
"""


class EntityClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Specific entity name or concise visual label.")
    period: str = Field(description="Historical era or approximate time period.")
    context: str = Field(description="Short cultural, social, or historical context.")
    traits: list[str] = Field(description="Three to five voice/personality adjectives.")

    @field_validator("traits")
    @classmethod
    def require_demo_trait_count(cls, traits: list[str]) -> list[str]:
        if not 3 <= len(traits) <= 5:
            raise ValueError("traits must contain 3 to 5 adjectives")
        return traits


def encode_image_as_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_type = IMAGE_MIME_TYPES.get(suffix)
    if mime_type is None:
        supported = ", ".join(sorted(IMAGE_MIME_TYPES))
        raise ValueError(f"Unsupported image type '{suffix}'. Use one of: {supported}.")

    image_bytes = path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_classification_messages(data_url: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": CLASSIFY_USER_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def classify_entity(
    image_path: str | Path,
    *,
    client: Any | None = None,
    model: str | None = None,
) -> EntityClassification:
    data_url = encode_image_as_data_url(image_path)
    client = client or _build_openai_client()
    selected_model = model or os.getenv("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)
    messages = build_classification_messages(data_url)

    completions = client.chat.completions
    if hasattr(completions, "parse"):
        completion = completions.parse(
            model=selected_model,
            messages=messages,
            response_format=EntityClassification,
        )
        return _classification_from_completion(completion)

    completion = completions.create(
        model=selected_model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Vision model returned an empty classification response.")
    return EntityClassification.model_validate_json(content)


def _classification_from_completion(completion: Any) -> EntityClassification:
    message = completion.choices[0].message
    parsed = getattr(message, "parsed", None)
    if isinstance(parsed, EntityClassification):
        return parsed
    if parsed is not None:
        return EntityClassification.model_validate(parsed)

    content = getattr(message, "content", None)
    if not content:
        raise RuntimeError("Vision model returned no parsed classification.")
    if isinstance(content, str):
        return EntityClassification.model_validate_json(content)
    return EntityClassification.model_validate(json.loads(content))


def _build_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The live Vision demo requires the OpenAI Python SDK. "
            "Install project dependencies with: pip install -r requirements.txt"
        ) from exc

    return OpenAI()
