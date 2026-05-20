# EP3 Voice Design

Vision-guided persona generation and in-session voice switching.

## Slide 4 live demo

Use a real local image captured from your phone. The Vision stage reads the image
bytes, encodes them as a base64 data URL, sends them to GPT-4o, and validates the
result as an `EntityClassification` Pydantic model.

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY="sk-..."
python ep3-voice-design\demo\statue_demo.py C:\path\to\roman-statue.jpg --classify-only
```

You can also put `OPENAI_API_KEY` in a local `.env`; the demo loads it
automatically.

Expected terminal shape:

```json
{
  "name": "Marcus Aurelius",
  "period": "2nd century AD",
  "context": "Roman emperor and Stoic philosopher",
  "traits": [
    "contemplative",
    "austere",
    "philosophical"
  ]
}
```

For the later pipeline slides, omit `--classify-only` to also build the local
voice persona scaffold from the classification.

## Slide 6 live demo

The real ElevenLabs Voice Design flow has two API calls:

1. `POST /v1/text-to-voice/design` returns preview audio plus a `generated_voice_id`.
2. `POST /v1/text-to-voice` persists that preview and returns the reusable `voice_id`.

Run the demo:

```powershell
$env:ELEVENLABS_API_KEY="..."
python ep3-voice-design\demo\voice_design_demo.py
```

The script:

- creates a generic reference MP3 with a stock voice
- generates a Roman statue voice from the default description
- writes generated preview audio to `ep3-voice-design\artifacts`
- stores `entity -> voice_id` in `ep3-voice-design\artifacts\voice-cache.json`
- prints the generic and generated audio file paths

To open the audio files automatically on Windows:

```powershell
python ep3-voice-design\demo\voice_design_demo.py --play
```

Run it a second time to show the cache hit path:

```powershell
python ep3-voice-design\demo\voice_design_demo.py
```

Use `--force` only when you deliberately want to generate a new ElevenLabs voice.

## Slide 9 full pipeline demo

Use three local exhibit images for the final live screen recording:

```powershell
$env:OPENAI_API_KEY="..."
$env:ELEVENLABS_API_KEY="..."
python ep3-voice-design\demo\full_pipeline_demo.py `
  C:\path\to\roman-statue.jpg `
  C:\path\to\darwin-portrait.jpg `
  C:\path\to\renaissance-merchant.jpg `
  --play
```

The script pauses before each exhibit so the terminal behaves like a live
`Classify` button. For each image it prints:

- Vision classification JSON
- voice description text
- user question and character reply
- cache hit or cache miss
- ElevenLabs `generated_voice_id` and persisted `voice_id`
- generated character audio path

Run it once before recording to populate the cache. Then run it again during the
recording; cached voices avoid the slow voice creation path and only synthesize
the character reply audio.

If your ElevenLabs plan still cannot persist generated voices, use preview-only
mode as a fallback:

```powershell
python ep3-voice-design\demo\full_pipeline_demo.py `
  C:\path\to\roman-statue.jpg `
  C:\path\to\darwin-portrait.jpg `
  C:\path\to\renaissance-merchant.jpg `
  --preview-only --play
```

Preview-only mode still gives you the audible character-voice payoff, but it does
not demonstrate reusable `voice_id` caching.
