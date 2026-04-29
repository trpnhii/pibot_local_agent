#pragma once

#include <memory>
#include <string>

#include "audio/audio_manager.hpp"
#include "audio/stt_engine.hpp"
#include "audio/tts_engine.hpp"
#include "brain/cloud_client.hpp"
#include "brain/ollama_client.hpp"
#include "brain/router.hpp"
#include "brain/tools/news_tool.hpp"
#include "brain/tools/weather_tool.hpp"
#include "config.hpp"
#include "senses/wake_word_detector.hpp"
#include "ui/ui_manager.hpp"

class Orchestrator {
 public:
  explicit Orchestrator(const Config& config);
  void Start();

 private:
  void ProcessQuery(const std::string& text);
  void Speak(const std::string& text);

  Config config_;
  audio::AudioManager audio_;
  audio::PiperTTS tts_;
  audio::WhisperSTT stt_;
  brain::OllamaClient ollama_;
  brain::Router router_;
  std::unique_ptr<brain::tools::WeatherTool> weather_;
  std::unique_ptr<brain::tools::NewsTool> news_;
  std::unique_ptr<brain::KimiClient> cloud_;
  senses::WakeWordDetector wake_word_;
  std::unique_ptr<ui::UIManager> ui_;
};
