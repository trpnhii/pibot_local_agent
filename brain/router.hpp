#pragma once

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

#include "brain/ollama_client.hpp"

namespace brain {

enum class ToolType { kTime, kWeather, kNews, kSystemStatus, kJoke, kCloud, kNone };

struct RouterResult {
  ToolType tool = ToolType::kNone;
  std::string response;
  nlohmann::json arguments = nlohmann::json::object();
};

class Router {
 public:
  explicit Router(OllamaClient client);
  RouterResult Route(const std::string& user_input);
  void ClearHistory();

 private:
  bool IsLocalChat(const std::string& user_input) const;
  std::string ExtractNewsCategory(const std::string& user_input) const;
  std::string ExtractLocation(const std::string& user_input, const std::string& response_text) const;
  std::pair<ToolType, nlohmann::json> DetectToolFromText(const std::string& user_input, const std::string& response_text) const;
  static std::string ToLower(std::string value);

  OllamaClient client_;
  nlohmann::json conversation_history_ = nlohmann::json::array();
};

}  // namespace brain
