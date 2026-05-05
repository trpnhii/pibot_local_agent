## Raspberry Pi 5 (Python) — Step-by-step Setup

This guide sets up **Jansky** on **Raspberry Pi OS (Bookworm, 64-bit)** with:
- **English-first** defaults (`assistant_language/stt_language/tts_language = en`)
- **Gemini** for cloud handoff (via `GEMINI_API_KEY`)

### 0) Prereqs

- **Hardware**: Raspberry Pi 5 (4GB+ recommended), USB mic, USB speaker
- **OS**: Raspberry Pi OS (Bookworm, 64-bit)
- **Network**: required for installing deps + downloading models

### 1) Update system packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 2) Install required system dependencies

```bash
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils
```

### 3) Clone the repo

```bash
git clone https://github.com/mayukh4/pibot_local_agent.git
cd pibot_local_agent
```

### 4) Create the Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
```

### 5) Install Python dependencies

```bash
pip install \
  httpx \
  sounddevice \
  numpy \
  piper-tts \
  openwakeword \
  onnxruntime \
  pygame \
  google-genai
```

Notes:
- `google-genai` is required for **Gemini cloud handoff**.

### 6) Install Ollama + pull the local model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:1.5b
```

If you need to run Ollama manually:

```bash
ollama serve
```

### 7) Build Whisper.cpp and install the CLI

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release -j"$(nproc)"
sudo cp build/bin/whisper-cli /usr/local/bin/whisper-cpp
```

### 8) Download an English Whisper model (English STT)

Your repo is configured to use an **English** Whisper model (`*.en`) for best accuracy/speed on English.

From inside `whisper.cpp/`:

```bash
# Download English base model
bash models/download-ggml-model.sh base.en

# Optional: try a pre-quantized download if your build doesn't have `quantize`
# (some whisper.cpp builds don't compile the quantizer binary)
# bash models/download-ggml-model.sh base.en-q5_0
```

Make sure `config/config.json` points to the downloaded model, e.g.:
- `whisper_model`: `/home/pi/workspace/pibot_local_agent/whisper.cpp/models/ggml-base.en.bin`

Then:

```bash
cd ..
```

### 9) Download an English Piper voice

Create the folder:

```bash
mkdir -p piper/voices
```

Download an English voice into `piper/voices/`:

```bash
wget -O piper/voices/en_GB-semaine-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
wget -O piper/voices/en_GB-semaine-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json
```

Then update `config/config.json`:
- `piper_voice`: `/home/pi/workspace/pibot_local_agent/piper/voices/en_GB-semaine-medium.onnx`

### 10) Configure `config/config.json` paths

Open `config/config.json` and confirm:
- `assistant_language`: `en`
- `stt_language`: `en`
- `tts_language`: `en`
- `whisper_path`: `/usr/local/bin/whisper-cpp`
- `whisper_model`: path to the English model you downloaded (`*.en.bin`)
- `piper_voice`: path to your English Piper voice

Also set `project_root` correctly to your clone location on the Pi, e.g. `/home/pi/pibot_local_agent`.

### 11) Add API keys in `.env` (Gemini)

Create `.env` from template:

```bash
cp .env.example .env
nano .env
```

Set:
- `GEMINI_API_KEY=...`

Optional:
- `OPENWEATHER_API_KEY=...` (weather)
- `NEWSAPI_KEY=...` (news)

### 12) Run Jansky

```bash
source venv/bin/activate
python orchestrator.py
```

### 13) Quick tests

Router test (requires Ollama running):

```bash
source venv/bin/activate
python tests/test_router.py
```

Gemini smoke test (requires `GEMINI_API_KEY` and an account/project with available quota):

```bash
source venv/bin/activate
python tests/test_gemini.py
```

List which Gemini models your key can use:

```bash
source venv/bin/activate
python tests/list_gemini_models.py
```

Audio pipeline test (requires mic + speaker):

```bash
source venv/bin/activate
python tests/test_audio_pipeline.py
```

### 14) Troubleshooting

- **Ollama not running**
  - Start: `ollama serve`
  - Confirm: `ollama list`
- **Whisper model is wrong**
  - For English-only: use `base.en` (or other `*.en` models) and update `whisper_model` in `config/config.json`
- **TTS voice missing**
  - Ensure both `.onnx` and `.onnx.json` exist for your selected Piper voice
- **Audio devices not found**
  - List devices:

```bash
arecord -l
aplay -l
python -c "import sounddevice as sd; print(list(enumerate(sd.query_devices())))"
```

  - Then set these in `config/config.json`:
    - `mic_name`: substring of your microphone device name (leave empty for auto-pick)
    - `speaker_name`: substring of your speaker card name used by `aplay -l` (leave empty for default)

