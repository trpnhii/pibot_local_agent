#pragma once

#include <optional>
#include <string>

struct Config {
  // Paths
  std::string project_root = "/home/jansky/jansky";
  std::string assets_path = "/home/jansky/jansky/assets/face";

  // Audio / models
  std::string piper_voice =
      "/home/jansky/jansky/piper/voices/en_GB-semaine-medium.onnx";
  std::string whisper_path = "/usr/local/bin/whisper-cpp";
  std::string whisper_model =
      "/home/jansky/jansky/whisper.cpp/models/ggml-base.en-q5_0.bin";
  std::string chat_model = "qwen2.5:1.5b";

  // Wake word
  std::string wake_word_model = "/home/jansky/jansky/models/wake_word/hey_jansky.onnx";
  double wake_word_threshold = 0.5;

  // Audio settings
  int mic_sample_rate = 48000;
  int target_sample_rate = 16000;

  // Defaults
  std::string local_location = "Kingston, CA";

  // API keys
  std::string openweather_api_key = "";
  std::string moonshot_api_key = "";
  std::string newsapi_key = "";

  // Personality prompts
  std::string local_soul_path = "/home/jansky/jansky/config/local_soul.md";
  std::string cloud_soul_path = "/home/jansky/jansky/config/cloud_soul.md";

  // Display
  int display_width = 800;
  int display_height = 480;
  bool use_framebuffer = true;

  // Features
  bool enable_streaming_tts = false;
  bool enable_ui = true;

  static Config Load(const std::optional<std::string>& config_path = std::nullopt);
  std::string ToDebugString() const;
};
