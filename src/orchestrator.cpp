#include "orchestrator.hpp"

#include <iostream>

#include "brain/tools/joke_tool.hpp"
#include "brain/tools/system_tool.hpp"
#include "brain/tools/time_tool.hpp"

Orchestrator::Orchestrator(const Config& config)
    : config_(config),
      audio_(config.target_sample_rate, config.mic_sample_rate),
      tts_(config.piper_voice),
      stt_(config.whisper_path, config.whisper_model, config.stt_language),
      ollama_(config.chat_model),
      router_(ollama_),
      wake_word_(config.wake_word_model, config.wake_word_threshold, config.mic_sample_rate) {
  if (!config.openweather_api_key.empty()) {
    weather_ = std::make_unique<brain::tools::WeatherTool>(config.openweather_api_key);
  }
  if (!config.newsapi_key.empty()) {
    news_ = std::make_unique<brain::tools::NewsTool>(config.newsapi_key);
  }
  if (!config.moonshot_api_key.empty()) {
    cloud_ = std::make_unique<brain::KimiClient>(config.moonshot_api_key, config.cloud_soul_path);
  }
  if (config.enable_ui) {
    ui_ = std::make_unique<ui::UIManager>(config.display_width, config.display_height, config.use_framebuffer);
  }
}

void Orchestrator::Start() {
  if (ui_) {
    ui_->Start();
    ui_->SetState(ui::UIState::kIdle);
  }
  if (config_.assistant_language == "vi") {
    Speak("Xin chao! Toi la Jansky. Hay noi hey Jansky de goi toi.");
  } else {
    Speak("Hello! I'm Jansky. Say hey Jansky to get my attention.");
  }
  // Placeholder entry path: processes one sample query to verify wiring.
  ProcessQuery("what time is it");
  if (ui_) {
    ui_->Stop();
  }
}

void Orchestrator::ProcessQuery(const std::string& text) {
  const brain::RouterResult result = router_.Route(text);
  switch (result.tool) {
    case brain::ToolType::kNone:
      Speak(result.response);
      break;
    case brain::ToolType::kTime:
      Speak(brain::tools::GetCurrentTime());
      break;
    case brain::ToolType::kWeather:
      Speak(weather_ ? weather_->GetWeather(result.arguments.value("location", config_.local_location))
                    : (config_.assistant_language == "vi" ? "Xin loi, tinh nang thoi tiet chua duoc cau hinh."
                                                          : "Sorry, weather lookup is not configured."));
      break;
    case brain::ToolType::kNews:
      Speak(news_ ? news_->GetNews(result.arguments.value("category", ""))
                 : (config_.assistant_language == "vi" ? "Xin loi, tinh nang tin tuc chua duoc cau hinh."
                                                       : "Sorry, news lookup is not configured."));
      break;
    case brain::ToolType::kSystemStatus:
      Speak(brain::tools::GetSystemStatus());
      break;
    case brain::ToolType::kJoke:
      Speak(brain::tools::GetJoke());
      break;
    case brain::ToolType::kCloud:
      Speak(cloud_ ? cloud_->Chat(result.arguments.value("query", text), false)
                  : (config_.assistant_language == "vi" ? "Xin loi, cloud AI chua duoc cau hinh."
                                                        : "Sorry, cloud AI is not configured."));
      break;
  }
}

void Orchestrator::Speak(const std::string& text) {
  if (text.empty()) return;
  std::cout << "Speaking: " << text << "\n";
  if (ui_) ui_->SetState(ui::UIState::kSpeaking);
  const std::string wav_path = tts_.Synthesize(text);
  audio_.PlayWav(wav_path);
  if (ui_) ui_->SetState(ui::UIState::kIdle);
}
