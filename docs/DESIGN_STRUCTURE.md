# PiBot Local Agent - Detailed Design Structure

## 1) Project Purpose

This project is a wake-word-activated voice assistant designed for Raspberry Pi.
It uses:
- local audio capture and playback,
- local speech-to-text (Whisper.cpp),
- local routing/chat (Ollama + Qwen 2.5 1.5B),
- optional cloud handoff (Moonshot Kimi),
- optional visual face UI (PyGame).

The top-level orchestration is implemented in `orchestrator.py`.

---

## 2) High-Level Architecture

The system is organized into these layers:

- `senses/` - always-on wake-word listening.
- `audio/` - microphone recording, silence detection, speaker playback, STT, TTS.
- `brain/` - query routing, local model interaction, external tool calls, cloud handoff.
- `ui/` - visual state display for interaction lifecycle.
- `config/` - runtime configuration and prompt/personality files.
- `tests/` - executable integration checks.

Main execution pipeline:

1. Wake word detector listens continuously.
2. On wake trigger, detector pauses and mic is reused for user utterance recording.
3. Recorded audio is transcribed to text.
4. Router decides:
   - direct local response,
   - local tool execution,
   - or cloud handoff.
5. Response text is synthesized to speech and played.
6. System returns to idle and resumes wake detection.

---

## 3) Repository Design Map

### Core runtime

- `orchestrator.py`
  - main process lifecycle controller.
  - creates and wires every subsystem.
  - owns state transitions: idle -> listening -> thinking -> speaking -> idle.
  - handles graceful shutdown (`SIGINT`/`SIGTERM`) and cleanup.

- `config.py`
  - `Config` dataclass with defaults.
  - load order:
    1) dataclass defaults,
    2) `config/config.json`,
    3) `.env` file,
    4) environment variable overrides.
  - avoids writing API keys back to JSON in `save()`.

### Audio layer (`audio/`)

- `audio_manager.py`
  - resolves mic/speaker devices by name.
  - records with `sounddevice.InputStream`.
  - silence-based utterance endpointing.
  - normalizes low-amplitude mic input.
  - downsamples 48kHz -> 16kHz by decimation for STT compatibility.
  - mutes mic during playback to reduce feedback loop.

- `stt_engine.py`
  - wrapper around Whisper.cpp CLI.
  - accepts either WAV path or in-memory numpy audio.
  - writes temporary WAV for array mode and parses CLI output.

- `tts_engine.py`
  - wrapper around `piper-tts` Python API.
  - loads ONNX voice model once at init.
  - synthesizes text into WAV files for playback.

### Brain layer (`brain/`)

- `router.py`
  - primary decision unit.
  - asks Ollama with tool schema (`tool_definitions.py`).
  - supports both:
    - structured tool calls from model,
    - text/keyword fallback detection if model output is not structured.
  - keeps short conversation history window.
  - routes unresolved/complex prompts to cloud handoff.

- `ollama_client.py`
  - local HTTP API client for Ollama chat endpoint.
  - parses optional tool call objects.
  - supports non-stream and stream response modes.

- `cloud_client.py`
  - Moonshot/Kimi client.
  - optional system "soul" prompt injection from markdown file.
  - supports streaming and non-streaming API usage.

- `tool_definitions.py`
  - declarative function-calling schema used by local model.
  - defines:
    - `get_current_time`,
    - `get_weather`,
    - `get_news`,
    - `get_system_status`,
    - `get_joke`,
    - `cloud_handoff`.

- `brain/tools/`
  - `time_tool.py` - local time/date formatting.
  - `weather_tool.py` - OpenWeatherMap integration.
  - `news_tool.py` - NewsAPI top headlines.
  - `system_tool.py` - host metrics from `/proc`, `/sys`, `statvfs`.
  - `joke_tool.py` - Official Joke API integration.

### Sensing layer (`senses/`)

- `wake_word_detector.py`
  - openWakeWord model inference loop.
  - records mic in 48k chunks, normalizes, decimates to 16k for model.
  - runs in background thread with queue buffering.
  - supports pause/resume to hand microphone ownership to recorder.

### UI layer (`ui/`)

