# PiBot Local Agent — Python to C++ Migration Plan

This document describes how to port **PiBot (Jansky)** from Python to C++ while preserving **behavior**, **control flow**, and a **similar source layout** to the current repository.

For overall architecture, see [`DESIGN_STRUCTURE.md`](DESIGN_STRUCTURE.md).

---

## 1. Goals and constraints

- **Same behavior**: wake word → record with silence end-detection → speech-to-text → route via Ollama (tools + chat) → optional cloud handoff → text-to-speech → playback; optional face UI; same configuration knobs and environment secrets.
- **Same project shape**: mirror today’s packages as directories (e.g. `audio/`, `brain/`, `senses/`, `ui/`, `config/`) using C++ headers and translation units instead of Python modules.
- **No silent logic drift**: treat existing Python as the specification; port in phases with parity checks.

---

## 2. Target C++ architecture

- **Single process** (as today): one orchestrator owns lifecycle, coordinates wake callbacks, recording, routing, TTS, and optional UI thread.
- **Suggested dependencies** (common, well-supported choices):
  - **HTTP**: `libcurl` or **cpp-httplib** (HTTPS for weather, news, cloud, Ollama).
  - **JSON**: **nlohmann/json** or **simdjson**.
  - **Audio I/O**: **PortAudio** (closest analogue to Python `sounddevice`) or **miniaudio**; keep optional **ALSA** playback (`aplay`) for parity with current `AudioManager::play_wav`.
  - **Whisper**: initially **subprocess** to `whisper-cpp` / `whisper-cli` with the same CLI flags as [`audio/stt_engine.py`](../audio/stt_engine.py) for fastest behavioral lock-in; later optionally link **whisper.cpp** in-process.
  - **Wake word**: **ONNX Runtime C++** with the same `.onnx` as today; preprocessing must match Python (48 kHz capture → 16 kHz frames, normalization, chunk sizes).
  - **TTS**: **Piper** via subprocess to the official binary first (parity), or native Piper integration once WAV output matches.
  - **UI**: **SDL2** (PyGame equivalent): Wayland fullscreen, PNG assets under `assets/face/`.
- **Build**: **CMake** at repository root; primary target `jansky` (name TBD); optional `jansky_tests`.

---

## 3. Directory and module mapping

| Python | C++ (suggested) |
|--------|------------------|
| [`orchestrator.py`](../orchestrator.py) | `src/orchestrator.hpp`, `src/orchestrator.cpp`, `src/main.cpp` |
| [`config.py`](../config.py) | `src/config.hpp`, `src/config.cpp` |
| [`audio/audio_manager.py`](../audio/audio_manager.py) | `audio/audio_manager.hpp`, `audio/audio_manager.cpp` |
| [`audio/stt_engine.py`](../audio/stt_engine.py) | `audio/stt_engine.hpp`, `audio/stt_engine.cpp` |
| [`audio/tts_engine.py`](../audio/tts_engine.py) | `audio/tts_engine.hpp`, `audio/tts_engine.cpp` |
| [`brain/router.py`](../brain/router.py) | `brain/router.hpp`, `brain/router.cpp` |
| [`brain/ollama_client.py`](../brain/ollama_client.py) | `brain/ollama_client.hpp`, `brain/ollama_client.cpp` |
| [`brain/cloud_client.py`](../brain/cloud_client.py) | `brain/cloud_client.hpp`, `brain/cloud_client.cpp` |
| [`brain/tool_definitions.py`](../brain/tool_definitions.py) | `brain/tool_definitions.hpp`, `brain/tool_definitions.cpp` (or embedded JSON under `resources/`) |
| [`brain/tools/*.py`](../brain/tools/) | `brain/tools/*.hpp`, `brain/tools/*.cpp` |
| [`senses/wake_word_detector.py`](../senses/wake_word_detector.py) | `senses/wake_word_detector.hpp`, `senses/wake_word_detector.cpp` |
| [`ui/ui_manager.py`](../ui/ui_manager.py) | `ui/ui_manager.hpp`, `ui/ui_manager.cpp` |
| [`tests/test_*.py`](../tests/) | `tests/` with **GoogleTest** or **Catch2**; keep manual mic/speaker harnesses where needed |

**Keep on disk unchanged (paths via config):**

- [`config/`](../config/) — `config.json`, `local_soul.md`, `cloud_soul.md`
- [`assets/`](../assets/)
- Wake word models under `models/wake_word/`
- Piper voice files and Whisper model paths as configured today

