from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.voice_designer import generate_voice, synthesize_speech


OUTPUT_DIR = Path(__file__).resolve().parent / "fixtures" / "voice-output"


class FakeResponse:
    def __init__(self, json_data=None, content=b"", headers=None):
        self._json_data = json_data or {}
        self.content = content
        self.headers = headers or {}
        self.text = str(self._json_data)
        self.status_code = 200

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self):
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/v1/text-to-voice/design"):
            return FakeResponse(
                {
                    "previews": [
                        {
                            "generated_voice_id": "generated_roman",
                            "audio_base_64": "cHJldmlldy1tcDM=",
                            "media_type": "audio/mpeg",
                        }
                    ]
                }
            )
        if url.endswith("/v1/text-to-voice"):
            return FakeResponse({"voice_id": "voice_roman"})
        raise AssertionError(f"unexpected URL: {url}")


def test_generate_voice_designs_preview_creates_voice_and_writes_audio():
    fake_client = FakeClient()
    preview_path = OUTPUT_DIR / "tiber-river-god-generated-preview.mp3"
    preview_path.unlink(missing_ok=True)

    result = generate_voice(
        description="A mature Roman river god voice, grave and resonant.",
        voice_name="Tiber River God",
        api_key="test-key",
        client=fake_client,
        output_dir=OUTPUT_DIR,
        preview_text="I have watched the river carry the memory of Rome through stone and empire.",
    )

    assert result.voice_id == "voice_roman"
    assert result.generated_voice_id == "generated_roman"
    assert result.preview_audio_path.read_bytes() == b"preview-mp3"
    design_url, design_kwargs = fake_client.posts[0]
    assert design_url.endswith("/v1/text-to-voice/design")
    assert design_kwargs["headers"]["xi-api-key"] == "test-key"
    assert design_kwargs["json"]["voice_description"].startswith("A mature Roman")
    create_url, create_kwargs = fake_client.posts[1]
    assert create_url.endswith("/v1/text-to-voice")
    assert create_kwargs["json"]["generated_voice_id"] == "generated_roman"


def test_synthesize_speech_writes_binary_audio():
    class SpeechClient:
        def __init__(self):
            self.posts = []

        def post(self, url, **kwargs):
            self.posts.append((url, kwargs))
            return FakeResponse(content=b"spoken-audio", headers={"content-type": "audio/mpeg"})

    client = SpeechClient()
    output_path = OUTPUT_DIR / "speech.mp3"
    output_path.unlink(missing_ok=True)

    saved_path = synthesize_speech(
        voice_id="voice_roman",
        text="Rome remembers every stone.",
        output_path=output_path,
        api_key="test-key",
        client=client,
    )

    assert saved_path == output_path
    assert output_path.read_bytes() == b"spoken-audio"
    url, kwargs = client.posts[0]
    assert url.endswith("/v1/text-to-speech/voice_roman")
    assert kwargs["json"]["text"] == "Rome remembers every stone."
