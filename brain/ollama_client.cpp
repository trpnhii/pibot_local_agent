#include "brain/ollama_client.hpp"

#include <algorithm>

namespace brain {

OllamaClient::OllamaClient(std::string model, std::string base_url)
    : model_(std::move(model)), base_url_(std::move(base_url)) {}

ChatResponse OllamaClient::Chat(const nlohmann::json& messages, const nlohmann::json* /*tools*/) const {
  ChatResponse out;
  if (!messages.is_array() || messages.empty()) {
    out.content = "I didn't receive any message.";
    return out;
  }

  std::string user_content;
  for (auto it = messages.rbegin(); it != messages.rend(); ++it) {
    if ((*it).contains("role") && (*it)["role"] == "user" && (*it).contains("content")) {
      user_content = (*it)["content"].get<std::string>();
      break;
    }
  }

  if (user_content.empty()) {
    out.content = "I am ready.";
    return out;
  }

  out.content = "Local C++ fallback response: " + user_content;
  return out;
}

bool OllamaClient::IsAvailable() const {
  return !model_.empty() && !base_url_.empty();
}

}  // namespace brain
