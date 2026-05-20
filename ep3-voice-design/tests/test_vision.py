from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.vision import (
    EntityClassification,
    classify_entity,
    encode_image_as_data_url,
)


FIXTURE_IMAGE = Path(__file__).resolve().parent / "fixtures" / "demo-statue.jpg"


class FakeMessage:
    parsed = EntityClassification(
        name="Marcus Aurelius",
        period="2nd century AD",
        context="Roman emperor and Stoic philosopher",
        traits=["contemplative", "austere", "philosophical"],
    )


class FakeChoice:
    message = FakeMessage()


class FakeCompletion:
    choices = [FakeChoice()]


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return FakeCompletion()


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self):
        self.chat = FakeChat()


def test_encode_image_as_data_url_uses_file_bytes():
    data_url = encode_image_as_data_url(FIXTURE_IMAGE)

    assert data_url == "data:image/jpeg;base64,ZGVtby1pbWFnZQo="


def test_classify_entity_sends_image_and_pydantic_schema():
    fake_client = FakeClient()

    entity = classify_entity(FIXTURE_IMAGE, client=fake_client, model="gpt-4o-demo")

    assert entity.name == "Marcus Aurelius"
    call = fake_client.chat.completions.calls[0]
    assert call["model"] == "gpt-4o-demo"
    assert call["response_format"] is EntityClassification
    content = call["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_encode_image_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="Unsupported image type"):
        encode_image_as_data_url(Path(__file__))