- `ui_manager.py`
  - background render thread for PyGame/Wayland.
  - state-driven visuals with PNG assets and procedural fallback.
  - states: `IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `ERROR`.

### Configuration and assets

- `config/config.json` - deployment-specific runtime settings.
- `config/local_soul.md`, `config/cloud_soul.md` - persona prompts.
- `assets/face/` - image assets for expressions.
- `assets/fillers/` - pre-generated filler wav phrases.

### Testing

- `tests/test_router.py` - routes sample prompts and checks expected tool mapping.
- `tests/test_wake_word.py` - wake-word detector validation.
- `tests/test_audio_pipeline.py` - TTS, STT, and round-trip checks.

---

## 4) Runtime Control Flow (Detailed)

### Startup sequence

1. `Config.load()` reads config and environment.
2. `Orchestrator` initializes subsystems in dependency order:
   - audio manager,
   - TTS,
   - STT,
   - Ollama client + router,
   - optional tools requiring API keys (weather/news/cloud),
   - wake-word detector,
   - optional UI manager.
3. Filler WAV cache is built from `assets/fillers`.
4. Startup greeting is spoken.
5. Wake-word loop starts.

### Interaction sequence per wake event

1. Wake callback fires.
2. Router conversation history is cleared (one wake == fresh interaction).
3. Wake-word stream pauses.
4. UI state -> listening.
5. `record_until_silence()` captures utterance.
6. UI state -> thinking.
7. STT transcribes audio.
8. Optional filler phrase playback (except custom "on camera" path).
9. Router returns action:
   - direct chat,
   - local tool call,
   - cloud handoff.
10. Orchestrator executes action and obtains response text.
11. UI state -> speaking.
12. TTS synthesizes response and playback occurs.
13. UI returns to idle, wake detector resumes.

### Shutdown sequence

1. Signal handler sets `_running = False`.
2. Main loop exits.
3. Wake-word detector and UI are stopped.
4. process exits.

---

## 5) Concurrency and Ownership Model

Main concurrency domains:

- Main thread:
  - orchestrator event loop and interaction pipeline.
- Wake-word background thread:
  - continuous mic capture and inference.
- UI background thread:
  - PyGame event + rendering loop.

Shared-resource rules implemented in code:

- Microphone ownership:
  - wake-word thread pauses/releases stream before utterance recording.
- Playback feedback prevention:
  - `AudioManager` mutes during speaker playback.
- UI state updates:
  - protected with `Lock` in `UIManager`.

This avoids direct simultaneous access to mic between detector and recorder.

---

## 6) Data Contracts Between Modules

- Wake detector callback contract:
  - no parameters, triggers orchestrator interaction.

- Audio -> STT:
  - mono `int16` numpy array at 16kHz target sample rate.

- Router output contract (`RouterResult`):
  - `tool`: enum identifying execution path.
  - `response`: direct text only when no tool.
  - `arguments`: dict for tool/cloud invocation.

- TTS -> Audio playback:
  - synthesized WAV file path.

---

## 7) Configuration Model

Key values in `config/config.json` shape behavior:

- audio and model paths (`whisper_path`, `whisper_model`, `piper_voice`).
- wake word model + threshold.
- mic sample rate and target rate.
- model selection (`chat_model`).
- display settings and UI enable flag.
- local default location for weather fallback.

Secrets are expected in `.env` or process environment:

- `OPENWEATHER_API_KEY`
- `NEWSAPI_KEY`
- `MOONSHOT_API_KEY`

---

## 8) Design Decisions and Trade-offs

- Hybrid local-first + cloud fallback:
  - keeps latency/cost low for common queries,
  - still supports complex requests.

- Single local model for both chat and routing:
  - simpler architecture,
  - requires fallback heuristics for unreliable tool-call formatting.

- CLI-based Whisper integration:
  - stable and easy deployment on Pi,
  - introduces process spawn overhead per request.

- File-based TTS output:
  - straightforward playback integration,
  - adds temp-file I/O per response.

- Device lookup by name:
  - robust to re-enumeration index changes,
  - requires matching expected device substrings.

---

## 9) Extension Guide

### Add a new tool

1. Implement tool logic in `brain/tools/`.
2. Add schema entry in `brain/tool_definitions.py`.
3. Add new enum in `ToolType` (`brain/router.py`).
4. Extend orchestrator dispatch logic in `_process_query()`.
5. Add tests in `tests/test_router.py` and tool-specific tests.

### Replace/upgrade local model

1. Change `chat_model` in config.
2. Validate tool-calling response format in router.
3. Re-tune fallback heuristics if needed.

### Run headless

Set `enable_ui` to `false` in config.

### Change wake word model

Update `wake_word_model` path and threshold in config.

---

## 10) Operational Risks and Known Tight Couplings

- Hard-coded Linux/Raspberry Pi paths in defaults.
- ALSA and `/proc`/`/sys` assumptions in system/audio behavior.
- Mic/speaker name constants in code may need per-device editing.
- Some network tools return user-facing error strings directly on failure.
- wake-word model filename case differs between defaults and config in some places (`hey_jansky.onnx` vs `Hey_Jansky.onnx`), which can cause path mismatch if not normalized on filesystem.

---

## 11) Suggested Next Improvements

- Centralize audio device names into configuration file.
- Add structured logging instead of print-based tracing.
- Add unit tests for router fallback heuristics.
- Introduce health-check command for all dependencies (Ollama, whisper binary, model files, APIs).
- Add interface abstractions to simplify future C++ migration/hybridization.

---

## 12) Quick Mental Model

Think of the app as three loops coordinated by the orchestrator:

- listen loop (wake word),
- think/route loop (local model + tools + optional cloud),
- speak/display loop (TTS + UI state).

The orchestrator serializes these loops per interaction, ensuring predictable microphone and speaker ownership with minimal concurrency conflicts.
