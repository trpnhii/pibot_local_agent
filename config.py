"""
Configuration management for Jansky.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


@dataclass
class Config:
    """Application configuration."""

    # Paths (adjusted for actual installation location)
    project_root: str = "/home/jansky/jansky"
    assets_path: str = "/home/jansky/jansky/assets/face"

    # Language
    assistant_language: str = "en"
    stt_language: str = "en"
    tts_language: str = "en"

    # Audio - Piper TTS (using piper-tts Python package)
    piper_voice: str = "/home/jansky/jansky/piper/voices/en_GB-semaine-medium.onnx"

    # Whisper.cpp
    whisper_path: str = "/usr/local/bin/whisper-cpp"
    whisper_model: str = "/home/jansky/jansky/whisper.cpp/models/ggml-base.en-q5_0.bin"

    # Models
    chat_model: str = "qwen2.5:1.5b"
    routing_engine: str = "gemini"  # "gemini" (no ollama) or "ollama"

    # Wake word
    wake_word_model: str = "/home/jansky/jansky/models/wake_word/Hey_Jansky.onnx"
    wake_word_threshold: float = 0.5
    wake_word_log_scores: bool = False
    wake_word_log_interval_s: float = 0.5

    # Microphone settings (for USB mics that may have different sample rates)
    mic_sample_rate: int = 48000
    mic_name: str = ""
    speaker_name: str = ""

    # Local location default
    local_location: str = "Kingston, CA"
    target_sample_rate: int = 16000

    # API Keys (loaded from environment)
    openweather_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    moonshot_api_key: str = ""
    newsapi_key: str = ""

    # Soul/personality files
    local_soul_path: str = "/home/jansky/jansky/config/local_soul.md"
    cloud_soul_path: str = "/home/jansky/jansky/config/cloud_soul.md"

    # Display
    display_width: int = 800
    display_height: int = 480
    use_framebuffer: bool = False
    ui_window_scale: float = 0.8

    # Features
    enable_streaming_tts: bool = False
    enable_ui: bool = True

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file and environment."""
        config = cls()

        # If running outside the Raspberry Pi image, the default /home/jansky/jansky
        # paths won't exist. Auto-detect project root from this file location so
        # local dev (Windows/macOS/Linux) loads the repo's config/.env correctly.
        if not Path(config.project_root).exists():
            detected_root = Path(__file__).resolve().parent
            config.project_root = str(detected_root)
            config.assets_path = str(detected_root / "assets" / "face")
            config.local_soul_path = str(detected_root / "config" / "local_soul.md")
            config.cloud_soul_path = str(detected_root / "config" / "cloud_soul.md")

        # Load from JSON file if exists
        if config_path is None:
            config_path = os.path.join(config.project_root, "config", "config.json")

        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # Load from .env file if present
        env_path = os.path.join(config.project_root, ".env")
        if Path(env_path).exists():
            config._load_env_file(env_path)

        # Override with environment variables
        config.openweather_api_key = os.getenv(
            "OPENWEATHER_API_KEY",
            config.openweather_api_key
        )
        config.gemini_api_key = os.getenv("GEMINI_API_KEY", config.gemini_api_key)
        config.gemini_model = os.getenv("GEMINI_MODEL", config.gemini_model)
        # Backward compatibility: allow legacy env var to keep working
        config.moonshot_api_key = os.getenv("MOONSHOT_API_KEY", config.moonshot_api_key)
        if not config.gemini_api_key and config.moonshot_api_key:
            config.gemini_api_key = config.moonshot_api_key
        config.newsapi_key = os.getenv(
            "NEWSAPI_KEY",
            config.newsapi_key
        )

        return config

    def _load_env_file(self, path: str):
        """Load environment variables from .env file."""
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    def save(self, config_path: Optional[str] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = os.path.join(self.project_root, "config", "config.json")

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        # Don't save API keys to file
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key") and not k.endswith("_key")
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
