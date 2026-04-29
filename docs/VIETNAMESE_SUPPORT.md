# Vietnamese Support Guide

This guide explains what to change to support Vietnamese end-to-end while keeping the current architecture and logic.

## Scope

Vietnamese support in this project means:

1. Wake word can be spoken naturally by Vietnamese users.
2. Speech-to-text (STT) transcribes Vietnamese reliably.
3. Router and prompts understand Vietnamese requests and tool intents.
4. Text-to-speech (TTS) speaks Vietnamese naturally.
5. Config lets you switch language without code edits.

---

## Current blockers in repo

- STT defaults to English in `audio/stt_engine.py` (`language="en"`).
- Whisper model path defaults to an English-only model (`ggml-base.en-q5_0.bin`).
- TTS defaults to British English voice in `config/config.json` and `audio/tts_engine.py`.
- Router keywords and system prompt are English-only in `brain/router.py` and `brain/tool_definitions.py`.
- Wake phrase is currently English ("Hey Jansky").

---

## Recommended target settings for Vietnamese

- **STT language**: `vi`
- **Whisper model**: multilingual model (for example `base`, `small`, or `medium` variants, not `*.en` models)
- **TTS voice**: Vietnamese Piper voice (quality varies by voice)
- **Router language**: bilingual or Vietnamese-first prompts and keyword heuristics
- **Wake phrase**: optional Vietnamese phrase variant

---

## Python changes (current production path)

### 1) Add language fields to config

File: `config.py`

Add fields:

- `assistant_language: str = "vi"`
- `stt_language: str = "vi"`
- `tts_language: str = "vi"` (optional metadata, useful for future logic)

Also add these to `config/config.json` so runtime behavior is controlled by config.

### 2) Switch Whisper to multilingual + Vietnamese

Files:

- `config/config.json`
- `audio/stt_engine.py`
- `orchestrator.py`

Changes:

1. In `config/config.json`, set `whisper_model` to a multilingual model path (example: `ggml-base-q5_0.bin`).
2. Pass `stt_language` from config into `WhisperSTT(...)`.
3. Keep existing CLI flag behavior but use `-l vi` via that config value.

### 3) Switch Piper voice to Vietnamese

Files:

- `config/config.json`
- optional `setup.sh` (if you automate downloads)

Changes:

1. Download a Vietnamese Piper voice (`.onnx` + `.onnx.json`) into `piper/voices/`.
2. Set `piper_voice` in `config/config.json` to that file.
3. Keep `audio/tts_engine.py` logic unchanged unless the chosen voice requires speaker config changes.

### 4) Make router understand Vietnamese intents

Files:

- `brain/router.py`
- `brain/tool_definitions.py`
- `config/local_soul.md` and `config/cloud_soul.md` (optional but recommended)

Changes:

1. Add Vietnamese keyword phrases for all existing tools:
   - time/date, weather, news, system status, joke, cloud handoff.
2. Update `SYSTEM_PROMPT` to explicitly allow Vietnamese responses and tool decisions from Vietnamese queries.
3. If desired, keep bilingual phrase lists to preserve English compatibility.

### 5) Wake word strategy

File: `senses/wake_word_detector.py` plus wake model assets.

Options:

- Keep existing English wake word (lowest risk).
- Add a new Vietnamese wake-word model (best UX for Vietnamese speakers).

Important: wake-word quality depends on model training data and pronunciation coverage.

---

## C++ changes (migration path)

The same behavior should be mirrored in C++ modules:

- `src/config.hpp` / `src/config.cpp`: add language fields.
- `audio/stt_engine.*`: pass `-l vi` and use multilingual Whisper model.
- `audio/tts_engine.*`: load Vietnamese Piper voice path from config.
- `brain/router.*` + `brain/tool_definitions.*`: add Vietnamese keywords and prompt text.
- `senses/wake_word_detector.*`: optional Vietnamese wake model path.

Note: current C++ audio/STT/TTS/wake code is placeholder-level. Implement language support in parallel with runtime parity work.

---

## Suggested config example

Add these values in `config/config.json`:

```json
{
  "assistant_language": "vi",
  "stt_language": "vi",
  "tts_language": "vi",
  "whisper_model": "/home/jansky/jansky/whisper.cpp/models/ggml-base-q5_0.bin",
  "piper_voice": "/home/jansky/jansky/piper/voices/vi_VN-<voice-name>.onnx"
}
```

Keep all existing fields unchanged unless needed.

---

## Testing checklist

1. **STT smoke test**: speak 20 Vietnamese utterances, verify transcription quality.
2. **Routing parity**: confirm Vietnamese prompts map to correct `ToolType`.
3. **TTS naturalness**: check pronunciation, speaking speed, clipping.
4. **Round-trip test**: mic -> STT -> router -> TTS with Vietnamese-only prompts.
5. **Fallback behavior**: verify cloud handoff still works for complex Vietnamese questions.
6. **Wake reliability** (if new wake phrase): false positive / false reject checks.

---

## Minimal rollout plan

1. Switch STT model + `-l vi`.
2. Switch TTS to Vietnamese voice.
3. Add Vietnamese router keywords and prompt.
4. Run regression tests for existing English flows.
5. Add Vietnamese wake word model only after core pipeline is stable.