---

## 4. Phased execution (low risk)

### Phase A — Skeleton and configuration parity

- Implement `Config::load()` with the same precedence as Python: defaults → `config/config.json` → `.env` → process environment overrides.
- Add a debug **config dump** on startup to verify Pi vs dev machine paths.

### Phase B — Audio manager parity

- Port: device lookup by name substring, input stream at `mic_sample_rate`, RMS silence detection, decimation 48 kHz → 16 kHz, mute/unmute around playback, WAV playback path.
- **Fixture test**: feed a known WAV through decimation/normalization and compare to a saved reference or a short Python reference script (floating tolerance).

### Phase C — STT and TTS parity

- **STT**: subprocess to Whisper CLI first; match arguments from current [`WhisperSTT`](../audio/stt_engine.py) (`-m`, `-f`, `-l`, `-t`, `--no-timestamps`, `-np`).
- **TTS**: subprocess Piper (or library) until output WAV matches expected format for playback.

### Phase D — HTTP clients

- **Ollama**: `POST /api/chat`; parse `message`, `content`, and `tool_calls` like [`OllamaClient`](../brain/ollama_client.py).
- **Kimi / Moonshot**: match non-streaming path used by orchestrator first; streaming can follow.
- **Weather / news / joke**: same URLs, query parameters, and error-to-speech behavior as Python tools.

### Phase E — Router and tools

- Port `ToolType`, `RouterResult`, keyword fallback ordering, conversation history window (last 8 messages / 4 exchanges), and `SYSTEM_PROMPT` / `TOOLS` text (prefer byte-for-byte identity).
- Run a **prompt corpus** with a **mock Ollama HTTP server** so router decisions are deterministic in CI.

### Phase F — Wake word

- Highest risk for subtle drift: ONNX inference plus **identical** preprocessing to [`WakeWordDetector`](../senses/wake_word_detector.py).
- Log per-frame scores against Python on the same raw PCM capture to validate threshold behavior.

### Phase G — UI

- SDL2 render thread: states `IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `ERROR`; load PNGs from configured `assets_path`; procedural fallback when assets missing.
- Honor Wayland-related environment behavior consistent with [`UIManager`](../ui/ui_manager.py).

### Phase H — Integration and packaging

- Single installable binary; update or replace [`setup.sh`](../setup.sh) with build steps (CMake, ONNX Runtime, SDL2, optional PortAudio).
- Document paths for Whisper binary, Piper, ONNX model, and Ollama assumptions (unchanged from README conceptually).

---

## 5. Testing strategy

- **Contract tests**: mock HTTP servers for Ollama and Moonshot where possible.
- **Audio fixtures**: short WAV files in `tests/fixtures/` (committed or generated).
- **Side-by-side parity**: same input transcript → same `ToolType` and arguments; same final spoken text string before TTS where applicable.
- **Definition of done**: same runtime flow and tool routing on a fixed test set as described in [`DESIGN_STRUCTURE.md`](../DESIGN_STRUCTURE.md) and [`README.md`](../README.md).

---

## 6. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Wake word preprocessing mismatch | Numerical parity tests vs Python on recorded PCM; tune chunking and gain to match |
| Mic opened twice (wake + record) | Preserve pause/resume and stream teardown order exactly as orchestrator + detector do today |
| Hard-coded device names | During port, move `MIC_NAME` / `SPEAKER_NAME` into `config.json` (behavior-preserving, easier deployments) |
| Path defaults (`/home/jansky/...`) | Always set `project_root` and paths in `config.json` per machine |
| Windows vs Linux audio | Primary target remains Pi/Linux; develop audio/UI on WSL or hardware |

---

## 7. Effort order of magnitude

- Expect **multiple person-weeks** for a faithful port with wake word + SDL UI + full router parity, assuming Whisper and Piper start as subprocesses.
- In-linking whisper.cpp, tighter ONNX optimization, and polished CI add time.

---

## 8. Optional hybrid path (if full port stalls)

- Keep Python orchestration temporarily; move **audio capture**, **wake word**, or **STT** to a small C++ library with a C ABI and call from Python via pybind11 — then continue replacing modules until the Python layer disappears.

---

## Related documents

- [`DESIGN_STRUCTURE.md`](../DESIGN_STRUCTURE.md) — current system design
- [`README.md`](../README.md) — setup, dependencies, and operational flow
